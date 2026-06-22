import re
from typing import Any

from ..utils import normalizar


EMPTY_TOKENS = {"", "NA", "ND", "N/A", "NAN"}
UNIDADES_CONHECIDAS = re.compile(
    r"(mg/L\s*\(como\s*\w+\)|NMP/100mL|\u00b5S/cm|\u00b5g/L|mg/L|UNT|NTU|"
    r"NMP/mL|UFC/mL|mg/kg|\u00b0C|pH|mV|\u2030|%|\bm\b)"
)


def texto_vazio(valor: Any) -> bool:
    texto = re.sub(r"\s+", " ", str(valor or "")).strip()
    return texto.upper() in EMPTY_TOKENS


def parse_numero_pt(valor: str) -> float | None:
    valor = valor.strip()
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return None


def extrair_unidade(texto: str) -> tuple[str, str | None]:
    match = UNIDADES_CONHECIDAS.search(texto)
    if not match:
        return texto, None
    unidade = match.group(0)
    texto_sem_unidade = (texto[:match.start()] + texto[match.end():]).strip()
    return re.sub(r"\s+", " ", texto_sem_unidade), unidade


def unidade_from_partes(partes: list) -> str | None:
    for parte in partes:
        match = UNIDADES_CONHECIDAS.search(str(parte or ""))
        if match:
            return match.group(0)
    return None


def parse_medida(original: Any, prefixo: str, duplicar_valor_simples: bool = False) -> dict[str, Any]:
    texto = re.sub(r"\s+", " ", str(original or "")).strip()
    is_empty = texto_vazio(texto)
    base = {
        prefixo: None if is_empty else texto,
        f"{prefixo}_operador": None,
        f"{prefixo}_minimo": None,
        f"{prefixo}_maximo": None,
        f"{prefixo}_unidade": None,
    }

    if is_empty:
        return base

    texto_sem_unidade, unidade = extrair_unidade(texto)
    base[f"{prefixo}_unidade"] = unidade

    operador = None
    texto_operador = normalizar(texto_sem_unidade)
    if texto_operador.startswith(("max.", "max ", "maximo", "maximo")):
        operador = "max"
    elif texto_operador.startswith(("min.", "min ", "minimo", "minimo")):
        operador = "min"
    else:
        match_operador = re.match(r"^\s*(<=|>=|<|>|=)", texto_sem_unidade)
        if match_operador:
            operador = match_operador.group(1)

    if operador:
        base[f"{prefixo}_operador"] = operador
        texto_sem_unidade = re.sub(
            r"^\s*(?:M[a\u00e1]x\.?|M[i\u00ed]n\.?|M[a\u00e1]ximo|M[i\u00ed]nimo|<=|>=|<|>|=)\s*",
            "",
            texto_sem_unidade,
            flags=re.IGNORECASE,
        )

    faixa = re.search(
        r"([+-]?[\d.,]+)\s*(?:-|(?:\ba\b))\s*([+-]?[\d.,]+)",
        texto_sem_unidade,
        re.IGNORECASE,
    )
    if faixa:
        base[f"{prefixo}_minimo"] = parse_numero_pt(faixa.group(1))
        base[f"{prefixo}_maximo"] = parse_numero_pt(faixa.group(2))
        return base

    valor = re.search(r"([<>]?)\s*([+-]?[\d.,]+)", texto_sem_unidade)
    if valor:
        numero = parse_numero_pt(valor.group(2))
        if not base[f"{prefixo}_operador"] and valor.group(1):
            base[f"{prefixo}_operador"] = valor.group(1)
        if duplicar_valor_simples:
            base[f"{prefixo}_minimo"] = numero
            base[f"{prefixo}_maximo"] = numero
            return base
        operador_final = base[f"{prefixo}_operador"]
        if operador_final in {"max", "<", "<="}:
            base[f"{prefixo}_maximo"] = numero
        elif operador_final in {"min", ">", ">="}:
            base[f"{prefixo}_minimo"] = numero
        else:
            base[f"{prefixo}_minimo"] = numero
            base[f"{prefixo}_maximo"] = numero
        return base

    return base


def parse_resultado(
    celula_resultado: str | None,
    unidade_fallback: str | None = None,
) -> tuple[float | None, str | None, str | None]:
    texto = re.sub(r"\s+", " ", str(celula_resultado or "")).strip()
    if texto_vazio(texto):
        return None, None, unidade_fallback

    qualificador = None
    match_qual = re.match(r"^\s*([<>])", texto)
    if match_qual:
        qualificador = match_qual.group(1)

    match = re.search(r"([<>]?)\s*([\d.,]+)(?:\s*x\s*10\s*([+-]?\d+))?", texto, re.IGNORECASE)
    valor = None
    if match:
        valor = parse_numero_pt(match.group(2))
        expoente_txt = match.group(3)
        if valor is not None and expoente_txt is not None:
            expoente = int(expoente_txt[-1]) if len(expoente_txt) > 1 and expoente_txt.startswith("10") else int(expoente_txt)
            valor *= 10 ** expoente
        if not qualificador:
            qualificador = match.group(1) or None

    unidade = unidade_from_partes([texto, unidade_fallback])
    return valor, qualificador, unidade
