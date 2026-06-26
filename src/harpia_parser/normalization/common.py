import re

import pandas as pd


PRESERVE_TEXT_COLUMNS = {
    "resultado",
    "ld",
    "lq",
    "incerteza",
    "faixa_aceitacao",
}


CODIGO_LAUDO_SUFFIX = re.compile(r"\b\d+/\d{4}\.(\d+(?:\.[A-Za-z0-9]+)*)\b")
DATE_TEXT = re.compile(r"\b(\d{2}/\d{2}/\d{4})(?:\s+(\d{2}:\d{2}(?::\d{2})?))?\b")


def _extract_acm_codigo_laudo(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    match = CODIGO_LAUDO_SUFFIX.search(str(value))
    return match.group(1) if match else None


def _extract_acm_data_inicio(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    match = DATE_TEXT.search(str(value))
    if not match:
        return None
    time_text = match.group(2) or "00:00:00"
    if time_text.count(":") == 1:
        time_text = f"{time_text}:00"
    return f"{match.group(1)} {time_text}"


def _strip_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    normalized = df.copy()
    for column in normalized.columns:
        if column in PRESERVE_TEXT_COLUMNS:
            continue
        if not normalized[column].map(lambda value: isinstance(value, str)).any():
            continue
        normalized[column] = normalized[column].map(lambda value: value.strip() if isinstance(value, str) else value)
    return normalized


def _normalize_codigo_laudo(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "codigo_laudo" not in df.columns:
        return df
    normalized = df.copy()
    normalized["acm_codigo_laudo"] = normalized["codigo_laudo"].map(_extract_acm_codigo_laudo)
    return normalized


def _normalize_data_inicio(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "data_inicio" not in df.columns:
        return df
    normalized = df.copy()
    normalized["acm_data_inicio"] = normalized["data_inicio"].map(_extract_acm_data_inicio)
    return normalized


def _normalize_common(df: pd.DataFrame, sample_df: pd.DataFrame, client_df: pd.DataFrame):
    normalized_df = _strip_text_columns(df)
    normalized_df = _normalize_codigo_laudo(normalized_df)
    normalized_df = _normalize_data_inicio(normalized_df)
    return (
        normalized_df,
        _strip_text_columns(sample_df),
        _strip_text_columns(client_df),
    )


def normalize_outputs(
    df: pd.DataFrame,
    sample_df: pd.DataFrame,
    client_df: pd.DataFrame,
    context,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df, sample_df, client_df = _normalize_common(df, sample_df, client_df)

    if context.tipo_laudo == "laudo_agua":
        from .laudo_agua import normalize
    elif context.tipo_laudo == "laudo_fito":
        from .laudo_fito import normalize
    elif context.tipo_laudo == "laudo_sedimento":
        from .laudo_sedimento import normalize
    else:
        return df, sample_df, client_df

    return normalize(df, sample_df, client_df, context)
