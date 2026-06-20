import pandas as pd

from ..parsing.measure_parser import parse_medida, parse_resultado, texto_vazio
from ..utils import normalizar

CALC_ERROR_TOKENS = {"VALUE", "DIV0", "#VALUE!", "#DIV/0!"}


def _original_or_none(value):
    return None if texto_vazio(value) else value


def _optional_text(value) -> str | None:
    return None if texto_vazio(value) else str(value)


def _normalize_lq(df: pd.DataFrame) -> pd.DataFrame:
    if "lq_original" not in df.columns:
        return df

    for index, value in df["lq_original"].items():
        parsed = parse_medida(value, "lq")
        df.at[index, "lq_original"] = _original_or_none(value)
        df.at[index, "lq_minimo"] = parsed["lq_minimo"]
        df.at[index, "lq_maximo"] = parsed["lq_maximo"]
        df.at[index, "lq_unidade"] = parsed["lq_unidade"]
    return df


def _normalize_ld(df: pd.DataFrame) -> pd.DataFrame:
    if "ld_original" not in df.columns:
        return df

    for index, value in df["ld_original"].items():
        parsed = parse_medida(value, "ld")
        df.at[index, "ld_original"] = _original_or_none(value)
        df.at[index, "ld_minimo"] = parsed["ld_minimo"]
        df.at[index, "ld_maximo"] = parsed["ld_maximo"]
        df.at[index, "ld_unidade"] = parsed["ld_unidade"]
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
    if "incerteza_original" not in df.columns:
        return df

    for index, value in df["incerteza_original"].items():
        parsed = parse_medida(value, "incerteza")
        df.at[index, "incerteza_original"] = _original_or_none(value)
        df.at[index, "incerteza_valor"] = parsed["incerteza_minimo"]
        df.at[index, "incerteza_unidade"] = parsed["incerteza_unidade"]
    return df


def _normalize_faixa_aceitacao(df: pd.DataFrame) -> pd.DataFrame:
    if "faixa_aceitacao_original" not in df.columns:
        return df

    for index, value in df["faixa_aceitacao_original"].items():
        parsed = parse_medida(value, "faixa_aceitacao", duplicar_valor_simples=True)
        df.at[index, "faixa_aceitacao_original"] = _original_or_none(value)
        df.at[index, "faixa_aceitacao_operador"] = parsed["faixa_aceitacao_operador"]
        df.at[index, "faixa_aceitacao_minimo"] = parsed["faixa_aceitacao_minimo"]
        df.at[index, "faixa_aceitacao_maximo"] = parsed["faixa_aceitacao_maximo"]
        df.at[index, "faixa_aceitacao_unidade"] = parsed["faixa_aceitacao_unidade"]
    return df


def _normalize_numeric_error_tokens(df: pd.DataFrame) -> pd.DataFrame:
    for column in {"variacao_percentual", "quantidade_adicionada", "recuperacao_percentual"} & set(df.columns):
        df[column] = df[column].map(
            lambda value: None
            if str(value or "").strip().upper() in CALC_ERROR_TOKENS
            else value
        )
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
        df = _normalize_ld(df)
        df = _normalize_lq(df)
        df = _normalize_incerteza(df)
        df = _normalize_faixa_aceitacao(df)
        df = _normalize_numeric_error_tokens(df)

    return df, sample_df, client_df
