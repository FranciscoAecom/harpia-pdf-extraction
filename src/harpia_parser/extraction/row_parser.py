import re

from .section_classifier import linha_header
from ..utils import cell


IGNORAR_TEXTO_LINHA = re.compile(
    r"data\s+coleta|data\s+recebimento|responsabilidade|tipo\s+de\s+coleta",
    re.IGNORECASE,
)


def processar_linha(row: list, estado: dict, config) -> dict | None:
    txt = " ".join(str(c) for c in row if c)

    if IGNORAR_TEXTO_LINHA.search(txt) or not re.search(r"\d", txt):
        return None
    if len([c for c in row if c]) < 2 or linha_header(row):
        return None

    parametro = str(row[0] or "").strip()
    if not parametro:
        return None

    tipo_registro = estado.get("tipo_registro")
    layout = config.result_layouts.get(tipo_registro, config.result_layouts["AMOSTRA"])
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
