from __future__ import annotations

from typing import Any

from .header_aliases import field_from_header_cell
from .section_classifier import linha_header
from ..constants import LAYOUT_FIELD_KEYS


FIELD_OUTPUT_NAMES = {
    "resultado_col": "resultado",
    "unidade_col": "unidade",
    "data_inicio_col": "data_inicio",
    "criterio_conformidade_col": "criterio_conformidade",
    "ld_col": "ld_original",
    "lq_col": "lq_original",
    "referencia_col": "referencia",
    "incerteza_col": "incerteza_original",
    "numero_cq_col": "numero_cq",
    "duplicata_col": "duplicata",
    "faixa_aceitacao_col": "faixa_aceitacao_original",
    "variacao_percentual_col": "variacao_percentual",
    "quantidade_adicionada_col": "quantidade_adicionada",
    "recuperacao_percentual_col": "recuperacao_percentual",
}


def _field_output_name(field: str) -> str:
    return FIELD_OUTPUT_NAMES.get(field, field)


def _clean_cell(value: object) -> str:
    return " ".join(str(value or "").split())


def _join(values: list[str]) -> str:
    return "; ".join(value for value in values if value)


def _expected_fields(tipo_registro: str | None, config) -> list[str]:
    layout = config.table_layouts.get(tipo_registro) or config.table_layouts.get("AMOSTRA") or {}
    expected = ["parameter"]
    for key in LAYOUT_FIELD_KEYS:
        if layout.get(key) is not None:
            expected.append(_field_output_name(key))
    return expected


def _detect_header(rows: list[list[Any]]) -> tuple[int | None, list[Any] | None]:
    for index, row in enumerate(rows[:3]):
        if linha_header(row):
            return index, row
    return None, None


def build_table_audit_row(
    *,
    context,
    page_number: int,
    table_index: int,
    rows: list[list[Any]],
    estado: dict[str, Any],
    config,
    is_qaqc_continuacao: bool,
) -> dict[str, Any]:
    tipo_registro = estado.get("tipo_registro")
    header_index, header = _detect_header(rows)
    expected = _expected_fields(tipo_registro, config)

    if header is None:
        status = "fallback"
        observacao = "Tabela processada sem cabecalho detectado; usado layout cadastrado na taxonomia."
        return {
            "nome_do_arquivo": context.nome_do_arquivo,
            "template_id": context.template_id,
            "tipo_laudo": context.tipo_laudo,
            "pagina": page_number,
            "tabela_indice": table_index,
            "categoria": estado.get("categoria"),
            "subcategoria": estado.get("subcategoria"),
            "tipo_registro": tipo_registro,
            "modo_auditoria": "contrato_e_descoberta",
            "cabecalho_detectado": None,
            "colunas_detectadas": None,
            "colunas_mapeadas": None,
            "colunas_sem_mapeamento": None,
            "campos_esperados": _join(expected),
            "campos_obrigatorios_ausentes": None,
            "campos_opcionais_ausentes": None,
            "usou_fallback": True,
            "status": status,
            "observacao": observacao,
        }

    detected_columns = [_clean_cell(value) for value in header if _clean_cell(value)]
    mapped_columns: list[str] = []
    unmapped_columns: list[str] = []
    mapped_fields: list[str] = ["parameter"]

    for value in header:
        column_name = _clean_cell(value)
        if not column_name:
            continue
        field = field_from_header_cell(value, config, include_parameter=True)
        if field is None:
            unmapped_columns.append(column_name)
            continue
        output_field = _field_output_name(field)
        mapped_columns.append(f"{column_name} -> {output_field}")
        if output_field not in mapped_fields:
            mapped_fields.append(output_field)

    expected_absent = [field for field in expected if field not in mapped_fields]
    if unmapped_columns and expected_absent:
        status = "alerta_descoberta_com_opcional_ausente"
    elif unmapped_columns:
        status = "alerta_descoberta"
    elif expected_absent:
        status = "ok_com_opcional_ausente"
    else:
        status = "ok"

    observations = []
    if expected_absent:
        observations.append(f"Campos esperados ausentes no cabecalho: {_join(expected_absent)}.")
    if unmapped_columns:
        observations.append(f"Colunas sem mapeamento: {_join(unmapped_columns)}.")
    if is_qaqc_continuacao:
        observations.append("Tabela reconhecida como continuacao de QA/QC.")

    return {
        "nome_do_arquivo": context.nome_do_arquivo,
        "template_id": context.template_id,
        "tipo_laudo": context.tipo_laudo,
        "pagina": page_number,
        "tabela_indice": table_index,
        "categoria": estado.get("categoria"),
        "subcategoria": estado.get("subcategoria"),
        "tipo_registro": tipo_registro,
        "modo_auditoria": "contrato_e_descoberta",
        "cabecalho_detectado": " | ".join(detected_columns),
        "colunas_detectadas": _join(detected_columns),
        "colunas_mapeadas": _join(mapped_columns),
        "colunas_sem_mapeamento": _join(unmapped_columns),
        "campos_esperados": _join(expected),
        "campos_obrigatorios_ausentes": None,
        "campos_opcionais_ausentes": _join(expected_absent),
        "usou_fallback": False,
        "status": status,
        "observacao": " ".join(observations) or None,
    }
