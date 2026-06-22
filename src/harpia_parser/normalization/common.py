import pandas as pd


PRESERVE_TEXT_COLUMNS = {
    "resultado",
    "ld",
    "lq",
    "incerteza",
    "faixa_aceitacao",
}


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


def _normalize_common(df: pd.DataFrame, sample_df: pd.DataFrame, client_df: pd.DataFrame):
    return _strip_text_columns(df), _strip_text_columns(sample_df), _strip_text_columns(client_df)


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
