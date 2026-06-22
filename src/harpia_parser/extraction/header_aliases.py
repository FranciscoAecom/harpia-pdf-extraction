from __future__ import annotations

import re

from ..utils import normalizar


STATIC_EXACT_ALIASES = [
    ("parameter", {"analise", "parametro", "parametros"}),
    ("unidade_col", {"unidade", "unid"}),
    ("resultado_col", {"resultado", "resultados"}),
    ("numero_cq_col", {"cq"}),
    ("duplicata_col", {"duplicata"}),
]

STATIC_REGEX_ALIASES = [
    ("ld_col", re.compile(r"(^ld$|limite de deteccao)", re.IGNORECASE)),
    ("lq_col", re.compile(r"(^lq$|limite de quantificacao)", re.IGNORECASE)),
    ("incerteza_col", re.compile(r"incerteza", re.IGNORECASE)),
    ("referencia_col", re.compile(r"referencia", re.IGNORECASE)),
    ("data_inicio_col", re.compile(r"data de inicio|data inicio", re.IGNORECASE)),
    ("numero_cq_col", re.compile(r"numero do cq", re.IGNORECASE)),
    ("faixa_aceitacao_col", re.compile(r"faixa de aceitacao", re.IGNORECASE)),
    ("variacao_percentual_col", re.compile(r"variacao", re.IGNORECASE)),
    ("quantidade_adicionada_col", re.compile(r"quantidade adicionada|^qtd adicionada$", re.IGNORECASE)),
    ("recuperacao_percentual_col", re.compile(r"recuperacao", re.IGNORECASE)),
    ("criterio_conformidade_col", re.compile(r"resolucao|conama|criterio", re.IGNORECASE)),
]


def field_from_header_cell(value: object, config, *, include_parameter: bool = False) -> str | None:
    text = normalizar(str(value or ""))
    if not text:
        return None

    for rule in getattr(config, "header_alias_rules", []):
        field = rule["field"]
        if field == "parameter" and not include_parameter:
            continue
        if rule["regex"].search(text):
            return field

    for field, aliases in STATIC_EXACT_ALIASES:
        if field == "parameter" and not include_parameter:
            continue
        if text in aliases:
            return field
    for field, regex in STATIC_REGEX_ALIASES:
        if regex.search(text):
            return field
    return None
