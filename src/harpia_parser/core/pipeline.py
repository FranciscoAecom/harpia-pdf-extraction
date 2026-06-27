import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from ..config.loader import filter_config_for_template, load_config, output_tabs_for_template
from ..constants import (
    CLIENT_COLUMNS,
    CONFORMITY_STATEMENT_COLUMNS,
    FIELD_EXTRACTION_AUDIT_COLUMNS,
    GENERAL_CONSIDERATIONS_COLUMNS,
    NOTES_COLUMNS,
    PACKAGING_PRESERVATIVES_COLUMNS,
    RESULTS_EXTRACT_COLUMNS,
    SAMPLE_COLUMNS,
    SECTION_EXTRACTION_AUDIT_COLUMNS,
    TABLE_EXTRACTION_AUDIT_COLUMNS,
    VALIDATION_KEY_COLUMNS,
)
from .context import DocumentContext
from ..formatting.common import format_results_extract
from ..extraction.metadata_extractor import codigo_laudo_from_text, extract_client, extract_metadata, extract_sample
from ..extraction.document_sections import extract_document_section
from ..extraction.field_audit import build_field_extraction_audit
from ..extraction.packaging_preservatives import extract_packaging_preservatives
from ..extraction.section_audit import build_section_extraction_audit
from ..normalization import normalize_outputs
from ..formatting.output_writer import salvar
from ..extraction.pdf_reader import read_pdf
from ..extraction.row_parser import processar_linha
from ..extraction.table_audit import build_table_audit_row
from .scope import classify_document
from ..extraction.section_classifier import (
    aplicar_section_pdf,
    inferir_qaqc_continuacao,
    novo_estado,
    pending_section_from_page_text,
    tabela_resultado,
)


log = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _print_dataframe(df: pd.DataFrame) -> None:
    output = df.to_string(index=False)
    try:
        print(output)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe_output = output.encode(encoding, errors="replace").decode(encoding)
        print(safe_output)


def _first_nonempty_value(dataframes: list[pd.DataFrame], column: str) -> str | None:
    for dataframe in dataframes:
        if column in dataframe.columns and not dataframe.empty:
            value = dataframe[column].dropna()
            if not value.empty:
                return str(value.iloc[0])
    return None


def _winner_template_id(classification_audit_df: pd.DataFrame) -> str | None:
    if classification_audit_df.empty or "template_avaliado" not in classification_audit_df.columns:
        return None
    if "status" in classification_audit_df.columns:
        winners = classification_audit_df[
            classification_audit_df["status"].astype(str) == "winner"
        ]["template_avaliado"].dropna()
        if not winners.empty:
            return str(winners.iloc[0])
    values = classification_audit_df["template_avaliado"].dropna()
    return str(values.iloc[0]) if not values.empty else None


def _default_output_path(base_dir: Path, df: pd.DataFrame, sample_df: pd.DataFrame, client_df: pd.DataFrame) -> Path:
    tipo_laudo = _first_nonempty_value([df, sample_df, client_df], "tipo_laudo")
    nome_taxonomia = _first_nonempty_value([df, sample_df, client_df], "nome_taxonomia")
    output_group = tipo_laudo or (nome_taxonomia.lower().replace(" ", "_") if nome_taxonomia else "sem_tema")
    return base_dir / "output" / output_group / "extracted_data.xlsx"


def _empty_outputs() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    return (
        pd.DataFrame(columns=RESULTS_EXTRACT_COLUMNS),
        pd.DataFrame(columns=SAMPLE_COLUMNS),
        pd.DataFrame(columns=CLIENT_COLUMNS),
        pd.DataFrame(columns=PACKAGING_PRESERVATIVES_COLUMNS),
        pd.DataFrame(columns=NOTES_COLUMNS),
        pd.DataFrame(columns=GENERAL_CONSIDERATIONS_COLUMNS),
        pd.DataFrame(columns=CONFORMITY_STATEMENT_COLUMNS),
        pd.DataFrame(columns=VALIDATION_KEY_COLUMNS),
        pd.DataFrame(),
        pd.DataFrame(columns=TABLE_EXTRACTION_AUDIT_COLUMNS),
        pd.DataFrame(columns=SECTION_EXTRACTION_AUDIT_COLUMNS),
        pd.DataFrame(columns=FIELD_EXTRACTION_AUDIT_COLUMNS),
    )


def _build_context(pdf_path: Path, texto: str, config) -> DocumentContext | None:
    classification = classify_document(texto, config, pdf_path)
    if not classification.template_id:
        return None

    return DocumentContext(
        pdf_path=pdf_path,
        nome_do_arquivo=pdf_path.name,
        template_id=classification.template_id,
        tipo_laudo=classification.tipo_laudo,
        id_taxonomia=classification.id_taxonomia,
        nome_taxonomia=classification.nome_taxonomia,
        versao_template=classification.versao_template,
        classification=classification,
    )


def _extract_header_tables(texto: str, context: DocumentContext, extraction_config):
    metadata = extract_metadata(texto, extraction_config)
    client_df = extract_client(texto, metadata, extraction_config)
    sample_df = extract_sample(texto, metadata, extraction_config)
    client_df["nome_do_arquivo"] = context.nome_do_arquivo
    client_df["id_taxonomia"] = context.id_taxonomia
    client_df["nome_taxonomia"] = context.nome_taxonomia
    client_df["versao_template"] = context.versao_template
    sample_df["nome_do_arquivo"] = context.nome_do_arquivo
    sample_df["id_taxonomia"] = context.id_taxonomia
    sample_df["nome_taxonomia"] = context.nome_taxonomia
    sample_df["versao_template"] = context.versao_template
    return metadata, sample_df, client_df


def _extract_result_rows(paginas, metadata: dict, sample_df: pd.DataFrame, context: DocumentContext, extraction_config):
    resultados = []
    table_audit_rows = []
    estado = novo_estado()
    pending_estado = None
    codigo_laudo_atual = metadata.get("codigo_laudo")

    for page_number, (page_text, tabelas) in enumerate(paginas, start=1):
        codigo_laudo_atual = codigo_laudo_from_text(page_text or "") or codigo_laudo_atual
        if pending_estado:
            estado.update(pending_estado)

        for table_index, tabela in enumerate(tabelas, start=1):
            if not tabela:
                continue

            first_row_text = " ".join(str(c) for c in tabela[0] if c)
            rows = tabela[1:] if aplicar_section_pdf(first_row_text, estado, extraction_config) else tabela
            is_qaqc_continuacao = inferir_qaqc_continuacao(rows, estado, extraction_config)

            if not estado.get("categoria") or (
                not is_qaqc_continuacao and not tabela_resultado(rows, estado, extraction_config)
            ):
                continue

            table_audit_rows.append(
                build_table_audit_row(
                    context=context,
                    page_number=page_number,
                    table_index=table_index,
                    rows=rows,
                    estado=estado,
                    config=extraction_config,
                    is_qaqc_continuacao=is_qaqc_continuacao,
                    page_text=page_text,
                )
            )

            for row in rows:
                txt = " ".join(str(c) for c in row if c)
                if aplicar_section_pdf(txt, estado, extraction_config):
                    continue

                dado = processar_linha(row, estado, extraction_config)
                if not dado:
                    continue

                resultados.append({
                    "nome_do_arquivo": context.nome_do_arquivo,
                    "id_taxonomia": context.id_taxonomia,
                    "nome_taxonomia": context.nome_taxonomia,
                    "versao_template": context.versao_template,
                    "id_amostra": metadata.get("id_amostra"),
                    "codigo_laudo": codigo_laudo_atual,
                    "codigo_laudo_substituido": sample_df.loc[0, "codigo_laudo_substituido"],
                    **dado,
                })

        pending_estado = pending_section_from_page_text(page_text, extraction_config)

    return pd.DataFrame(resultados), pd.DataFrame(table_audit_rows, columns=TABLE_EXTRACTION_AUDIT_COLUMNS)


def run_pipeline_document(pdf_path, config=None, pdf_content=None) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    pdf_path = Path(pdf_path)
    config = config or load_config(PROJECT_ROOT)
    log.info("Processando: %s", pdf_path)

    texto, paginas = pdf_content if pdf_content is not None else read_pdf(pdf_path)
    context = _build_context(pdf_path, texto, config)
    if not context:
        log.info("PDF fora do escopo da taxonomy: %s", pdf_path.name)
        return _empty_outputs()

    log.info("Template identificado: %s (%s)", context.template_id, context.tipo_laudo)
    extraction_config = filter_config_for_template(config, context.template_id)
    metadata, sample_df, client_df = _extract_header_tables(texto, context, extraction_config)
    raw_results_df, table_audit_df = _extract_result_rows(
        paginas,
        metadata,
        sample_df,
        context,
        extraction_config,
    )
    packaging_preservatives_df = extract_packaging_preservatives(paginas, context, extraction_config)
    notes_df = extract_document_section(
        paginas,
        context,
        metadata,
        extraction_config.df_notes_rules,
        columns=NOTES_COLUMNS,
    )
    general_considerations_df = extract_document_section(
        paginas,
        context,
        metadata,
        extraction_config.df_general_considerations_rules,
        columns=GENERAL_CONSIDERATIONS_COLUMNS,
    )
    conformity_statement_df = extract_document_section(
        paginas,
        context,
        metadata,
        extraction_config.df_conformity_statement_rules,
        columns=CONFORMITY_STATEMENT_COLUMNS,
    )
    validation_key_df = extract_document_section(
        paginas,
        context,
        metadata,
        extraction_config.df_validation_key_rules,
        columns=VALIDATION_KEY_COLUMNS,
    )
    section_audit_df = build_section_extraction_audit(
        paginas,
        context,
        extraction_config,
        {
            "packaging_preservatives": packaging_preservatives_df,
            "notes": notes_df,
            "general_considerations": general_considerations_df,
            "conformity_statement": conformity_statement_df,
            "validation_key": validation_key_df,
        },
        table_audit_df,
    )
    field_audit_df = build_field_extraction_audit(
        paginas,
        context,
        extraction_config,
        metadata,
        sample_df,
        client_df,
    )

    df = format_results_extract(raw_results_df, extraction_config, context)
    sample_df = sample_df.reindex(columns=SAMPLE_COLUMNS)
    client_df = client_df.reindex(columns=CLIENT_COLUMNS)
    packaging_preservatives_df = packaging_preservatives_df.reindex(columns=PACKAGING_PRESERVATIVES_COLUMNS)
    notes_df = notes_df.reindex(columns=NOTES_COLUMNS)
    general_considerations_df = general_considerations_df.reindex(columns=GENERAL_CONSIDERATIONS_COLUMNS)
    conformity_statement_df = conformity_statement_df.reindex(columns=CONFORMITY_STATEMENT_COLUMNS)
    validation_key_df = validation_key_df.reindex(columns=VALIDATION_KEY_COLUMNS)
    df, sample_df, client_df = normalize_outputs(df, sample_df, client_df, context)
    classification_audit_df = context.classification.to_dataframe(context.nome_do_arquivo)

    log.info("Pipeline concluido: %d registros extraidos de %s", len(df), pdf_path.name)
    return (
        df,
        sample_df,
        client_df,
        packaging_preservatives_df,
        notes_df,
        general_considerations_df,
        conformity_statement_df,
        validation_key_df,
        classification_audit_df,
        table_audit_df,
        section_audit_df,
        field_audit_df,
        field_audit_df,
    )


def run_pipeline(pdf_path) -> pd.DataFrame:
    df, *_ = run_pipeline_document(pdf_path)
    return df


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Extrai dados analiticos de um PDF usando a taxonomy configurada."
    )
    parser.add_argument("pdf", help="Caminho do PDF a processar.")
    parser.add_argument(
        "--out",
        dest="output",
        default=None,
        help="Arquivo de saida. Extensao determina o formato: .xlsx, .csv ou .json.",
    )
    args = parser.parse_args(argv)

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        log.error("PDF nao encontrado: %s", pdf_path)
        return 1

    config = load_config(PROJECT_ROOT)
    (
        df,
        sample_df,
        client_df,
        packaging_preservatives_df,
        notes_df,
        general_considerations_df,
        conformity_statement_df,
        validation_key_df,
        classification_audit_df,
        table_audit_df,
        section_audit_df,
    ) = run_pipeline_document(pdf_path, config)
    if df.empty and sample_df.empty and client_df.empty:
        log.warning("Nenhum dado extraido. Verifique o PDF e as regras da taxonomy.")
        return 0

    template_id = _winner_template_id(classification_audit_df)
    output_tabs = output_tabs_for_template(config, template_id) if template_id else None
    output_path = Path(args.output) if args.output else _default_output_path(PROJECT_ROOT, df, sample_df, client_df)
    salvar(
        df,
        output_path,
        sample_df,
        client_df,
        output_tabs,
        classification_audit_df,
        table_audit_df,
        section_extraction_audit_df=section_audit_df,
        field_extraction_audit_df=field_audit_df,
        packaging_preservatives_df=packaging_preservatives_df,
        notes_df=notes_df,
        general_considerations_df=general_considerations_df,
        conformity_statement_df=conformity_statement_df,
        validation_key_df=validation_key_df,
    )
    log.info("Resultado salvo em: %s  (%d registros)", output_path, len(df))
    if not df.empty:
        _print_dataframe(df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
