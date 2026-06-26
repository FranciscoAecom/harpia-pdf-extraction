import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pdfplumber


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harpia_parser.config.loader import load_config, output_tabs_for_template  # noqa: E402
from harpia_parser.audit.duplicate_audit import (  # noqa: E402
    build_duplicate_audit,
    build_duplicate_candidate,
    duplicate_paths_to_skip,
)
from harpia_parser.constants import ACM_EXTRACTION_TIMESTAMP_COLUMN  # noqa: E402
from harpia_parser.core.pipeline import run_pipeline_document  # noqa: E402
from harpia_parser.core.scope import classify_document  # noqa: E402
from harpia_parser.formatting.output_writer import salvar  # noqa: E402


DEFAULT_INPUT_DIRS = [
    Path(r"L:\Secure_DCS\BRBLH1PINFW001\COE_Digital\others\harpia_rd"),
    Path(r"L:\Secure_DCS\BRBLH1PINFW001\COE_Digital\others\lumen"),
]
log = logging.getLogger(__name__)


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


def _list_pdfs(input_dirs: list[Path]) -> list[Path]:
    pdfs: dict[str, Path] = {}
    for input_dir in input_dirs:
        if not input_dir.exists():
            raise FileNotFoundError(f"Pasta de entrada nao encontrada: {input_dir}")
        for pdf in input_dir.rglob("*.pdf"):
            pdfs[str(pdf)] = pdf
    return sorted(pdfs.values(), key=lambda path: str(path).lower())


def _read_pdf_text(pdf_path: Path, max_pages: int | None = None) -> str:
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        for page in pages:
            texts.append(page.extract_text() or "")
    return "\n".join(texts)


def classify_batch(input_dirs: list[Path], output_path: Path, max_pages: int | None = 3) -> None:
    config = load_config(ROOT)
    rows = []
    pdfs = _list_pdfs(input_dirs)
    extraction_timestamp = _timestamp_text()

    for index, pdf in enumerate(pdfs, start=1):
        log.info("[%d/%d] Classificando %s", index, len(pdfs), pdf.name)
        try:
            texto = _read_pdf_text(pdf, max_pages=max_pages)
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


def extract_batch(input_dirs: list[Path], output_dir: Path) -> None:
    config = load_config(ROOT)
    all_results: dict[str, list[pd.DataFrame]] = {}
    all_samples: dict[str, list[pd.DataFrame]] = {}
    all_clients: dict[str, list[pd.DataFrame]] = {}
    all_packaging_preservatives: dict[str, list[pd.DataFrame]] = {}
    all_notes: dict[str, list[pd.DataFrame]] = {}
    all_general_considerations: dict[str, list[pd.DataFrame]] = {}
    all_conformity_statement: dict[str, list[pd.DataFrame]] = {}
    all_validation_key: dict[str, list[pd.DataFrame]] = {}
    all_audits: dict[str, list[pd.DataFrame]] = {}
    all_table_audits: dict[str, list[pd.DataFrame]] = {}
    all_duplicate_candidates = {}
    extracted_documents: dict[str, list[dict]] = {}
    summary = []
    pdfs = _list_pdfs(input_dirs)
    extraction_timestamp = _timestamp_text()

    for index, pdf in enumerate(pdfs, start=1):
        log.info("[%d/%d] Extraindo %s", index, len(pdfs), pdf.name)
        try:
            (
                df,
                sample_df,
                client_df,
                packaging_preservatives_df,
                notes_df,
                general_considerations_df,
                conformity_statement_df,
                validation_key_df,
                audit_df,
                table_audit_df,
            ) = run_pipeline_document(pdf, config)
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
                continue

            text_for_duplicate = _read_pdf_text(pdf)
            duplicate_candidate = build_duplicate_candidate(pdf, text_for_duplicate, df, sample_df)

            all_duplicate_candidates.setdefault(tipo_laudo, []).append(duplicate_candidate)
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
            }
            summary.append(summary_row)
            extracted_documents.setdefault(tipo_laudo, []).append({
                "caminho": str(pdf),
                "results": df,
                "sample": sample_df,
                "client": client_df,
                "packaging_preservatives": packaging_preservatives_df,
                "notes": notes_df,
                "general_considerations": general_considerations_df,
                "conformity_statement": conformity_statement_df,
                "validation_key": validation_key_df,
                "classification_audit": audit_df,
                "table_extraction_audit": table_audit_df,
                "summary": summary_row,
            })
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

    output_dir.mkdir(parents=True, exist_ok=True)
    duplicate_audits_by_theme: dict[str, pd.DataFrame] = {}
    for tipo_laudo, documents in extracted_documents.items():
        candidates = all_duplicate_candidates.get(tipo_laudo, [])
        duplicate_audit_df = build_duplicate_audit(candidates)
        duplicate_audits_by_theme[tipo_laudo] = duplicate_audit_df
        skipped_paths = duplicate_paths_to_skip(candidates)

        for document in documents:
            summary_row = document["summary"]
            if document["caminho"] in skipped_paths:
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
                ]:
                    summary_row[column] = 0
                continue

            all_results.setdefault(tipo_laudo, []).append(document["results"])
            all_samples.setdefault(tipo_laudo, []).append(document["sample"])
            all_clients.setdefault(tipo_laudo, []).append(document["client"])
            all_packaging_preservatives.setdefault(tipo_laudo, []).append(document["packaging_preservatives"])
            all_notes.setdefault(tipo_laudo, []).append(document["notes"])
            all_general_considerations.setdefault(tipo_laudo, []).append(document["general_considerations"])
            all_conformity_statement.setdefault(tipo_laudo, []).append(document["conformity_statement"])
            all_validation_key.setdefault(tipo_laudo, []).append(document["validation_key"])
            all_audits.setdefault(tipo_laudo, []).append(document["classification_audit"])
            all_table_audits.setdefault(tipo_laudo, []).append(document["table_extraction_audit"])

    for tipo_laudo in sorted(
        set(extracted_documents)
    ):
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
        audit_df = pd.concat(all_audits.get(tipo_laudo, []), ignore_index=True) if all_audits.get(tipo_laudo) else pd.DataFrame()
        table_audit_df = pd.concat(all_table_audits.get(tipo_laudo, []), ignore_index=True) if all_table_audits.get(tipo_laudo) else pd.DataFrame()
        duplicate_audit_df = duplicate_audits_by_theme.get(tipo_laudo, pd.DataFrame())

        template_id = _winner_template_id(audit_df)
        output_tabs = output_tabs_for_template(config, template_id) if template_id else None
        salvar(
            results_df,
            output_dir / tipo_laudo / "extracted_data.xlsx",
            sample_df=sample_df,
            client_df=client_df,
            output_tabs=output_tabs,
            classification_audit_df=audit_df,
            table_extraction_audit_df=table_audit_df,
            duplicate_audit_df=duplicate_audit_df,
            packaging_preservatives_df=packaging_preservatives_df,
            notes_df=notes_df,
            general_considerations_df=general_considerations_df,
            conformity_statement_df=conformity_statement_df,
            validation_key_df=validation_key_df,
        )

    summary_df = pd.DataFrame(summary)
    summary_path = output_dir / "batch_extraction_summary.xlsx"
    summary_df.to_excel(summary_path, index=False)
    log.info("Resumo salvo em: %s", summary_path)
    if not summary_df.empty:
        log.info("Status:\n%s", summary_df["status"].value_counts(dropna=False).to_string())


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
        default=3,
        help="Numero de paginas lidas por PDF no modo classify. Use 0 para ler todas.",
    )
    args = parser.parse_args(argv)

    if args.mode == "classify":
        max_pages = args.classify_pages if args.classify_pages > 0 else None
        classify_batch(args.input, args.output / "template_classification_audit.xlsx", max_pages=max_pages)
    else:
        extract_batch(args.input, args.output)
    return 0


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


if __name__ == "__main__":
    sys.exit(main())
