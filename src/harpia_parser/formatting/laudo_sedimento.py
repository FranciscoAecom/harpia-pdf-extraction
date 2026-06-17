import pandas as pd

from ..constants import RESULTS_EXTRACT_COLUMNS


def format_results_extract(df: pd.DataFrame, config, context=None) -> pd.DataFrame:
    return pd.DataFrame(columns=RESULTS_EXTRACT_COLUMNS)
