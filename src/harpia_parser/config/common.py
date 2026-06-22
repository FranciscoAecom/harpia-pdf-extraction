import re
import unicodedata
from typing import Any

import pandas as pd


EMPTY_MARKERS = {
    "",
    "na",
    "nan",
    "none",
    "nao_aplicavel",
    "nao_se_aplica",
    "nao_aplica",
}


def bool_value(value: Any, *, default: bool = True) -> bool:
    if pd.isna(value):
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "verdadeiro", "sim", "yes", "1"}:
        return True
    if text in {"false", "falso", "nao", "não", "nÃ£o", "no", "0"}:
        return False
    return bool(value)


def normalize_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def is_empty_marker(value: Any) -> bool:
    if pd.isna(value):
        return True
    raw_text = str(value).strip()
    if raw_text == "":
        return True
    token = normalize_token(value)
    return bool(token) and token in EMPTY_MARKERS


def cell_or_none(value: Any) -> Any:
    return None if is_empty_marker(value) else value


def value_or_none(row: pd.Series, column: str) -> Any:
    value = row[column] if column in row.index else None
    return cell_or_none(value)


def parse_attrs(value: Any) -> dict[str, str]:
    if is_empty_marker(value):
        return {}

    attrs: dict[str, str] = {}
    for part in str(value).split(";"):
        if "=" not in part:
            continue
        key, attr_value = part.split("=", 1)
        key = normalize_token(key)
        if key:
            attrs[key] = attr_value.strip()
    return attrs


def parse_weight(value: Any) -> float:
    attrs = parse_attrs(value)
    raw_weight = attrs.get("peso", value)
    if is_empty_marker(raw_weight):
        return 0.0
    match = re.search(r"-?\d+(?:[,.]\d+)?", str(raw_weight))
    return float(match.group(0).replace(",", ".")) if match else 0.0


def normalize_tipo_registro(value: Any) -> str | None:
    if is_empty_marker(value):
        return None
    token = normalize_token(value)
    mapping = {
        "amostra": "AMOSTRA",
        "branco": "BRANCO",
        "duplicata": "DUPLICATA",
        "recuperacao": "RECUPERACAO",
    }
    return mapping.get(token, str(value).strip().upper())
