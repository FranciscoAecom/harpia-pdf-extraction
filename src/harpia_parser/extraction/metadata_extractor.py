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
            data[rule["campo"]] = val if val else "BASE"
        else:
            data[rule["campo"]] = None
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

    latitude = parse_decimal_pt(metadata.get("latitude"))
    longitude = parse_decimal_pt(metadata.get("longitude"))
    coordenadas = f"{latitude},{longitude}" if latitude is not None and longitude is not None else None

    sample = {
        "id_amostra": metadata.get("id_amostra"),
        "identificacao_amostra": extracted.get("identificacao_amostra"),
        "tipo_amostra": extracted.get("tipo_amostra"),
        "criterio_conformidade": extracted.get("criterio_conformidade"),
        "data_coleta": metadata.get("data_coleta"),
        "dh_coleta": extracted.get("dh_coleta"),
        "data_publicacao": extracted.get("data_publicacao"),
        "dh_publicacao": extracted.get("dh_publicacao"),
        "data_recebimento": extracted.get("data_recebimento"),
        "dh_recebimento": extracted.get("dh_recebimento"),
        "observacoes": extracted.get("observacoes"),
        "dh_inicio_atividade": extracted.get("dh_inicio_atividade"),
        "localizacao": extracted.get("localizacao"),
        "latitude": latitude,
        "longitude": longitude,
        "coordenadas": coordenadas,
        "clima_ultimas_24h": extracted.get("clima_ultimas_24h"),
        "clima": extracted.get("clima"),
        "tipo_coleta": extracted.get("tipo_coleta"),
        "responsavel_amostra": extracted.get("responsavel_amostra"),
        "planejamento_amostragem": extracted.get("planejamento_amostragem"),
        "descricao_nao_conformidade": extracted.get("descricao_nao_conformidade"),
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
        r"Relat.rio Anal.tico\s*(\d+/\d+\.\d+)(?:\.([A-Z]{1,2}))?",
        texto,
        re.IGNORECASE,
    )
    if not match:
        return None

    relatorio_base = match.group(1)
    sufixo = match.group(2)
    return f"{relatorio_base}.{sufixo}" if sufixo else relatorio_base
