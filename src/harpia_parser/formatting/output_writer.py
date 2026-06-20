from pathlib import Path
import re

import pandas as pd

from ..validation.schemas import validate_outputs


NUMERIC_TEXT = re.compile(r"^([+-]?\d+(?:[,.]\d+)?)(?:\s*x\s*10\s*([+-]?\d+))?$", re.IGNORECASE)
NUMBER_IN_TEXT = re.compile(r"[<>]?\s*([+-]?\d+(?:[,.]\d+)?)")


def _numeric_value_and_format(value) -> tuple[float, str] | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    match = NUMERIC_TEXT.match(text)
    if not match:
        return None

    mantissa = match.group(1)
    decimal_separator = "," if "," in mantissa else "." if "." in mantissa else None
    decimal_places = len(mantissa.split(decimal_separator, 1)[1]) if decimal_separator else 0
    numeric = float(mantissa.replace(",", "."))
    exponent = match.group(2)
    if exponent is not None:
        numeric *= 10 ** int(exponent)
        number_format = "0" if decimal_places == 0 else f"0.{'0' * decimal_places}"
        return numeric, number_format

    number_format = "0" if decimal_places == 0 else f"0.{'0' * decimal_places}"
    return numeric, number_format


def _number_format_from_text(value) -> str | None:
    parsed = _numeric_value_and_format(value)
    return parsed[1] if parsed else None


def _number_formats_from_source(value) -> list[str]:
    if value is None or pd.isna(value):
        return []
    formats = []
    for match in NUMBER_IN_TEXT.finditer(str(value)):
        number_text = match.group(1)
        number_format = _number_format_from_text(number_text)
        if number_format:
            formats.append(number_format)
    return formats


def _apply_numeric_format_to_column(
    worksheet,
    df: pd.DataFrame,
    column_name: str,
    source_column: str | None = None,
    source_number_index: int = 0,
) -> None:
    if column_name not in df.columns:
        return

    column_index = list(df.columns).index(column_name) + 1
    for row_index, value in enumerate(df[column_name], start=2):
        parsed = _numeric_value_and_format(value)
        if parsed is None and not pd.isna(value):
            try:
                parsed = (float(value), "0")
            except (TypeError, ValueError):
                parsed = None
        if parsed is None:
            continue

        numeric, number_format = parsed
        if source_column and source_column in df.columns:
            source_formats = _number_formats_from_source(df[source_column].iloc[row_index - 2])
            if source_formats:
                number_format = source_formats[min(source_number_index, len(source_formats) - 1)]

        cell = worksheet.cell(row=row_index, column=column_index)
        cell.value = numeric
        cell.number_format = number_format


def _format_numeric_results_sheet(writer: pd.ExcelWriter, df: pd.DataFrame) -> None:
    worksheet = writer.sheets["results_extract"]
    direct_numeric_text_columns = [
        "variacao_percentual",
        "quantidade_adicionada",
        "recuperacao_percentual",
    ]
    for column in direct_numeric_text_columns:
        _apply_numeric_format_to_column(worksheet, df, column)

    source_mapped_columns = [
        ("resultado_tratado", "resultado", 0),
        ("ld_minimo", "ld_original", 0),
        ("ld_maximo", "ld_original", 1),
        ("lq_minimo", "lq_original", 0),
        ("lq_maximo", "lq_original", 1),
        ("incerteza_valor", "incerteza_original", 0),
        ("faixa_aceitacao_minimo", "faixa_aceitacao_original", 0),
        ("faixa_aceitacao_maximo", "faixa_aceitacao_original", 1),
    ]
    for column, source, source_number_index in source_mapped_columns:
        _apply_numeric_format_to_column(worksheet, df, column, source, source_number_index)


def salvar(
    df: pd.DataFrame,
    output_path: Path,
    sample_df: pd.DataFrame | None = None,
    client_df: pd.DataFrame | None = None,
    output_sheets: list[str] | None = None,
    classification_audit_df: pd.DataFrame | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ext = output_path.suffix.lower()
    sheets_to_write = output_sheets or ["results_extract", "sample", "client", "validation_errors"]
    validation_errors = validate_outputs(df, sample_df, client_df, sheets_to_write).get("results_extract", pd.DataFrame())

    if ext == ".csv":
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        if not validation_errors.empty:
            validation_errors.to_csv(
                output_path.with_name(f"{output_path.stem}_validation_errors.csv"),
                index=False,
                encoding="utf-8-sig",
            )
    elif ext == ".json":
        df.to_json(output_path, orient="records", force_ascii=False, indent=2)
        if not validation_errors.empty:
            validation_errors.to_json(
                output_path.with_name(f"{output_path.stem}_validation_errors.json"),
                orient="records",
                force_ascii=False,
                indent=2,
            )
    else:
        with pd.ExcelWriter(output_path) as writer:
            for sheet_name in sheets_to_write:
                if sheet_name == "results_extract":
                    df.to_excel(writer, sheet_name="results_extract", index=False)
                    _format_numeric_results_sheet(writer, df)
                elif sheet_name == "sample" and sample_df is not None:
                    sample_df.to_excel(writer, sheet_name="sample", index=False)
                elif sheet_name == "client" and client_df is not None:
                    client_df.to_excel(writer, sheet_name="client", index=False)
                elif sheet_name == "classification_audit" and classification_audit_df is not None:
                    classification_audit_df.to_excel(writer, sheet_name="classification_audit", index=False)
                elif sheet_name == "validation_errors":
                    validation_errors.to_excel(writer, sheet_name="validation_errors", index=False)
