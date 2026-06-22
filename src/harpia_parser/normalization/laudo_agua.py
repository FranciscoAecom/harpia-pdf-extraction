import pandas as pd

from ..parsing.measure_parser import parse_medida, parse_resultado, texto_vazio
from ..utils import normalizar


def _original_or_none(value):
    return None if texto_vazio(value) else value


def _pdf_text_or_none(value):
    if value is None or pd.isna(value):
        return None
    text = str(value)
    return None if text.strip() == "" else value


def _optional_text(value) -> str | None:
    return None if texto_vazio(value) else str(value)


def _normalize_lq(df: pd.DataFrame) -> pd.DataFrame:
    if "lq" not in df.columns:
        return df

    for index, value in df["lq"].items():
        parsed = parse_medida(value, "lq")
        df.at[index, "lq"] = _original_or_none(value)
        df.at[index, "lq_minimo"] = parsed["lq_minimo"]
        df.at[index, "lq_maximo"] = parsed["lq_maximo"]
        df.at[index, "lq_unidade"] = parsed["lq_unidade"]
    return df


def _normalize_ld(df: pd.DataFrame) -> pd.DataFrame:
    if "ld" not in df.columns:
        return df

    for index, value in df["ld"].items():
        parsed = parse_medida(value, "ld")
        df.at[index, "ld"] = _original_or_none(value)
        df.at[index, "ld_minimo"] = parsed["ld_minimo"]
        df.at[index, "ld_maximo"] = parsed["ld_maximo"]
        df.at[index, "ld_unidade"] = parsed["ld_unidade"]
    return df


def _normalize_normative_field(df: pd.DataFrame, field: str) -> pd.DataFrame:
    if field not in df.columns:
        return df

    for index, value in df[field].items():
        parsed = parse_medida(value, field)
        df.at[index, field] = _pdf_text_or_none(value)
        df.at[index, f"{field}_operador"] = parsed[f"{field}_operador"]
        df.at[index, f"{field}_minimo"] = parsed[f"{field}_minimo"]
        df.at[index, f"{field}_maximo"] = parsed[f"{field}_maximo"]
        df.at[index, f"{field}_unidade"] = parsed[f"{field}_unidade"]
    return df


def _normalize_resultado(df: pd.DataFrame) -> pd.DataFrame:
    if "resultado" not in df.columns:
        return df

    for index, value in df["resultado"].items():
        unidade_fallback = _optional_text(df.at[index, "unidade"]) if "unidade" in df.columns else None
        valor, qualificador, unidade = parse_resultado(value, unidade_fallback)
        parametro = df.at[index, "parameter"] if "parameter" in df.columns else None
        if unidade is None and normalizar(str(parametro or "")) == "ph":
            unidade = "pH"

        df.at[index, "resultado_tratado"] = valor
        df.at[index, "qualificador"] = qualificador
        df.at[index, "unidade"] = unidade
    return df


def _normalize_incerteza(df: pd.DataFrame) -> pd.DataFrame:
    if "incerteza" not in df.columns:
        return df

    for index, value in df["incerteza"].items():
        parsed = parse_medida(value, "incerteza")
        df.at[index, "incerteza"] = _original_or_none(value)
        df.at[index, "incerteza_valor"] = parsed["incerteza_minimo"]
        df.at[index, "incerteza_unidade"] = parsed["incerteza_unidade"]
    return df


def _normalize_faixa_aceitacao(df: pd.DataFrame) -> pd.DataFrame:
    if "faixa_aceitacao" not in df.columns:
        return df

    for index, value in df["faixa_aceitacao"].items():
        parsed = parse_medida(value, "faixa_aceitacao", duplicar_valor_simples=True)
        df.at[index, "faixa_aceitacao"] = _original_or_none(value)
        df.at[index, "faixa_aceitacao_operador"] = parsed["faixa_aceitacao_operador"]
        df.at[index, "faixa_aceitacao_minimo"] = parsed["faixa_aceitacao_minimo"]
        df.at[index, "faixa_aceitacao_maximo"] = parsed["faixa_aceitacao_maximo"]
        df.at[index, "faixa_aceitacao_unidade"] = parsed["faixa_aceitacao_unidade"]
    return df


def normalize(
    df: pd.DataFrame,
    sample_df: pd.DataFrame,
    client_df: pd.DataFrame,
    context,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not df.empty:
        df = df.copy()
        df = _normalize_resultado(df)
        df = _normalize_normative_field(df, "conama")
        df = _normalize_normative_field(df, "copam_cerh")
        df = _normalize_ld(df)
        df = _normalize_lq(df)
        df = _normalize_incerteza(df)
        df = _normalize_faixa_aceitacao(df)

    return df, sample_df, client_df
