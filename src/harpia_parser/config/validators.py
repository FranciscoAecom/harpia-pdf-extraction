import re
from typing import Iterable

import pandas as pd

from ..constants import (
    CLIENT_COLUMNS,
    CONFORMITY_STATEMENT_COLUMNS,
    GENERAL_CONSIDERATIONS_COLUMNS,
    LAYOUT_FIELD_KEYS,
    NOTES_COLUMNS,
    PACKAGING_PRESERVATIVES_COLUMNS,
    RESULTS_EXTRACT_COLUMNS,
    SAMPLE_COLUMNS,
    VALIDATION_KEY_COLUMNS,
)
from .common import is_empty_marker, normalize_token, parse_attrs
from .reader import TaxonomyWorkbook


EXPECTED_COLUMNS = {
    "item_taxonomia": {"id", "id_taxonomia", "nome"},
    "template": {"id", "id_item_taxonomia", "regex", "ativo"},
    "item_template": {"id", "id_template", "schema", "campo", "regex", "coluna_origem", "tipo_registro"},
    "schema": {"id", "id_item_taxonomia", "nome", "is_serial"},
    "item_schema": {"id", "id_schema", "schema", "campo", "tipo", "nulo"},
}

KNOWN_ITEM_TEMPLATE_SCHEMAS = {
    "template_required",
    "template_positive",
    "template_negative",
    "template_detection",
    "metadata",
    "sample",
    "client",
    "packaging_preservatives",
    "notes",
    "general_considerations",
    "conformity_statement",
    "validation_key",
    "layout",
    "header_alias",
    "category_type",
    "category_alias",
    "subcategory_alias",
    "continuation",
}


def validate_raw_taxonomy(workbook: TaxonomyWorkbook) -> None:
    frames = {
        "item_taxonomia": workbook.item_taxonomia,
        "template": workbook.template,
        "item_template": workbook.item_template,
        "schema": workbook.schema,
        "item_schema": workbook.item_schema,
    }

    for sheet_name, required_columns in EXPECTED_COLUMNS.items():
        df = frames[sheet_name]
        existing_columns = {str(column) for column in df.columns}
        missing = sorted(required_columns - existing_columns)
        if missing:
            raise ValueError(f"Aba {sheet_name} sem colunas obrigatorias: {missing}")
        if df.empty:
            raise ValueError(f"Aba {sheet_name} esta vazia.")

    _validate_unique_ids("item_taxonomia", workbook.item_taxonomia)
    _validate_unique_ids("template", workbook.template)
    _validate_unique_ids("item_template", workbook.item_template)
    _validate_unique_ids("schema", workbook.schema)
    _validate_unique_ids("item_schema", workbook.item_schema)
    _validate_foreign_keys(workbook)
    _validate_known_schemas(workbook.item_template)
    _validate_template_detection_rules(workbook.item_template)
    _validate_layout_fields(workbook)
    _validate_boolean_like_values(workbook)
    _validate_regexes(workbook)


def validate_output_model(sheet_name: str, df_model: pd.DataFrame, expected_columns: list[str]) -> None:
    if df_model.empty:
        raise ValueError(f"Aba obrigatoria ausente ou vazia na taxonomy: {sheet_name}")
    if "campo" not in df_model.columns:
        raise ValueError(f"Aba {sheet_name} nao contem a coluna obrigatoria 'campo'.")

    actual_columns = df_model["campo"].dropna().astype(str).tolist()
    missing = [column for column in expected_columns if column not in actual_columns]
    extra = [column for column in actual_columns if column not in expected_columns]
    wrong_order = not missing and not extra and actual_columns != expected_columns

    if missing or extra or wrong_order:
        details = []
        if missing:
            details.append(f"faltando={missing}")
        if extra:
            details.append(f"extras={extra}")
        if wrong_order:
            details.append("ordem diferente do codigo")
        raise ValueError(f"Modelo de saida divergente em {sheet_name}: {'; '.join(details)}")


def validate_detection_sources(sheet_name: str, df: pd.DataFrame) -> None:
    if df.empty or "source" not in df.columns:
        return

    sources = df["source"].fillna("text").astype(str).str.strip().str.lower()
    invalid_sources = sorted({source for source in sources if source != "text"})
    if invalid_sources:
        raise ValueError(
            f"Aba {sheet_name} contem source invalido para classificacao: {invalid_sources}. "
            "Use somente source='text'."
        )


def validate_boolean_columns(sheet_name: str, df: pd.DataFrame) -> None:
    for column in {"ativo", "obrigatorio", "extrair_subcategoria"} & {str(column) for column in df.columns}:
        if not pd.api.types.is_bool_dtype(df[column]):
            raise ValueError(
                f"Aba {sheet_name} contem valores nao booleanos na coluna '{column}'. "
                "Use booleano verdadeiro/falso no Excel."
            )


def validate_template_ids(sheet_name: str, df: pd.DataFrame, template_ids: set[str]) -> None:
    if df.empty or "template_id" not in df.columns:
        return

    values = df["template_id"].fillna("").astype(str).str.strip()
    invalid_scope = sorted({value for value in values if not value or value == "*"})
    unknown = sorted({value for value in values if value and value != "*" and value not in template_ids})

    details = []
    if invalid_scope:
        details.append(f"template_id vazio/coringa={invalid_scope}")
    if unknown:
        details.append(f"template_id nao cadastrado={unknown}")
    if details:
        raise ValueError(f"Aba {sheet_name} contem vinculo de template invalido: {'; '.join(details)}")


def validate_contract_frames(frames: dict[str, pd.DataFrame], template_ids: set[str]) -> None:
    validate_output_model("results_extract", frames["results_extract_model"], RESULTS_EXTRACT_COLUMNS)
    validate_output_model("sample", frames["sample_output_model"], SAMPLE_COLUMNS)
    validate_output_model("client", frames["client_output_model"], CLIENT_COLUMNS)
    validate_output_model(
        "packaging_preservatives",
        frames["packaging_preservatives_model"],
        PACKAGING_PRESERVATIVES_COLUMNS,
    )
    validate_output_model("notes", frames["notes_model"], NOTES_COLUMNS)
    validate_output_model(
        "general_considerations",
        frames["general_considerations_model"],
        GENERAL_CONSIDERATIONS_COLUMNS,
    )
    validate_output_model(
        "conformity_statement",
        frames["conformity_statement_model"],
        CONFORMITY_STATEMENT_COLUMNS,
    )
    validate_output_model("validation_key", frames["validation_key_model"], VALIDATION_KEY_COLUMNS)
    validate_detection_sources("template_rules", frames["template_rules"])

    for sheet_name, df in {
        "templates": frames["templates"],
        "template_rules": frames["template_rules"],
        "output_tabs": frames["output_tabs"],
        "metadata_text_rules": frames["metadata_text_rules"],
        "client_text_rules": frames["client_text_rules"],
        "packaging_preservatives_rules": frames["packaging_preservatives_rules"],
        "notes_rules": frames["notes_rules"],
        "general_considerations_rules": frames["general_considerations_rules"],
        "conformity_statement_rules": frames["conformity_statement_rules"],
        "validation_key_rules": frames["validation_key_rules"],
        "sample_text_rules": frames["sample_text_rules"],
        "category_type_rules": frames["category_type_rules"],
        "category_alias_rules": frames["category_alias_rules"],
        "subcategory_alias_rules": frames["subcategory_alias_rules"],
        "table_layouts": frames["table_layouts"],
        "header_alias_rules": frames["header_alias_rules"],
        "continuation_rules": frames["continuation_rules"],
        "results_extract_model": frames["results_extract_model"],
        "sample_output_model": frames["sample_output_model"],
        "client_output_model": frames["client_output_model"],
        "packaging_preservatives_model": frames["packaging_preservatives_model"],
        "notes_model": frames["notes_model"],
        "general_considerations_model": frames["general_considerations_model"],
        "conformity_statement_model": frames["conformity_statement_model"],
        "validation_key_model": frames["validation_key_model"],
    }.items():
        validate_boolean_columns(sheet_name, df)
        validate_template_ids(sheet_name, df, template_ids)


def _validate_unique_ids(sheet_name: str, df: pd.DataFrame) -> None:
    duplicated = df["id"][df["id"].duplicated()].dropna().tolist()
    if duplicated:
        raise ValueError(f"Aba {sheet_name} contem ids duplicados: {duplicated}")


def _validate_foreign_keys(workbook: TaxonomyWorkbook) -> None:
    taxonomy_ids = _ids(workbook.item_taxonomia)
    template_ids = _ids(workbook.template)
    schema_ids = _ids(workbook.schema)
    schema_names = set(workbook.schema["nome"].dropna().astype(str))

    _assert_known_values("template.id_item_taxonomia", workbook.template["id_item_taxonomia"], taxonomy_ids)
    _assert_known_values("schema.id_item_taxonomia", workbook.schema["id_item_taxonomia"], taxonomy_ids)
    _assert_known_values("item_template.id_template", workbook.item_template["id_template"], template_ids)
    _assert_known_values("item_schema.id_schema", workbook.item_schema["id_schema"], schema_ids)
    _assert_known_values("item_schema.schema", workbook.item_schema["schema"].astype(str), schema_names)

    schema_name_by_id = dict(zip(workbook.schema["id"], workbook.schema["nome"], strict=False))
    mismatches = []
    for _, row in workbook.item_schema.iterrows():
        expected = schema_name_by_id.get(row["id_schema"])
        actual = row["schema"]
        if expected is not None and str(expected) != str(actual):
            mismatches.append(f"id_schema={row['id_schema']} esperado={expected} informado={actual}")
    if mismatches:
        raise ValueError(f"Aba item_schema contem vinculos inconsistentes: {mismatches[:10]}")


def _validate_known_schemas(df_item_template: pd.DataFrame) -> None:
    values = set(df_item_template["schema"].dropna().astype(str))
    unknown = sorted(values - KNOWN_ITEM_TEMPLATE_SCHEMAS)
    if unknown:
        raise ValueError(f"Aba item_template contem schemas desconhecidos: {unknown}")


def _validate_template_detection_rules(df_item_template: pd.DataFrame) -> None:
    rows = df_item_template[df_item_template["schema"].astype(str) == "template_detection"]
    invalid = []
    for _, row in rows.iterrows():
        attrs = parse_attrs(row.get("coluna_origem"))
        rule_type = normalize_token(attrs.get("rule_type"))
        if rule_type not in {"required", "positive", "negative"}:
            invalid.append(row.get("id"))
    if invalid:
        raise ValueError(
            "Aba item_template/template_detection contem rule_type invalido em coluna_origem "
            f"nos ids: {invalid[:10]}. Use required, positive ou negative."
        )


def _validate_layout_fields(workbook: TaxonomyWorkbook) -> None:
    result_fields = set(
        workbook.item_schema[workbook.item_schema["schema"].astype(str) == "results_extract"]["campo"]
        .dropna()
        .astype(str)
    )
    valid_layout_fields = {field.removesuffix("_col") for field in LAYOUT_FIELD_KEYS}
    layout_output_field = {
        "unidade": "acm_unidade",
    }

    layout_rows = workbook.item_template[workbook.item_template["schema"].astype(str) == "layout"]
    layout_fields = set(layout_rows["campo"].dropna().astype(str))
    unknown_layout_fields = sorted(layout_fields - valid_layout_fields)
    missing_output_fields = sorted({
        field
        for field in layout_fields
        if layout_output_field.get(field, field) not in result_fields
    })
    if unknown_layout_fields:
        raise ValueError(f"Aba item_template/layout contem campos desconhecidos: {unknown_layout_fields}")
    if missing_output_fields:
        raise ValueError(f"Aba item_template/layout aponta campos ausentes em results_extract: {missing_output_fields}")

    header_rows = workbook.item_template[workbook.item_template["schema"].astype(str) == "header_alias"]
    header_fields = set(header_rows["campo"].dropna().astype(str))
    allowed_header_fields = result_fields | valid_layout_fields | {"parameter"}
    unknown_header_fields = sorted(header_fields - allowed_header_fields)
    if unknown_header_fields:
        raise ValueError(f"Aba item_template/header_alias contem campos sem saida correspondente: {unknown_header_fields}")


def _validate_boolean_like_values(workbook: TaxonomyWorkbook) -> None:
    for sheet_name, df, column in [
        ("template", workbook.template, "ativo"),
        ("schema", workbook.schema, "is_serial"),
    ]:
        invalid = _invalid_bool_values(df[column])
        if invalid:
            raise ValueError(f"Aba {sheet_name} contem valores booleanos invalidos em {column}: {invalid}")

    invalid_nulo = sorted({
        str(value)
        for value in workbook.item_schema["nulo"].dropna()
        if normalize_token(value) not in {"sim", "nao", "false", "falso", "true", "verdadeiro"}
    })
    if invalid_nulo:
        raise ValueError(f"Aba item_schema contem valores invalidos em nulo: {invalid_nulo}")


def _validate_regexes(workbook: TaxonomyWorkbook) -> None:
    _validate_regex_column("template.regex", workbook.template["regex"])

    regex_rows = workbook.item_template[
        ~workbook.item_template["schema"].astype(str).isin({"layout"})
    ]
    errors: list[str] = []
    for _, row in regex_rows.iterrows():
        value = row["regex"]
        if is_empty_marker(value):
            continue
        try:
            re.compile(str(value), re.IGNORECASE)
        except re.error as exc:
            errors.append(f"id={row['id']} schema={row['schema']} campo={row['campo']}: {exc}")
    if errors:
        raise ValueError(f"Aba item_template contem regex invalida: {errors[:10]}")

    for _, row in workbook.item_template.iterrows():
        attrs = parse_attrs(row.get("coluna_origem"))
        if (
            "prioridade" in attrs
            and not is_empty_marker(attrs["prioridade"])
            and not re.fullmatch(r"\d+(?:[,.]0+)?", str(attrs["prioridade"]).strip())
        ):
            raise ValueError(f"Aba item_template id={row['id']} contem prioridade invalida em coluna_origem.")


def _validate_regex_column(label: str, values: pd.Series) -> None:
    errors = []
    for excel_row_number, value in enumerate(values, start=2):
        if is_empty_marker(value):
            continue
        try:
            re.compile(str(value), re.IGNORECASE)
        except re.error as exc:
            errors.append(f"linha={excel_row_number}: {exc}")
    if errors:
        raise ValueError(f"{label} contem regex invalida: {errors[:10]}")


def _ids(df: pd.DataFrame) -> set:
    return set(df["id"].dropna())


def _assert_known_values(label: str, values: Iterable, known: set) -> None:
    unknown = sorted({value for value in values if not pd.isna(value) and value not in known})
    if unknown:
        raise ValueError(f"{label} contem referencias inexistentes: {unknown}")


def _invalid_bool_values(values: pd.Series) -> list[str]:
    invalid = []
    accepted = {"true", "verdadeiro", "sim", "yes", "1", "false", "falso", "nao", "não", "no", "0"}
    for value in values.dropna():
        text = str(value).strip().lower()
        if text not in accepted:
            invalid.append(str(value))
    return sorted(set(invalid))
