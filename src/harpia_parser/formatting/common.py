import pandas as pd

from ..constants import RESULTS_EXTRACT_COLUMNS


def format_results_extract(df: pd.DataFrame, config, context) -> pd.DataFrame:
    if context.tipo_laudo == "laudo_agua":
        from .laudo_agua import format_results_extract as format_laudo_agua

        return format_laudo_agua(df, config, context)

    return pd.DataFrame(columns=RESULTS_EXTRACT_COLUMNS)
