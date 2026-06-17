import pandas as pd


def normalize(
    df: pd.DataFrame,
    sample_df: pd.DataFrame,
    client_df: pd.DataFrame,
    context,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return df, sample_df, client_df
