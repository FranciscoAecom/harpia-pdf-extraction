import os
import re
import unicodedata
from pathlib import Path


def resolve_path(base_dir: Path, env_name: str, default_name: str) -> Path:
    raw = Path(os.environ.get(env_name, default_name))
    if raw.is_absolute():
        return raw
    if raw.parent == Path("."):
        return base_dir / raw
    return Path.cwd() / raw


def normalizar(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt).strip().casefold()


def search_group(pattern: str, texto: str, group: int = 1) -> str | None:
    match = re.search(pattern, texto, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(group)).strip()


def parse_decimal_pt(valor: str | None) -> float | None:
    if valor is None:
        return None
    try:
        return float(str(valor).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def cell(row: list, index: int | None) -> str | None:
    if index is None or len(row) <= index:
        return None
    value = row[index]
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value or None
