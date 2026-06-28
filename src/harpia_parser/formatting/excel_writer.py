from collections.abc import Callable
from pathlib import Path

import pandas as pd

from ..constants import DUPLICATE_AUDIT_COLUMNS


def write_excel(
    output_path: Path,
    sheets: list[str],
    frames: dict[str, pd.DataFrame | None],
    format_results: Callable[[pd.ExcelWriter, pd.DataFrame], None],
    format_sheet: Callable[[pd.ExcelWriter, str], None],
) -> None:
    with pd.ExcelWriter(output_path) as writer:
        written = []
        for sheet in sheets:
            frame = frames.get(sheet)
            if sheet == "duplicate_audit" and frame is None:
                frame = pd.DataFrame(columns=DUPLICATE_AUDIT_COLUMNS)
            if frame is None:
                continue
            frame.to_excel(writer, sheet_name=sheet, index=False)
            if sheet == "results_extract":
                format_results(writer, frame)
            written.append(sheet)
        for sheet in written:
            format_sheet(writer, sheet)
