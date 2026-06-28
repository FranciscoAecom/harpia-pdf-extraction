from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Any

import pandas as pd
import simplejson as json

from ..constants import ACM_EXTRACTION_TIMESTAMP_COLUMN


SOURCE_NUMBER_IN_TEXT = re.compile(
    r"[<>]?\s*([+-]?\d+(?:[,.]\d+)?)(?:\s*(?:x\s*10|[Ee])\s*[+-]?\d+)?",
    re.IGNORECASE,
)
DATE_COLUMNS = {"acm_data_inicio", "data_coleta", "data_publicacao", "data_recebimento"}
DATETIME_COLUMNS = {ACM_EXTRACTION_TIMESTAMP_COLUMN} | DATE_COLUMNS
INTEGER_COLUMNS = {"id_amostra", "id_taxonomia", "versao_template"}
DECIMAL_SOURCES = {
    "acm_resultado_tratado": ("resultado", 0), "acm_conama_minimo": ("conama", 0),
    "acm_conama_maximo": ("conama", 1), "acm_copam_cerh_minimo": ("copam_cerh", 0),
    "acm_copam_cerh_maximo": ("copam_cerh", 1), "acm_ld_minimo": ("ld", 0),
    "acm_ld_maximo": ("ld", 1), "acm_lq_minimo": ("lq", 0), "acm_lq_maximo": ("lq", 1),
    "acm_incerteza_valor": ("incerteza", 0),
    "acm_faixa_aceitacao_minimo": ("faixa_aceitacao", 0),
    "acm_faixa_aceitacao_maximo": ("faixa_aceitacao", 1),
}


def _datetime_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(value).strftime("%d/%m/%Y %H:%M:%S")
    text = str(value).strip()
    match = re.fullmatch(r"(\d{2}/\d{2}/\d{4})(?:\s+(\d{2}:\d{2})(?::(\d{2}))?)?", text)
    if not match:
        return text
    return f"{match.group(1)} {match.group(2) or '00:00'}:{match.group(3) or '00'}"


def _scalar(key: str, value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if key in DATETIME_COLUMNS:
        return _datetime_text(value)
    if key in INTEGER_COLUMNS and re.fullmatch(r"\d+", str(value).strip()):
        return int(str(value).strip())
    if isinstance(value, pd.Timestamp):
        return value.strftime("%d/%m/%Y %H:%M:%S")
    if hasattr(value, "item"):
        value = value.item()
    return value


def _decimal_places(source: Any, index: int) -> int | None:
    if source is None or pd.isna(source):
        return None
    matches = list(SOURCE_NUMBER_IN_TEXT.finditer(str(source)))
    if not matches:
        return None
    selected = matches[min(index, len(matches) - 1)].group(1)
    separator = "," if "," in selected else "." if "." in selected else None
    return len(selected.rsplit(separator, 1)[1]) if separator else 0


def _scaled_decimal(value: Any, source: Any, index: int) -> Any:
    if value is None or pd.isna(value):
        return value
    places = _decimal_places(source, index)
    if places is None:
        return value
    try:
        return Decimal(str(value)).quantize(Decimal(1).scaleb(-places))
    except (InvalidOperation, TypeError, ValueError):
        return value


def _records(frame: pd.DataFrame | None, indices: Any) -> list[dict[str, Any]]:
    if frame is None or indices is None:
        return []
    selected = frame.iloc[indices] if not isinstance(indices, slice) else frame
    if selected.empty:
        return []
    cleaned = selected.astype(object).where(pd.notna(selected), None)
    records = []
    for row in cleaned.to_dict(orient="records"):
        record = {}
        for key, value in row.items():
            key = str(key)
            serialized = _scalar(key, value)
            if key in DECIMAL_SOURCES:
                source, index = DECIMAL_SOURCES[key]
                serialized = _scaled_decimal(serialized, row.get(source), index)
            record[key] = serialized
        records.append(record)
    return records


def _indices_by_file(frame: pd.DataFrame | None) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {}
    if "nome_do_arquivo" not in frame.columns:
        return {"": slice(None)}
    names = frame["nome_do_arquivo"].fillna("").astype(str)
    return {str(name): indices for name, indices in names.groupby(names, sort=False).indices.items()}


def write_jsonl(
    output_path: Path,
    table_sources: dict[str, pd.DataFrame | None],
    audit_sources: dict[str, pd.DataFrame | None],
    sheets: list[str],
) -> None:
    table_indices = {name: _indices_by_file(frame) for name, frame in table_sources.items()}
    audit_indices = {name: _indices_by_file(frame) for name, frame in audit_sources.items()}
    file_names = {
        str(value)
        for frame in [*table_sources.values(), *audit_sources.values()]
        if frame is not None and not frame.empty and "nome_do_arquivo" in frame.columns
        for value in frame["nome_do_arquivo"].dropna()
    } or {""}
    with output_path.open("w", encoding="utf-8") as handle:
        for file_name in sorted(file_names):
            identity_records = []
            tables = {}
            for name, frame in table_sources.items():
                if name in sheets:
                    records = _records(frame, table_indices[name].get(file_name, table_indices[name].get("")))
                    tables[name] = records
                    identity_records.extend(records)
            audits = {}
            for name, frame in audit_sources.items():
                if name in sheets:
                    records = _records(frame, audit_indices[name].get(file_name, audit_indices[name].get("")))
                    audits[name] = records
                    identity_records.extend(records)
            identity = {"nome_do_arquivo": file_name, "id_taxonomia": None, "nome_taxonomia": None, "versao_template": None}
            for record in identity_records:
                for field in ("id_taxonomia", "nome_taxonomia", "versao_template"):
                    if identity[field] is None and record.get(field) is not None:
                        identity[field] = record[field]
            json.dump({"arquivo": identity, "tabelas": tables, "auditoria": audits}, handle, ensure_ascii=False, use_decimal=True, separators=(",", ":"))
            handle.write("\n")
