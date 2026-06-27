import re
from typing import Any, Pattern

import pandas as pd

from ..config.common import value_or_none
from ..constants import PACKAGING_PRESERVATIVES_COLUMNS
from ..core.context import DocumentContext


def _clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()
    return text or None


def _compile_rules(rules_df: pd.DataFrame) -> dict[str, list[Pattern[str]]]:
    rules: dict[str, list[Pattern[str]]] = {}
    if rules_df.empty:
        return rules

    for _, row in rules_df.iterrows():
        campo = str(value_or_none(row, "campo") or "").strip()
        regex = value_or_none(row, "regex")
        if not campo or regex is None:
            continue
        rules.setdefault(campo, []).append(re.compile(str(regex), re.IGNORECASE))
    return rules


def _matches_any(patterns: list[Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _joined_row(row: list[Any]) -> str:
    return " ".join(str(cell) for cell in row if _clean_text(cell))


def _find_header_index(table: list[list[Any]], header_patterns: list[Pattern[str]]) -> int | None:
    for index, row in enumerate(table):
        row_text = _joined_row(row)
        if _matches_any(header_patterns, row_text):
            return index
    return None


def _sample_identification(table: list[list[Any]], header_index: int, sample_patterns: list[Pattern[str]]) -> str | None:
    candidate_rows = table[max(0, header_index - 2):header_index]
    for row in reversed(candidate_rows):
        text = _joined_row(row)
        if not text:
            continue
        if not sample_patterns or _matches_any(sample_patterns, text):
            return _clean_text(text)
    return None


def _sample_identification_from_text(text: str, sample_patterns: list[Pattern[str]]) -> str | None:
    for line in (text or "").splitlines():
        cleaned = _clean_text(line)
        if cleaned and (not sample_patterns or _matches_any(sample_patterns, cleaned)):
            return cleaned
    return None


def _sample_id(identificacao_amostra: str | None) -> str | None:
    if not identificacao_amostra:
        return None
    match = re.search(r"\b(\d+)\b", identificacao_amostra)
    return match.group(1) if match else None


def _data_rows(table: list[list[Any]], header_index: int) -> list[list[Any]]:
    rows = []
    for row in table[header_index + 1:]:
        padded = list(row[:4]) + [None] * max(0, 4 - len(row))
        if not any(_clean_text(cell) for cell in padded[:4]):
            continue
        rows.append(padded[:4])
    return rows


def extract_packaging_preservatives(
    paginas: list[tuple[str, list[list[list[Any]]]]],
    context: DocumentContext,
    extraction_config,
) -> pd.DataFrame:
    rules = _compile_rules(extraction_config.df_packaging_preservatives_rules)
    section_patterns = rules.get("section_start", [])
    header_patterns = rules.get("table_header", [])
    sample_patterns = rules.get("sample_identification", [])
    if not section_patterns or not header_patterns:
        return pd.DataFrame(columns=PACKAGING_PRESERVATIVES_COLUMNS)

    output_rows: list[dict[str, Any]] = []
    carry_section_to_next_page = False
    carried_identification: str | None = None
    for page_text, tables in paginas:
        page_has_section = _matches_any(section_patterns, page_text or "")
        section_is_active = page_has_section or carry_section_to_next_page
        page_identification = _sample_identification_from_text(page_text or "", sample_patterns)
        if page_has_section and page_identification:
            carried_identification = page_identification
        header_is_in_page_text = _matches_any(header_patterns, page_text or "")
        extracted_on_page = False
        for table in tables:
            if not table:
                continue

            table_text = " ".join(_joined_row(row) for row in table)
            if not section_is_active and not _matches_any(section_patterns, table_text):
                continue

            header_index = _find_header_index(table, header_patterns)
            if header_index is None and section_is_active and header_is_in_page_text:
                header_index = -1
            if header_index is None:
                continue

            identificacao_amostra = (
                _sample_identification(table, header_index, sample_patterns)
                if header_index >= 0
                else None
            ) or page_identification or carried_identification
            id_amostra = _sample_id(identificacao_amostra)
            for embalagem, volume, preservacao, metodos in _data_rows(table, header_index):
                extracted_on_page = True
                output_rows.append({
                    "nome_do_arquivo": context.nome_do_arquivo,
                    "id_taxonomia": context.id_taxonomia,
                    "nome_taxonomia": context.nome_taxonomia,
                    "versao_template": context.versao_template,
                    "id_amostra": id_amostra,
                    "identificacao_amostra": identificacao_amostra,
                    "embalagem": _clean_text(embalagem),
                    "volume": _clean_text(volume),
                    "preservacao": _clean_text(preservacao),
                    "metodos": _clean_text(metodos),
                })
        carry_section_to_next_page = page_has_section and not extracted_on_page
        if extracted_on_page:
            carried_identification = None

    return pd.DataFrame(output_rows, columns=PACKAGING_PRESERVATIVES_COLUMNS)
