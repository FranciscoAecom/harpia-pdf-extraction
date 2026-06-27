import re

import pandas as pd

from ..constants import CLIENT_COLUMNS, SAMPLE_COLUMNS
from ..utils import parse_decimal_pt, search_group


def extract_metadata(texto: str, config) -> dict:
    data = {}
    for rule in config.metadata_rules:
        match = rule["regex"].search(texto)
        if match:
            val = match.group(1) if match.lastindex and match.group(1) else None
            if rule["campo"] == "codigo_laudo" and val:
                val = re.sub(r"\s+", " ", val).strip()
            data[rule["campo"]] = val if val else "BASE"
        else:
            data[rule["campo"]] = None
    if not data.get("codigo_laudo"):
        data["codigo_laudo"] = codigo_laudo_from_text(texto)
    return data


def extract_sample(texto: str, metadata: dict, config) -> pd.DataFrame:
    extracted = {}

    if not config.df_sample_text_rules.empty:
        for _, row in config.df_sample_text_rules.iterrows():
            campo = row.get("campo")
            regex = row.get("regex")
            if pd.notna(campo) and pd.notna(regex) and str(regex) != "DERIVADO_DO_NOME_DO_PDF":
                extracted[str(campo)] = search_group(str(regex), texto)

    if extracted.get("descricao_nao_conformidade"):
        extracted["descricao_nao_conformidade"] = _clean_descricao_nao_conformidade(
            extracted["descricao_nao_conformidade"]
        )
    if extracted.get("planejamento_amostragem"):
        extracted["planejamento_amostragem"] = _clean_planejamento_amostragem(
            extracted["planejamento_amostragem"]
        )

    latitude = parse_decimal_pt(metadata.get("latitude"))
    longitude = parse_decimal_pt(metadata.get("longitude"))

    sample = {
        "id_amostra": metadata.get("id_amostra"),
        "identificacao_amostra": extracted.get("identificacao_amostra"),
        "tipo_amostra": extracted.get("tipo_amostra"),
        "criterio_conformidade": extracted.get("criterio_conformidade"),
        "data_coleta": metadata.get("data_coleta"),
        "data_publicacao": extracted.get("data_publicacao"),
        "data_recebimento": extracted.get("data_recebimento"),
        "observacoes": extracted.get("observacoes"),
        "localizacao": extracted.get("localizacao"),
        "latitude": latitude,
        "longitude": longitude,
        "clima_ultimas_24h": extracted.get("clima_ultimas_24h"),
        "clima": extracted.get("clima"),
        "tipo_coleta": extracted.get("tipo_coleta"),
        "responsavel_amostra": extracted.get("responsavel_amostra"),
        "planejamento_amostragem": extracted.get("planejamento_amostragem"),
        "descricao_nao_conformidade": extracted.get("descricao_nao_conformidade"),
        "codigo_laudo_substituido": extracted.get("codigo_laudo_substituido"),
    }
    return pd.DataFrame([sample], columns=SAMPLE_COLUMNS)


def _clean_descricao_nao_conformidade(value: str) -> str:
    value = re.sub(
        r"\s*Planejamento de Amostragem:\s*\S+\s*",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", value).strip()


def _clean_planejamento_amostragem(value: str) -> str | None:
    match = re.search(r"\bCA\d+/\d{4}\b", str(value or ""), re.IGNORECASE)
    return match.group(0) if match else None


def extract_client(texto: str, metadata: dict, config) -> pd.DataFrame:
    extracted = {}

    if not config.df_client_text_rules.empty:
        for _, row in config.df_client_text_rules.iterrows():
            campo = row.get("campo")
            regex = row.get("regex")
            if pd.notna(campo) and pd.notna(regex) and str(regex) != "DERIVADO_DO_NOME_DO_PDF":
                extracted[str(campo)] = search_group(str(regex), texto)

    client = {
        "id_amostra": metadata.get("id_amostra"),
        "proposta_comercial": extracted.get("proposta_comercial"),
        "cliente": extracted.get("cliente"),
        "cnpj_cpf": extracted.get("cnpj_cpf"),
        "contato": extracted.get("contato"),
        "telefone": extracted.get("telefone"),
        "endereco": extracted.get("endereco"),
    }
    return pd.DataFrame([client], columns=CLIENT_COLUMNS)


def relatorio_from_text(texto: str) -> str | None:
    match = re.search(
        r"Relat.rio\s+Anal.tico(?:\s+Parcial)?\s*(\d+/\d+\.\d+)(?:\.([A-Z]{1,2}))?",
        texto,
        re.IGNORECASE,
    )
    if not match:
        return None

    relatorio_base = match.group(1)
    sufixo = match.group(2)
    return f"{relatorio_base}.{sufixo}" if sufixo else relatorio_base


def codigo_laudo_from_text(texto: str) -> str | None:
    match = re.search(
        r"(Relat.rio\s+Anal.tico(?:\s+Parcial)?\s*\d+/\d+\.\d+(?:\.[A-Z]{1,2})?)",
        texto,
        re.IGNORECASE,
    )
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip()
