import re

from .header_aliases import field_from_header_cell
from .section_classifier import linha_header
from ..constants import LAYOUT_FIELD_KEYS
from ..utils import cell


IGNORAR_TEXTO_LINHA = re.compile(
    r"data\s+coleta|data\s+recebimento|responsabilidade|tipo\s+de\s+coleta",
    re.IGNORECASE,
)


def _base_layout(tipo_registro: str | None, config) -> dict[str, int | None]:
    fallback = config.table_layouts.get("AMOSTRA", {})
    layout = config.table_layouts.get(tipo_registro, fallback).copy()
    return {field: layout.get(field) for field in LAYOUT_FIELD_KEYS}


def _layout_from_header(row: list, tipo_registro: str | None, config) -> dict[str, int | None] | None:
    layout: dict[str, int | None] = {field: None for field in LAYOUT_FIELD_KEYS}
    found = False
    for index, value in enumerate(row):
        field = field_from_header_cell(value, config)
        if field:
            layout[field] = index
            found = True
    return layout if found and layout.get("resultado_col") is not None else None


def _header_names_from_layout(row: list, layout: dict[str, int | None]) -> dict[str, str | None]:
    headers: dict[str, str | None] = {}
    for field, index in layout.items():
        headers[field] = cell(row, index)
    return headers


def processar_linha(row: list, estado: dict, config) -> dict | None:
    txt = " ".join(str(c) for c in row if c)

    if len([c for c in row if c]) < 2:
        return None

    if linha_header(row):
        header_layout = _layout_from_header(row, estado.get("tipo_registro"), config)
        if header_layout:
            estado["layout_override"] = header_layout
            estado["layout_override_tipo"] = estado.get("tipo_registro")
            estado["layout_override_headers"] = _header_names_from_layout(row, header_layout)
        return None

    if IGNORAR_TEXTO_LINHA.search(txt) or not re.search(r"\d", txt):
        return None

    parametro = str(row[0] or "").strip()
    if not parametro:
        return None

    tipo_registro = estado.get("tipo_registro")
    layout = (
        estado.get("layout_override")
        if estado.get("layout_override_tipo") == tipo_registro
        else None
    ) or _base_layout(tipo_registro, config)
    layout_headers = (
        estado.get("layout_override_headers")
        if estado.get("layout_override_tipo") == tipo_registro
        else {}
    ) or {}
    resultado_cell = cell(row, layout.get("resultado_col"))
    unidade_cell = cell(row, layout.get("unidade_col"))

    if not re.search(r"\d", str(resultado_cell or "")):
        return None

    return {
        "categoria": estado.get("categoria"),
        "subcategoria": estado.get("subcategoria"),
        "tipo_registro": tipo_registro,
        "parametro": parametro,
        "resultado": resultado_cell,
        "resultado_tratado": None,
        "qualificador_resultado": None,
        "unidade_resultado": unidade_cell,
        "local": estado.get("local"),
        "data_inicio": cell(row, layout.get("data_inicio_col")),
        "conama": cell(row, layout.get("conama_col")),
        "copam_cerh": cell(row, layout.get("copam_cerh_col")),
        "ld": cell(row, layout.get("ld_col")),
        "lq": cell(row, layout.get("lq_col")),
        "referencia": cell(row, layout.get("referencia_col")),
        "incerteza": cell(row, layout.get("incerteza_col")),
        "numero_cq": cell(row, layout.get("numero_cq_col")),
        "duplicata": cell(row, layout.get("duplicata_col")),
        "faixa_aceitacao": cell(row, layout.get("faixa_aceitacao_col")),
        "variacao_percentual": cell(row, layout.get("variacao_percentual_col")),
        "quantidade_adicionada": cell(row, layout.get("quantidade_adicionada_col")),
        "recuperacao_percentual": cell(row, layout.get("recuperacao_percentual_col")),
    }
