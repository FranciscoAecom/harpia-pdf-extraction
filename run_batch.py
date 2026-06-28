import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import logging
import sys
from datetime import datetime
from pathlib import Path
from time import monotonic

import pandas as pd


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harpia_parser.config.loader import load_config, output_tabs_for_template  # noqa: E402
from harpia_parser.batch.models import DocumentExtraction  # noqa: E402
from harpia_parser.batch.cache import BatchCache, exact_duplicate_plan  # noqa: E402
from harpia_parser.batch.discovery import list_pdfs, read_pdf_text  # noqa: E402
from harpia_parser.batch.executor import extract_pdf_once  # noqa: E402
from harpia_parser.audit.duplicate_audit import (  # noqa: E402
    build_duplicate_audit,
    build_duplicate_candidate,
    duplicate_paths_to_skip,
    text_sha256,
)
from harpia_parser.constants import ACM_EXTRACTION_TIMESTAMP_COLUMN  # noqa: E402
from harpia_parser.core.scope import classify_document  # noqa: E402
from harpia_parser.formatting.output_writer import salvar  # noqa: E402


DEFAULT_INPUT_DIRS = [
    Path(r"L:\Secure_DCS\BRBLH1PINFW001\COE_Digital\others\harpia_rd"),
    Path(r"L:\Secure_DCS\BRBLH1PINFW001\COE_Digital\others\lumen"),
]
log = logging.getLogger(__name__)
error_log = logging.getLogger("harpia_parser.errors")


def _configure_logging(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    execution_file = logging.FileHandler(output_dir / "extraction.log", mode="w", encoding="utf-8")
    execution_file.setLevel(logging.INFO)
    execution_file.setFormatter(formatter)
    root_logger.addHandler(execution_file)

    error_log.handlers.clear()
    error_log.setLevel(logging.ERROR)
    error_log.propagate = False
    error_file = logging.FileHandler(output_dir / "extraction_errors.log", mode="w", encoding="utf-8")
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
    ))
    error_log.addHandler(error_file)

    logging.getLogger("harpia_parser.core.pipeline").setLevel(logging.WARNING)


def _elapsed_text(started_at: float) -> str:
    elapsed = max(0, int(monotonic() - started_at))
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _log_progress(index: int, total: int, summary: list[dict], started_at: float) -> None:
    if index != total and index % 100 != 0:
        return
    statuses = Counter(str(row.get("status") or "") for row in summary)
    percent = (index / total * 100) if total else 100.0
    log.info(
        "[PROGRESSO] %d/%d (%.1f%%) | extraidos=%d | duplicados=%d | fora_escopo=%d | erros=%d | tempo=%s",
        index,
        total,
        percent,
        statuses["extraido"],
        statuses["duplicado_nao_persistido"],
        statuses["fora_escopo"],
        statuses["erro"],
        _elapsed_text(started_at),
    )


def _log_document_alerts(pdf: Path, section_audit_df: pd.DataFrame, table_audit_df: pd.DataFrame) -> None:
    section_alerts = set()
    if not section_audit_df.empty and "status" in section_audit_df.columns:
        section_alerts = set(section_audit_df["status"].dropna().astype(str)) - {"ok", "nao_aplicavel"}
    table_alerts = set()
    if not table_audit_df.empty and "status" in table_audit_df.columns:
        table_alerts = set(table_audit_df["status"].dropna().astype(str)) & {
            "alerta_descoberta",
            "alerta_descoberta_com_opcional_ausente",
            "fallback",
            "fallback_cabecalho_texto_layout_incompleto",
        }
    if section_alerts or table_alerts:
        log.warning(
            "[ALERTA] %s | secoes=%s | tabelas=%s",
            pdf.name,
            ",".join(sorted(section_alerts)) or "ok",
            ",".join(sorted(table_alerts)) or "ok",
        )


def _timestamp_text() -> str:
    return datetime.now().replace(microsecond=0).strftime("%d/%m/%Y %H:%M:%S")


def _first_value(dataframes: list[pd.DataFrame], column: str) -> str | None:
    for dataframe in dataframes:
        if column in dataframe.columns and not dataframe.empty:
            values = dataframe[column].dropna()
            if not values.empty:
                return str(values.iloc[0])
    return None


def _winner_template_id(audit_df: pd.DataFrame) -> str | None:
    if audit_df.empty or "template_avaliado" not in audit_df.columns:
        return None
    if "status" in audit_df.columns:
        winners = audit_df[audit_df["status"].astype(str) == "winner"]["template_avaliado"].dropna()
        if not winners.empty:
            return str(winners.iloc[0])
    values = audit_df["template_avaliado"].dropna()
    return str(values.iloc[0]) if not values.empty else None


def classify_batch(input_dirs: list[Path], output_path: Path, max_pages: int | None = 3) -> None:
    config = load_config(ROOT)
    rows = []
    pdfs = list_pdfs(input_dirs)
    extraction_timestamp = _timestamp_text()

    for index, pdf in enumerate(pdfs, start=1):
        log.info("[%d/%d] Classificando %s", index, len(pdfs), pdf.name)
        try:
            texto = read_pdf_text(pdf, max_pages=max_pages)
            result = classify_document(texto, config, pdf)
            rows.append({
                "arquivo": pdf.name,
                "caminho": str(pdf),
                "id_taxonomia": result.id_taxonomia,
                "nome_taxonomia": result.nome_taxonomia,
                "versao_template": result.versao_template,
                ACM_EXTRACTION_TIMESTAMP_COLUMN: extraction_timestamp,
                "status": "identificado" if result.template_id else "fora_escopo",
                "scores": "; ".join(
                    f"{score.template_id}:{score.status}:{score.score}/{score.score_minimo}"
                    for score in result.scores
                ),
            })
        except Exception as exc:
            rows.append({
                "arquivo": pdf.name,
                "caminho": str(pdf),
                "id_taxonomia": None,
                "nome_taxonomia": None,
                "versao_template": None,
                ACM_EXTRACTION_TIMESTAMP_COLUMN: extraction_timestamp,
                "status": "erro",
                "scores": f"{type(exc).__name__}: {exc}",
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(output_path, index=False)
    log.info("Auditoria de classificacao salva em: %s", output_path)


def extract_batch(input_dirs: list[Path], output_dir: Path, workers: int = 5, preclassify_pages: int = 3) -> None:
    started_at = monotonic()
    config = load_config(ROOT)
    all_results: dict[str, list[pd.DataFrame]] = {}
    all_samples: dict[str, list[pd.DataFrame]] = {}
    all_clients: dict[str, list[pd.DataFrame]] = {}
    all_packaging_preservatives: dict[str, list[pd.DataFrame]] = {}
    all_notes: dict[str, list[pd.DataFrame]] = {}
    all_general_considerations: dict[str, list[pd.DataFrame]] = {}
    all_conformity_statement: dict[str, list[pd.DataFrame]] = {}
    all_validation_key: dict[str, list[pd.DataFrame]] = {}
    all_revision_reason: dict[str, list[pd.DataFrame]] = {}
    all_audits: dict[str, list[pd.DataFrame]] = {}
    all_table_audits: dict[str, list[pd.DataFrame]] = {}
    all_section_audits: dict[str, list[pd.DataFrame]] = {}
    all_field_audits: dict[str, list[pd.DataFrame]] = {}
    all_duplicate_candidates = {}
    candidate_by_path = {}
    theme_by_path: dict[str, str] = {}
    canonical_text_paths: dict[tuple[str, str], str] = {}
    empty_text_hash = text_sha256("")
    extracted_documents: dict[str, list[DocumentExtraction]] = {}
    summary = []
    pdfs = list_pdfs(input_dirs)
    cache = BatchCache(output_dir / ".cache", ROOT, SRC)
    log.info("Calculando hashes binarios com %d workers...", workers)
    file_hashes, cached_hashes = cache.file_hashes(pdfs, workers)
    taxonomy_hash = cache.runtime_signature(config.taxonomy_path, Path(__file__))
    pdfs_to_extract, exact_duplicates = exact_duplicate_plan(pdfs, file_hashes)
    extraction_timestamp = _timestamp_text()
    log.info("=" * 70)
    log.info("EXTRACAO DE DOCUMENTOS")
    log.info("Inicio: %s", extraction_timestamp)
    log.info("Taxonomia: %s", config.taxonomy_path)
    log.info("Pastas de entrada: %s", "; ".join(str(path) for path in input_dirs))
    log.info("PDFs encontrados: %d", len(pdfs))
    log.info("Duplicados binarios ignorados antes da extracao: %d", len(exact_duplicates))
    log.info("PDFs enviados ao parser: %d", len(pdfs_to_extract))
    log.info("Hashes reutilizados do cache: %d", cached_hashes)
    log.info("=" * 70)

    extraction_executor = ThreadPoolExecutor(max_workers=max(1, workers))
    extraction_results = extraction_executor.map(
        lambda pdf: extract_pdf_once(
            pdf, config, file_hashes[str(pdf)], taxonomy_hash, cache, preclassify_pages
        ),
        pdfs_to_extract,
        buffersize=max(2, workers * 2),
    )
    cached_extractions = 0
    for index, extraction in enumerate(extraction_results, start=1):
        pdf = extraction.path
        texto = extraction.text
        pipeline_outputs = extraction.outputs
        extraction_error = extraction.error
        cached_extractions += int(extraction.from_cache)
        try:
            if extraction_error is not None:
                raise extraction_error
            if texto is None or pipeline_outputs is None:
                raise RuntimeError("Extracao nao retornou dados nem erro.")
            outputs = pipeline_outputs
            df, sample_df, client_df = outputs.results, outputs.sample, outputs.client
            packaging_preservatives_df = outputs.packaging_preservatives
            notes_df = outputs.notes
            general_considerations_df = outputs.general_considerations
            conformity_statement_df = outputs.conformity_statement
            validation_key_df = outputs.validation_key
            revision_reason_df = outputs.revision_reason
            audit_df = outputs.classification_audit
            table_audit_df = outputs.table_extraction_audit
            section_audit_df = outputs.section_extraction_audit
            field_audit_df = outputs.field_extraction_audit
            template_id = _winner_template_id(audit_df)
            template = config.templates.get(template_id or "", {})
            tipo_laudo = str(template.get("theme_id") or "") if template else None
            id_taxonomia = _first_value([df, sample_df, client_df, packaging_preservatives_df], "id_taxonomia")
            nome_taxonomia = _first_value([df, sample_df, client_df, packaging_preservatives_df], "nome_taxonomia")
            versao_template = _first_value([df, sample_df, client_df, packaging_preservatives_df], "versao_template")

            if not template_id or not tipo_laudo:
                summary.append({
                    "arquivo": pdf.name,
                    "caminho": str(pdf),
                    "status": "fora_escopo",
                    "id_taxonomia": None,
                    "nome_taxonomia": None,
                    "versao_template": None,
                    ACM_EXTRACTION_TIMESTAMP_COLUMN: extraction_timestamp,
                    "results_rows": 0,
                    "sample_rows": 0,
                    "client_rows": 0,
                })
                _log_progress(index, len(pdfs_to_extract), summary, started_at)
                continue

            duplicate_candidate = build_duplicate_candidate(
                pdf,
                texto,
                df,
                sample_df,
                file_hash=file_hashes[str(pdf)],
            )

            all_duplicate_candidates.setdefault(tipo_laudo, []).append(duplicate_candidate)
            candidate_by_path[str(pdf)] = duplicate_candidate
            theme_by_path[str(pdf)] = tipo_laudo
            summary_row = {
                "arquivo": pdf.name,
                "caminho": str(pdf),
                "status": "extraido",
                "id_taxonomia": id_taxonomia,
                "nome_taxonomia": nome_taxonomia,
                "versao_template": versao_template,
                ACM_EXTRACTION_TIMESTAMP_COLUMN: extraction_timestamp,
                "results_rows": len(df),
                "sample_rows": len(sample_df),
                "client_rows": len(client_df),
                "packaging_preservatives_rows": len(packaging_preservatives_df),
                "notes_rows": len(notes_df),
                "general_considerations_rows": len(general_considerations_df),
                "conformity_statement_rows": len(conformity_statement_df),
                "validation_key_rows": len(validation_key_df),
                "revision_reason_rows": len(revision_reason_df),
                "section_extraction_audit_rows": len(section_audit_df),
                "field_extraction_audit_rows": len(field_audit_df),
            }
            summary.append(summary_row)
            text_key = (tipo_laudo, duplicate_candidate.hash_texto)
            text_reference = canonical_text_paths.get(text_key)
            if text_reference and duplicate_candidate.hash_texto != empty_text_hash:
                summary_row["status"] = "duplicado_nao_persistido"
                summary_row["motivo"] = f"Duplicado textual de {Path(text_reference).name}."
                for column in [key for key in summary_row if key.endswith("_rows")]:
                    summary_row[column] = 0
            else:
                canonical_text_paths[text_key] = str(pdf)
                extracted_documents.setdefault(tipo_laudo, []).append(
                    DocumentExtraction(pdf, outputs, summary_row)
                )
            _log_document_alerts(pdf, section_audit_df, table_audit_df)
        except Exception as exc:
            summary.append({
                "arquivo": pdf.name,
                "caminho": str(pdf),
                "status": "erro",
                "id_taxonomia": None,
                "nome_taxonomia": None,
                "versao_template": None,
                ACM_EXTRACTION_TIMESTAMP_COLUMN: extraction_timestamp,
                "results_rows": 0,
                "sample_rows": 0,
                "client_rows": 0,
                "erro": f"{type(exc).__name__}: {exc}",
            })
            log.error("[ERRO] %s | %s: %s", pdf.name, type(exc).__name__, exc)
            error_log.exception("Falha ao processar %s", pdf)
        _log_progress(index, len(pdfs_to_extract), summary, started_at)
    extraction_executor.shutdown(wait=True)

    for duplicate_path, canonical_path in exact_duplicates.items():
        canonical_candidate = candidate_by_path.get(str(canonical_path))
        canonical_theme = theme_by_path.get(str(canonical_path))
        duplicate = Path(duplicate_path)
        if canonical_candidate is not None and canonical_theme is not None:
            duplicate_candidate = replace(
                canonical_candidate,
                nome_do_arquivo=duplicate.name,
                caminho_arquivo=duplicate_path,
            )
            all_duplicate_candidates.setdefault(canonical_theme, []).append(duplicate_candidate)
            candidate_by_path[duplicate_path] = duplicate_candidate
            theme_by_path[duplicate_path] = canonical_theme
        summary.append({
            "arquivo": duplicate.name,
            "caminho": duplicate_path,
            "status": "duplicado_nao_persistido",
            "id_taxonomia": canonical_candidate.id_taxonomia if canonical_candidate else None,
            "nome_taxonomia": canonical_candidate.nome_taxonomia if canonical_candidate else None,
            "versao_template": canonical_candidate.versao_template if canonical_candidate else None,
            ACM_EXTRACTION_TIMESTAMP_COLUMN: extraction_timestamp,
            "results_rows": 0,
            "sample_rows": 0,
            "client_rows": 0,
            "motivo": f"Duplicado binario de {canonical_path.name}; nao enviado ao parser.",
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    duplicate_audits_by_theme: dict[str, pd.DataFrame] = {}
    output_themes = sorted(extracted_documents)
    for tipo_laudo, documents in extracted_documents.items():
        candidates = all_duplicate_candidates.get(tipo_laudo, [])
        duplicate_audit_df = build_duplicate_audit(candidates)
        duplicate_audits_by_theme[tipo_laudo] = duplicate_audit_df
        skipped_paths = duplicate_paths_to_skip(candidates)

        for document in documents:
            summary_row = document.summary
            if str(document.path) in skipped_paths:
                summary_row["status"] = "duplicado_nao_persistido"
                summary_row["motivo"] = "PDF duplicado; registros mantidos apenas no arquivo canonico do grupo."
                for column in [
                    "results_rows",
                    "sample_rows",
                    "client_rows",
                    "packaging_preservatives_rows",
                    "notes_rows",
                    "general_considerations_rows",
                    "conformity_statement_rows",
                    "validation_key_rows",
                    "revision_reason_rows",
                    "section_extraction_audit_rows",
                    "field_extraction_audit_rows",
                ]:
                    summary_row[column] = 0
                continue

            outputs = document.outputs
            all_results.setdefault(tipo_laudo, []).append(outputs.results)
            all_samples.setdefault(tipo_laudo, []).append(outputs.sample)
            all_clients.setdefault(tipo_laudo, []).append(outputs.client)
            all_packaging_preservatives.setdefault(tipo_laudo, []).append(outputs.packaging_preservatives)
            all_notes.setdefault(tipo_laudo, []).append(outputs.notes)
            all_general_considerations.setdefault(tipo_laudo, []).append(outputs.general_considerations)
            all_conformity_statement.setdefault(tipo_laudo, []).append(outputs.conformity_statement)
            all_validation_key.setdefault(tipo_laudo, []).append(outputs.validation_key)
            all_revision_reason.setdefault(tipo_laudo, []).append(outputs.revision_reason)
            all_audits.setdefault(tipo_laudo, []).append(outputs.classification_audit)
            all_table_audits.setdefault(tipo_laudo, []).append(outputs.table_extraction_audit)
            all_section_audits.setdefault(tipo_laudo, []).append(outputs.section_extraction_audit)
            all_field_audits.setdefault(tipo_laudo, []).append(outputs.field_extraction_audit)
        documents.clear()

    extracted_documents.clear()

    for tipo_laudo in output_themes:
        results_df = pd.concat(all_results.get(tipo_laudo, []), ignore_index=True) if all_results.get(tipo_laudo) else pd.DataFrame()
        sample_df = pd.concat(all_samples.get(tipo_laudo, []), ignore_index=True) if all_samples.get(tipo_laudo) else pd.DataFrame()
        client_df = pd.concat(all_clients.get(tipo_laudo, []), ignore_index=True) if all_clients.get(tipo_laudo) else pd.DataFrame()
        packaging_preservatives_df = (
            pd.concat(all_packaging_preservatives.get(tipo_laudo, []), ignore_index=True)
            if all_packaging_preservatives.get(tipo_laudo)
            else pd.DataFrame()
        )
        notes_df = pd.concat(all_notes.get(tipo_laudo, []), ignore_index=True) if all_notes.get(tipo_laudo) else pd.DataFrame()
        general_considerations_df = (
            pd.concat(all_general_considerations.get(tipo_laudo, []), ignore_index=True)
            if all_general_considerations.get(tipo_laudo)
            else pd.DataFrame()
        )
        conformity_statement_df = (
            pd.concat(all_conformity_statement.get(tipo_laudo, []), ignore_index=True)
            if all_conformity_statement.get(tipo_laudo)
            else pd.DataFrame()
        )
        validation_key_df = (
            pd.concat(all_validation_key.get(tipo_laudo, []), ignore_index=True)
            if all_validation_key.get(tipo_laudo)
            else pd.DataFrame()
        )
        revision_reason_df = (
            pd.concat(all_revision_reason.get(tipo_laudo, []), ignore_index=True)
            if all_revision_reason.get(tipo_laudo)
            else pd.DataFrame()
        )
        audit_df = pd.concat(all_audits.get(tipo_laudo, []), ignore_index=True) if all_audits.get(tipo_laudo) else pd.DataFrame()
        table_audit_df = pd.concat(all_table_audits.get(tipo_laudo, []), ignore_index=True) if all_table_audits.get(tipo_laudo) else pd.DataFrame()
        section_audit_df = (
            pd.concat(all_section_audits.get(tipo_laudo, []), ignore_index=True)
            if all_section_audits.get(tipo_laudo)
            else pd.DataFrame()
        )
        field_audit_df = (
            pd.concat(all_field_audits.get(tipo_laudo, []), ignore_index=True)
            if all_field_audits.get(tipo_laudo)
            else pd.DataFrame()
        )
        duplicate_audit_df = duplicate_audits_by_theme.get(tipo_laudo, pd.DataFrame())

        template_id = _winner_template_id(audit_df)
        output_tabs = output_tabs_for_template(config, template_id) if template_id else None
        validation_errors_df = salvar(
            results_df,
            output_dir / tipo_laudo / "extracted_data.xlsx",
            sample_df=sample_df,
            client_df=client_df,
            output_tabs=output_tabs,
            classification_audit_df=audit_df,
            table_extraction_audit_df=table_audit_df,
            section_extraction_audit_df=section_audit_df,
            field_extraction_audit_df=field_audit_df,
            duplicate_audit_df=duplicate_audit_df,
            packaging_preservatives_df=packaging_preservatives_df,
            notes_df=notes_df,
            general_considerations_df=general_considerations_df,
            conformity_statement_df=conformity_statement_df,
            validation_key_df=validation_key_df,
            revision_reason_df=revision_reason_df,
        )
        log.info(
            "[SAIDA] %s | resultados=%d | amostras=%d | clientes=%d | validacoes=%d",
            tipo_laudo,
            len(results_df),
            len(sample_df),
            len(client_df),
            len(validation_errors_df),
        )

    summary_df = pd.DataFrame(summary)
    summary_path = output_dir / "batch_extraction_summary.xlsx"
    summary_df.to_excel(summary_path, index=False)
    statuses = Counter(summary_df["status"].dropna().astype(str)) if not summary_df.empty else Counter()
    log.info("=" * 70)
    log.info("RESUMO FINAL")
    log.info("Duracao: %s", _elapsed_text(started_at))
    log.info("PDFs processados: %d", len(summary_df))
    log.info("Extraidos: %d", statuses["extraido"])
    log.info("Fora do escopo: %d", statuses["fora_escopo"])
    log.info("Duplicados nao persistidos: %d", statuses["duplicado_nao_persistido"])
    log.info("Com erro: %d", statuses["erro"])
    log.info("Extracoes reutilizadas do cache: %d", cached_extractions)
    log.info("Resumo: %s", summary_path)
    log.info("Log: %s", output_dir / "extraction.log")
    log.info("Erros: %s", output_dir / "extraction_errors.log")
    log.info("=" * 70)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Processa lotes de PDFs do Harpia.")
    parser.add_argument(
        "mode",
        choices=["classify", "extract"],
        help="Use classify para auditar templates ou extract para extrair os dados.",
    )
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        default=DEFAULT_INPUT_DIRS,
        help="Uma ou mais pastas raiz contendo PDFs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output",
        help="Pasta de saida.",
    )
    parser.add_argument(
        "--classify-pages",
        type=int,
        default=5,
        help="Numero de paginas lidas por PDF no modo classify. Use 0 para ler todas.",
    )
    parser.add_argument(
        "--preclassify-pages",
        type=int,
        default=3,
        help="Paginas usadas na pre-classificacao. Use 0 para desativar.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Numero de workers para hash e extracao. Use 1 para processamento sequencial.",
    )
    args = parser.parse_args(argv)
    _configure_logging(args.output)

    if args.mode == "classify":
        max_pages = args.classify_pages if args.classify_pages > 0 else None
        classify_batch(args.input, args.output / "template_classification_audit.xlsx", max_pages=max_pages)
    else:
        extract_batch(
            args.input,
            args.output,
            workers=max(1, args.workers),
            preclassify_pages=max(0, args.preclassify_pages),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
