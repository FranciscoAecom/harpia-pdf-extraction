import re

from ..utils import normalizar


def novo_estado() -> dict:
    return {
        "categoria": None,
        "tipo_registro": "AMOSTRA",
        "subcategoria": None,
        "local": None,
    }


def aplicar_category_type_rule(txt: str, estado: dict, config) -> bool:
    for regra in config.category_type_rules:
        if regra["regex"].search(txt):
            estado["categoria"] = regra["categoria"]
            estado["tipo_registro"] = regra["tipo_registro"]
            estado["local"] = "laboratorio"
            if regra["extrair_subcategoria"] and "-" in txt:
                estado["subcategoria"] = re.sub(r"\s+", " ", txt).strip()
            else:
                estado["subcategoria"] = None
            return True
    return False


def _apply_section_subcategory(txt: str, estado: dict, config) -> bool:
    raw = re.sub(r"\s+", " ", txt or "").strip()
    norm = normalizar(raw)
    if not norm:
        return False

    for rule in getattr(config, "subcategory_alias_rules", []):
        if rule["regex"].search(norm):
            estado["categoria"] = rule["categoria"]
            estado["subcategoria"] = rule["subcategoria"] or raw
            estado["tipo_registro"] = rule["tipo_registro"]
            estado["local"] = rule["local"]
            return True
    return False


def _apply_section_title(txt: str, estado: dict, config) -> bool:
    raw = re.sub(r"\s+", " ", txt or "").strip()
    norm = normalizar(raw)
    if not norm:
        return False

    if _apply_section_subcategory(raw, estado, config):
        return True

    tipo_registro = "AMOSTRA"
    subcat_from_tipo = None
    section_norm = norm

    if " - " in raw and not norm.startswith("ethica ambiental"):
        _, subcat_txt = raw.split(" - ", 1)
        section_norm = normalizar(subcat_txt)
        subcat_from_tipo = raw

    for rule in config.category_alias_rules:
        if rule["regex"].search(section_norm) or rule["regex"].search(norm):
            if (
                estado.get("categoria") == rule["categoria"]
                and estado.get("subcategoria")
                and not rule["subcategoria"]
            ):
                return True
            estado["categoria"] = rule["categoria"]
            estado["subcategoria"] = rule["subcategoria"] or subcat_from_tipo
            estado["tipo_registro"] = tipo_registro
            estado["local"] = rule["local"]
            return True

    return False


def aplicar_section_pdf(txt: str, estado: dict, config) -> bool:
    return _apply_section_title(txt, estado, config) or aplicar_category_type_rule(txt, estado, config)


def estado_from_section_title(txt: str, config) -> dict | None:
    estado = novo_estado()
    if _apply_section_title(txt, estado, config):
        return estado
    return None


def pending_section_from_page_text(page_text: str, config) -> dict | None:
    pending = None
    for line in page_text.splitlines():
        candidate = estado_from_section_title(line, config)
        if candidate:
            if (
                pending
                and pending.get("categoria") == candidate.get("categoria")
                and pending.get("subcategoria")
                and not candidate.get("subcategoria")
            ):
                continue
            pending = candidate
    return pending


def linha_header(row: list) -> bool:
    if len(row) < 2:
        return False
    col0 = normalizar(str(row[0] or ""))
    col1 = normalizar(str(row[1] or ""))
    return col0 in {"analise", "parametros"} and col1 in {"resultado", "numero do cq", "unidade"}


def tabela_resultado(rows: list, estado: dict) -> bool:
    if any(linha_header(row) for row in rows[:2]):
        return True

    if not estado.get("categoria") or estado.get("tipo_registro") != "AMOSTRA":
        return False

    data_rows = 0
    for row in rows[:5]:
        if len(row) < 5:
            continue
        parametro = normalizar(str(row[0] or ""))
        resultado = str(row[1] or "").strip()
        if parametro and re.search(r"(^[<>]=?|[+-]?\d)", resultado):
            data_rows += 1
    return data_rows >= 2


def inferir_qaqc_continuacao(tabela: list, estado: dict, config) -> bool:
    if not tabela or len(tabela[0]) < 2:
        return False

    first = tabela[0]
    row_text = " ".join(str(c or "") for c in first)
    matched_tipo = None
    for rule in config.continuation_rules:
        if rule["regex"].search(row_text):
            matched_tipo = rule["tipo_registro"]
            break

    if not matched_tipo:
        return False

    if estado.get("tipo_registro") in {"BRANCO", "DUPLICATA", "RECUPERACAO"}:
        pass
    elif matched_tipo:
        estado["tipo_registro"] = matched_tipo
    elif len(first) >= 7:
        estado["tipo_registro"] = "DUPLICATA"
    elif len(first) >= 6:
        estado["tipo_registro"] = "RECUPERACAO"
    elif len(first) >= 5:
        estado["tipo_registro"] = "BRANCO"
    else:
        return False

    if not estado.get("subcategoria"):
        estado["subcategoria"] = estado.get("categoria")
    estado["local"] = "laboratorio"
    return True
