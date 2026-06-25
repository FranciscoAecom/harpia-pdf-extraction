import re
from typing import Any, Pattern

import pandas as pd

from ..config.common import value_or_none
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
        rules.setdefault(campo, []).append(re.compile(str(regex), re.IGNORECASE | re.DOTALL))
    return rules


def extract_document_section(
    paginas: list[tuple[str, list[list[list[Any]]]]],
    context: DocumentContext,
    metadata: dict,
    rules_df: pd.DataFrame,
    *,
    columns: list[str],
) -> pd.DataFrame:
    rules = _compile_rules(rules_df)
    if not rules:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for page_number, (page_text, _) in enumerate(paginas, start=1):
        text = page_text or ""
        for field, patterns in rules.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    value = match.group(1) if match.lastindex else match.group(0)
                    cleaned = _clean_text(value)
                    if not cleaned:
                        continue
                    if field == "chave_validacao" and _invalid_validation_key(cleaned):
                        continue
                    identity = (field, cleaned)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    rows.append({
                        "nome_do_arquivo": context.nome_do_arquivo,
                        "id_taxonomia": context.id_taxonomia,
                        "nome_taxonomia": context.nome_taxonomia,
                        "versao": context.versao,
                        "id_amostra": metadata.get("id_amostra"),
                        "pagina": page_number,
                        field: cleaned,
                    })

    return pd.DataFrame(rows, columns=columns)


def _invalid_validation_key(value: str) -> bool:
    return bool(re.fullmatch(r"FO-ANL-\d+", value.strip(), flags=re.IGNORECASE))
