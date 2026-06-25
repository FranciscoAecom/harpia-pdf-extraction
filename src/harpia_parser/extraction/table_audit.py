from __future__ import annotations

from typing import Any
import re

from .header_aliases import field_from_header_cell
from .section_classifier import linha_header
from ..constants import LAYOUT_FIELD_KEYS
from ..utils import normalizar


FIELD_OUTPUT_NAMES = {
    "resultado_col": "resultado",
    "unidade_col": "acm_unidade",
    "data_inicio_col": "data_inicio",
    "conama_col": "conama",
    "copam_cerh_col": "copam_cerh",
    "ld_col": "ld",
    "lq_col": "lq",
    "referencia_col": "referencia",
    "incerteza_col": "incerteza",
    "numero_cq_col": "numero_cq",
    "duplicata_col": "duplicata",
    "faixa_aceitacao_col": "faixa_aceitacao",
    "variacao_percentual_col": "variacao_percentual",
    "quantidade_adicionada_col": "quantidade_adicionada",
    "recuperacao_percentual_col": "recuperacao_percentual",
}

PAGE_HEADER_PATTERNS = {
    "parameter": re.compile(r"\b(analise|parametros?)\b", re.IGNORECASE),
    "resultado": re.compile(r"\bresultados?\b", re.IGNORECASE),
    "unidade": re.compile(r"\b(unidade|unid)\b", re.IGNORECASE),
    "acm_unidade": re.compile(r"\b(unidade|unid)\b", re.IGNORECASE),
    "data_inicio": re.compile(r"data\s+(de\s+)?inicio", re.IGNORECASE),
    "conama": re.compile(r"conama", re.IGNORECASE),
    "copam_cerh": re.compile(r"copam|cerh|deliberacao\s+normativa", re.IGNORECASE),
    "ld": re.compile(r"(^|\s)ld($|\s)|limite\s+de\s+deteccao", re.IGNORECASE),
    "lq": re.compile(r"(^|\s)lq($|\s)|limite\s+de\s+quantificacao", re.IGNORECASE),
    "referencia": re.compile(r"referencia", re.IGNORECASE),
    "incerteza": re.compile(r"incerteza", re.IGNORECASE),
    "numero_cq": re.compile(r"numero\s+do\s+cq|(^|\s)cq($|\s)", re.IGNORECASE),
    "duplicata": re.compile(r"duplicata", re.IGNORECASE),
    "faixa_aceitacao": re.compile(r"faixa\s+de\s+aceitacao", re.IGNORECASE),
    "variacao_percentual": re.compile(r"variacao", re.IGNORECASE),
    "quantidade_adicionada": re.compile(r"quantidade\s+adicionada|qtd\s+adicionada", re.IGNORECASE),
    "recuperacao_percentual": re.compile(r"recuperacao", re.IGNORECASE),
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


def _fields_from_page_header_text(text: str, expected: list[str]) -> list[str]:
    normalized_text = normalizar(text)
    found_with_position = []
    for field in expected:
        pattern = PAGE_HEADER_PATTERNS.get(field)
        if not pattern:
            continue
        match = pattern.search(normalized_text)
        if match:
            found_with_position.append((match.start(), field))
    found_with_position.sort()
    found = []
    for _, field in found_with_position:
        if field not in found:
            found.append(field)
    return found


def _detect_page_header_context(page_text: str | None, expected: list[str]) -> tuple[str | None, list[str]]:
    if not page_text:
        return None, []

    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    candidates: list[tuple[str, list[str]]] = []
    for start in range(len(lines)):
        for size in range(1, 5):
            chunk = " ".join(lines[start:start + size])
            if not chunk:
                continue
            fields = _fields_from_page_header_text(chunk, expected)
            if "parameter" in fields and len(fields) >= 3:
                candidates.append((chunk, fields))

    if not candidates:
        return None, []

    candidates.sort(key=lambda item: (-len(item[1]), len(item[0])))
    return candidates[0]


def _positions_from_layout(layout: dict[str, int | None]) -> dict[str, int]:
    positions: dict[str, int] = {}
    for key in LAYOUT_FIELD_KEYS:
        value = layout.get(key)
        if value is None:
            continue
        positions[_field_output_name(key)] = int(value)
    positions["parameter"] = 0
    return positions


def _layout_positions(
    tipo_registro: str | None,
    config,
    estado: dict[str, Any] | None = None,
    page_header_fields: list[str] | None = None,
) -> dict[str, int]:
    if page_header_fields and "parameter" in page_header_fields and "resultado" in page_header_fields:
        return {field: index for index, field in enumerate(page_header_fields)}

    if estado and estado.get("layout_override_tipo") == tipo_registro:
        layout_override = estado.get("layout_override") or {}
        if layout_override:
            return _positions_from_layout(layout_override)

    layout = config.table_layouts.get(tipo_registro) or config.table_layouts.get("AMOSTRA") or {}
    return _positions_from_layout(layout)


def _expected_from_positions(positions: dict[str, int]) -> list[str]:
    ordered = sorted(positions.items(), key=lambda item: item[1])
    return [field for field, _ in ordered]


def _layout_confidence(
    rows: list[list[Any]],
    tipo_registro: str | None,
    expected: list[str],
    config,
    estado: dict[str, Any] | None = None,
    page_header_fields: list[str] | None = None,
) -> tuple[bool, str, dict[str, int]]:
    positions = _layout_positions(tipo_registro, config, estado, page_header_fields)
    expected_positions = [positions[field] for field in expected if field in positions]
    if not expected_positions:
        return False, "Layout sem posicoes cadastradas para os campos esperados.", positions

    max_position = max(expected_positions)
    data_rows = [row for row in rows if any(_clean_cell(value) for value in row)]
    if not data_rows:
        return False, "Tabela sem linhas de dados avaliaveis.", positions

    rows_with_enough_columns = sum(1 for row in data_rows if len(row) > max_position)
    result_position = positions.get("resultado")
    rows_with_result_value = 0
    if result_position is not None:
        for row in data_rows:
            value = row[result_position] if len(row) > result_position else None
            if re.search(r"(^[<>]=?|[+-]?\d)", str(value or "")):
                rows_with_result_value += 1

    enough_columns_ratio = rows_with_enough_columns / len(data_rows)
    result_value_ratio = rows_with_result_value / len(data_rows) if result_position is not None else 1
    is_confident = enough_columns_ratio >= 0.8 and result_value_ratio >= 0.8
    detail = (
        f"Compatibilidade do layout: {rows_with_enough_columns}/{len(data_rows)} linhas com colunas suficientes"
        f"; {rows_with_result_value}/{len(data_rows)} linhas com valor na coluna de resultado."
    )
    return is_confident, detail, positions


def build_table_audit_row(
    *,
    context,
    page_number: int,
    table_index: int,
    rows: list[list[Any]],
    estado: dict[str, Any],
    config,
    is_qaqc_continuacao: bool,
    page_text: str | None = None,
) -> dict[str, Any]:
    tipo_registro = estado.get("tipo_registro")
    header_index, header = _detect_header(rows)
    expected = _expected_fields(tipo_registro, config)

    if header is None:
        page_header_text, page_header_fields = _detect_page_header_context(page_text, expected)
        layout_is_confident, layout_detail, positions = _layout_confidence(
            rows,
            tipo_registro,
            page_header_fields or expected,
            config,
            estado,
            page_header_fields,
        )
        effective_expected = page_header_fields or _expected_from_positions(positions) or expected

        if page_header_text and layout_is_confident:
            status = "fallback_cabecalho_texto_layout_confiavel"
        elif page_header_text:
            status = "fallback_cabecalho_texto_layout_incompleto"
        elif layout_is_confident:
            status = "fallback_layout_confiavel"
        else:
            status = "fallback"

        observations = ["Tabela processada sem cabecalho detectado na malha extraida pelo PDF."]
        if page_header_text:
            observations.append(f"Cabecalho contextual encontrado no texto da pagina: {_clean_cell(page_header_text)}.")
            observations.append(f"Campos encontrados no texto da pagina: {_join(page_header_fields)}.")
        observations.append(layout_detail)
        observations.append("Foi usado o layout cadastrado na taxonomia.")
        return {
            "nome_do_arquivo": context.nome_do_arquivo,
            "id_taxonomia": context.id_taxonomia,
            "nome_taxonomia": context.nome_taxonomia,
            "versao": getattr(context, "versao", None),
            "pagina": page_number,
            "tabela_indice": table_index,
            "categoria": estado.get("categoria"),
            "subcategoria": estado.get("subcategoria"),
            "tipo_registro": tipo_registro,
            "modo_auditoria": "contrato_e_descoberta",
            "cabecalho_detectado": _clean_cell(page_header_text) if page_header_text else None,
            "colunas_detectadas": None,
            "colunas_mapeadas": None,
            "colunas_sem_mapeamento": None,
            "campos_esperados": _join(effective_expected),
            "campos_obrigatorios_ausentes": None,
            "campos_opcionais_ausentes": None,
            "usou_fallback": True,
            "status": status,
            "observacao": " ".join(observations),
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
        "id_taxonomia": context.id_taxonomia,
        "nome_taxonomia": context.nome_taxonomia,
        "versao": getattr(context, "versao", None),
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
