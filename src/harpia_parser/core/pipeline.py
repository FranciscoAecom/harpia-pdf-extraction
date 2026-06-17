import argparse
import logging
import re
import sys
from pathlib import Path

import pandas as pd

from ..config.loader import filter_config_for_template, load_config, output_sheets_for_template
from ..constants import CLIENT_COLUMNS, RESULTS_EXTRACT_COLUMNS, SAMPLE_COLUMNS
from .context import DocumentContext
from ..formatting.common import format_results_extract
from ..extraction.metadata_extractor import extract_client, extract_metadata, extract_sample, relatorio_from_text
from ..normalization import normalize_outputs
from ..formatting.output_writer import salvar
from ..extraction.pdf_reader import read_pdf
from ..extraction.row_parser import processar_linha
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


def _default_output_path(base_dir: Path, df: pd.DataFrame, sample_df: pd.DataFrame, client_df: pd.DataFrame) -> Path:
    tipo_laudo = _first_nonempty_value([df, sample_df, client_df], "tipo_laudo") or "sem_tema"
    return base_dir / "output" / tipo_laudo / "extracted_data.xlsx"


def _empty_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        pd.DataFrame(columns=RESULTS_EXTRACT_COLUMNS),
        pd.DataFrame(columns=SAMPLE_COLUMNS),
        pd.DataFrame(columns=CLIENT_COLUMNS),
        pd.DataFrame(),
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
        classification=classification,
    )


def _extract_header_tables(texto: str, context: DocumentContext, extraction_config):
    metadata = extract_metadata(texto, extraction_config)
    client_df = extract_client(texto, metadata, extraction_config)
    sample_df = extract_sample(texto, metadata, extraction_config)
    client_df["nome_do_arquivo"] = context.nome_do_arquivo
    client_df["template_id"] = context.template_id
    client_df["tipo_laudo"] = context.tipo_laudo
    sample_df["nome_do_arquivo"] = context.nome_do_arquivo
    sample_df["template_id"] = context.template_id
    sample_df["tipo_laudo"] = context.tipo_laudo
    return metadata, sample_df, client_df


def _extract_result_rows(paginas, metadata: dict, sample_df: pd.DataFrame, context: DocumentContext, extraction_config):
    resultados = []
    estado = novo_estado()
    subcategoria_relatorio_atual = None
    dh_inicio_atividade = sample_df.loc[0, "dh_inicio_atividade"]
    pending_estado = None

    for page_text, tabelas in paginas:
        subcategoria_pagina = relatorio_from_text(page_text)
        subcategoria_relatorio_atual = subcategoria_pagina or subcategoria_relatorio_atual

        if pending_estado:
            estado.update(pending_estado)

        for tabela in tabelas:
            if not tabela:
                continue

            first_row_text = " ".join(str(c) for c in tabela[0] if c)
            rows = tabela[1:] if aplicar_section_pdf(first_row_text, estado, extraction_config) else tabela
            is_qaqc_continuacao = inferir_qaqc_continuacao(rows, estado, extraction_config)

            if not estado.get("categoria") or (not is_qaqc_continuacao and not tabela_resultado(rows, estado)):
                continue

            for row in rows:
                txt = " ".join(str(c) for c in row if c)
                if aplicar_section_pdf(txt, estado, extraction_config):
                    continue

                dado = processar_linha(row, estado, extraction_config)
                if not dado:
                    continue

                if pd.isna(dh_inicio_atividade) and len(row) > 2:
                    data_inicio = re.search(r"\b\d{2}/\d{2}/\d{4}\b", str(row[2] or ""))
                    if data_inicio:
                        dh_inicio_atividade = data_inicio.group(0)

                dado["subcategoria"] = subcategoria_relatorio_atual
                resultados.append({
                    "nome_do_arquivo": context.nome_do_arquivo,
                    "template_id": context.template_id,
                    "tipo_laudo": context.tipo_laudo,
                    "id_amostra": metadata.get("id_amostra"),
                    **dado,
                })

        pending_estado = pending_section_from_page_text(page_text, extraction_config)

    return pd.DataFrame(resultados), dh_inicio_atividade


def run_pipeline_document(pdf_path, config=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pdf_path = Path(pdf_path)
    config = config or load_config(PROJECT_ROOT)
    log.info("Processando: %s", pdf_path)

    texto, paginas = read_pdf(pdf_path)
    context = _build_context(pdf_path, texto, config)
    if not context:
        log.info("PDF fora do escopo da taxonomy: %s", pdf_path.name)
        return _empty_outputs()

    log.info("Template identificado: %s (%s)", context.template_id, context.tipo_laudo)
    extraction_config = filter_config_for_template(config, context.template_id)
    metadata, sample_df, client_df = _extract_header_tables(texto, context, extraction_config)
    raw_results_df, dh_inicio_atividade = _extract_result_rows(
        paginas,
        metadata,
        sample_df,
        context,
        extraction_config,
    )

    df = format_results_extract(raw_results_df, extraction_config, context)
    if pd.notna(dh_inicio_atividade):
        sample_df.loc[0, "dh_inicio_atividade"] = dh_inicio_atividade
    sample_df = sample_df.reindex(columns=SAMPLE_COLUMNS)
    client_df = client_df.reindex(columns=CLIENT_COLUMNS)
    df, sample_df, client_df = normalize_outputs(df, sample_df, client_df, context)
    classification_audit_df = context.classification.to_dataframe(context.nome_do_arquivo)

    log.info("Pipeline concluido: %d registros extraidos de %s", len(df), pdf_path.name)
    return df, sample_df, client_df, classification_audit_df


def run_pipeline(pdf_path) -> pd.DataFrame:
    df, _, _, _ = run_pipeline_document(pdf_path)
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
    df, sample_df, client_df, classification_audit_df = run_pipeline_document(pdf_path, config)
    if df.empty and sample_df.empty and client_df.empty:
        log.warning("Nenhum dado extraido. Verifique o PDF e as regras da taxonomy.")
        return 0

    template_id = _first_nonempty_value([df, sample_df, client_df], "template_id")
    output_sheets = output_sheets_for_template(config, template_id) if template_id else None
    output_path = Path(args.output) if args.output else _default_output_path(PROJECT_ROOT, df, sample_df, client_df)
    salvar(df, output_path, sample_df, client_df, output_sheets, classification_audit_df)
    log.info("Resultado salvo em: %s  (%d registros)", output_path, len(df))
    if not df.empty:
        _print_dataframe(df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
