import re

from .section_classifier import linha_header
from ..constants import LAYOUT_FIELD_KEYS
from ..utils import cell
from ..utils import normalizar


IGNORAR_TEXTO_LINHA = re.compile(
    r"data\s+coleta|data\s+recebimento|responsabilidade|tipo\s+de\s+coleta",
    re.IGNORECASE,
)


def _base_layout(tipo_registro: str | None, config) -> dict[str, int | None]:
    fallback = config.table_layouts.get("AMOSTRA", {})
    layout = config.table_layouts.get(tipo_registro, fallback).copy()
    return {field: layout.get(field) for field in LAYOUT_FIELD_KEYS}


def _field_from_header_cell(value: object) -> str | None:
    text = normalizar(str(value or ""))
    if not text:
        return None

    if text in {"unidade", "unid"}:
        return "unidade_col"
    if text == "ld" or "limite de deteccao" in text:
        return "ld_col"
    if text == "lq" or "limite de quantificacao" in text:
        return "lq_col"
    if text == "resultado" or text == "resultados":
        return "resultado_col"
    if "incerteza" in text:
        return "incerteza_col"
    if "referencia" in text:
        return "referencia_col"
    if "data de inicio" in text or "data inicio" in text:
        return "data_inicio_col"
    if "numero do cq" in text or text == "cq":
        return "numero_cq_col"
    if text == "duplicata":
        return "duplicata_col"
    if "faixa de aceitacao" in text:
        return "faixa_aceitacao_col"
    if "variacao" in text:
        return "variacao_percentual_col"
    if "quantidade adicionada" in text or text == "qtd adicionada":
        return "quantidade_adicionada_col"
    if "recuperacao" in text:
        return "recuperacao_percentual_col"
    if "resolucao" in text or "conama" in text or "criterio" in text:
        return "criterio_conformidade_col"
    return None


def _layout_from_header(row: list, tipo_registro: str | None, config) -> dict[str, int | None] | None:
    layout: dict[str, int | None] = {field: None for field in LAYOUT_FIELD_KEYS}
    found = False
    for index, value in enumerate(row):
        field = _field_from_header_cell(value)
        if field:
            layout[field] = index
            found = True
    return layout if found and layout.get("resultado_col") is not None else None


def processar_linha(row: list, estado: dict, config) -> dict | None:
    txt = " ".join(str(c) for c in row if c)

    if len([c for c in row if c]) < 2:
        return None

    if linha_header(row):
        header_layout = _layout_from_header(row, estado.get("tipo_registro"), config)
        if header_layout:
            estado["layout_override"] = header_layout
            estado["layout_override_tipo"] = estado.get("tipo_registro")
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
        "criterio_conformidade": cell(row, layout.get("criterio_conformidade_col")),
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
