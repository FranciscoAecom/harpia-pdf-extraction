import logging
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Pattern

import pandas as pd

from ..constants import (
    CLIENT_COLUMNS,
    LAYOUT_FIELD_KEYS,
    RESULTS_EXTRACT_COLUMNS,
    SAMPLE_COLUMNS,
)
from ..utils import resolve_path


log = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    taxonomy_path: Path
    df_templates: pd.DataFrame
    df_sections: pd.DataFrame
    df_metadata: pd.DataFrame
    df_section_aliases: pd.DataFrame
    df_section_subcategory_aliases: pd.DataFrame
    df_sample_schema: pd.DataFrame
    df_client_schema: pd.DataFrame
    df_results_extract_schema: pd.DataFrame
    df_sample_output_schema: pd.DataFrame
    df_client_output_schema: pd.DataFrame
    df_template_detection_rules: pd.DataFrame
    df_output_sheets: pd.DataFrame
    df_result_layouts: pd.DataFrame
    df_continuation_rules: pd.DataFrame
    templates: dict[str, dict[str, Any]]
    section_config_rules: list[dict[str, Any]]
    metadata_rules: list[dict[str, Any]]
    section_rules: list[dict[str, Any]]
    section_subcategory_rules: list[dict[str, Any]]
    result_layouts: dict[str, dict[str, int | None]]
    continuation_rules: list[dict[str, str | Pattern[str]]]
    template_detection_rules: list[dict[str, Any]]
    output_sheets: dict[str, list[str]]


def _read_optional_sheet(excel: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    if sheet_name not in excel.sheet_names:
        return pd.DataFrame()
    return pd.read_excel(excel, sheet_name)


def _bool_value(value: Any, *, default: bool = True) -> bool:
    if pd.isna(value):
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "verdadeiro", "sim", "yes", "1"}:
        return True
    if text in {"false", "falso", "nao", "não", "no", "0"}:
        return False
    return bool(value)


def _coerce_bool_column(df: pd.DataFrame, column: str, *, default: bool = True) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    result = df.copy()
    result[column] = result[column].map(lambda value: _bool_value(value, default=default)).astype(bool)
    return result


def _coerce_bool_columns(df: pd.DataFrame, columns: set[str], *, default: bool = True) -> pd.DataFrame:
    result = df
    for column in columns & set(result.columns):
        result = _coerce_bool_column(result, column, default=default)
    return result


def _value_or_none(row: pd.Series, column: str) -> Any:
    value = row[column] if column in row.index else None
    return None if pd.isna(value) else value


def _row_to_str_dict(row: pd.Series) -> dict[str, Any]:
    return {str(key): value for key, value in row.dropna().items()}


def _is_disabled(value: Any) -> bool:
    return value is False or str(value).strip().lower() in {"false", "0", "nao", "não", "nÃ£o"}


def _filter_rules_dataframe(df: pd.DataFrame, template_id: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    filtered = df.copy()
    if "ativo" in filtered.columns:
        filtered = filtered[~filtered["ativo"].map(_is_disabled)]
    if "template_id" in filtered.columns:
        template_values = filtered["template_id"].fillna("").astype(str).str.strip()
        filtered = filtered[template_values == template_id]
    return filtered.copy()


def _validate_template_ids(sheet_name: str, df: pd.DataFrame, template_ids: set[str]) -> None:
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


def _validate_detection_sources(sheet_name: str, df: pd.DataFrame) -> None:
    if df.empty or "source" not in df.columns:
        return

    sources = df["source"].fillna("text").astype(str).str.strip().str.lower()
    invalid_sources = sorted({source for source in sources if source != "text"})
    if invalid_sources:
        raise ValueError(
            f"Aba {sheet_name} contem source invalido para classificacao: {invalid_sources}. "
            "Use somente source='text'."
        )


def _validate_boolean_columns(sheet_name: str, df: pd.DataFrame) -> None:
    for column in {"ativo", "obrigatorio", "extrair_subcategoria"} & set(df.columns):
        if not pd.api.types.is_bool_dtype(df[column]):
            raise ValueError(
                f"Aba {sheet_name} contem valores nao booleanos na coluna '{column}'. "
                "Use booleano verdadeiro/falso no Excel, nao textos como sim/nao."
            )


def _build_section_rules(df_section_aliases: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []

    for _, row in df_section_aliases.iterrows():
        padrao = _value_or_none(row, "padrao_regex")
        categoria = _value_or_none(row, "categoria")
        if pd.isna(padrao) or pd.isna(categoria):
            continue
        rules.append({
            "regex": re.compile(str(padrao), re.IGNORECASE),
            "categoria": categoria,
            "subcategoria": _value_or_none(row, "subcategoria"),
            "local": _value_or_none(row, "local") or "laboratorio",
        })
    return rules


def _build_section_subcategory_rules(df_section_subcategory_aliases: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if df_section_subcategory_aliases.empty:
        return rules

    source = df_section_subcategory_aliases.copy()
    if "prioridade" in source.columns:
        source = source.sort_values("prioridade", na_position="last")

    for _, row in source.iterrows():
        padrao = _value_or_none(row, "padrao_regex")
        categoria = _value_or_none(row, "categoria")
        if padrao is None or categoria is None:
            continue
        rules.append({
            "regex": re.compile(str(padrao), re.IGNORECASE),
            "categoria": categoria,
            "subcategoria": _value_or_none(row, "subcategoria"),
            "tipo_registro": str(_value_or_none(row, "tipo_registro") or "AMOSTRA").strip().upper(),
            "local": _value_or_none(row, "local") or "laboratorio",
        })
    return rules


def _build_section_config_rules(df_sections: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for _, row in df_sections.iterrows():
        padrao = _value_or_none(row, "padrao_regex")
        if padrao is None:
            continue
        rules.append({
            "regex": re.compile(str(padrao), re.IGNORECASE),
            "categoria": _value_or_none(row, "categoria"),
            "tipo_registro": _value_or_none(row, "tipo_registro"),
            "extrair_subcategoria": bool(_value_or_none(row, "extrair_subcategoria")),
        })
    return rules


def _build_metadata_rules(df_metadata: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for _, row in df_metadata.iterrows():
        regex = _value_or_none(row, "regex")
        campo = _value_or_none(row, "campo")
        if regex is None or campo is None:
            continue
        rules.append({
            "campo": campo,
            "regex": re.compile(str(regex), re.IGNORECASE),
        })
    return rules


def _build_result_layouts(df_result_layouts: pd.DataFrame) -> dict[str, dict[str, int | None]]:
    layouts: dict[str, dict[str, int | None]] = {}
    if df_result_layouts.empty:
        return layouts

    if {"campo", "coluna_origem"}.issubset(df_result_layouts.columns):
        for _, row in df_result_layouts.iterrows():
            tipo = str(_value_or_none(row, "tipo_registro") or "").strip().upper()
            campo = str(_value_or_none(row, "campo") or "").strip()
            value = _value_or_none(row, "coluna_origem")
            if not tipo or not campo or value is None:
                continue
            key = campo if campo.endswith("_col") else f"{campo}_col"
            if key not in LAYOUT_FIELD_KEYS:
                continue
            layout = layouts.setdefault(tipo, {field: None for field in LAYOUT_FIELD_KEYS})
            layout[key] = int(value)
        return layouts

    for _, row in df_result_layouts.iterrows():
        tipo = str(_value_or_none(row, "tipo_registro") or "").strip().upper()
        if not tipo:
            continue
        layout: dict[str, int | None] = {key: None for key in LAYOUT_FIELD_KEYS}
        for key in LAYOUT_FIELD_KEYS:
            value = _value_or_none(row, key)
            if value is not None:
                layout[key] = int(value)
        layouts[tipo] = layout
    return layouts


def _build_continuation_rules(df_continuation_rules: pd.DataFrame) -> list[dict[str, str | Pattern[str]]]:
    if df_continuation_rules.empty:
        return []

    rules: list[dict[str, str | Pattern[str]]] = []
    for _, row in df_continuation_rules.iterrows():
        tipo = str(_value_or_none(row, "tipo_registro") or "").strip().upper()
        pattern = _value_or_none(row, "continuation_regex")
        if not tipo or pd.isna(pattern):
            continue
        rules.append({"tipo_registro": tipo, "regex": re.compile(str(pattern), re.IGNORECASE)})
    return rules


def _build_templates(df_templates: pd.DataFrame) -> dict[str, dict[str, Any]]:
    templates: dict[str, dict[str, Any]] = {}
    if df_templates.empty:
        return templates

    id_column = "template_id" if "template_id" in df_templates.columns else "id_template"
    for _, row in df_templates.iterrows():
        if _is_disabled(_value_or_none(row, "ativo")):
            continue
        template_id = str(_value_or_none(row, id_column) or "").strip()
        if not template_id:
            continue
        template = _row_to_str_dict(row)
        template["template_id"] = template_id
        template["prioridade"] = int(_value_or_none(row, "prioridade") or 999)
        template["score_minimo"] = float(_value_or_none(row, "score_minimo") or 0)
        templates[template_id] = template
    return templates


def _validate_output_schema(sheet_name: str, df_schema: pd.DataFrame, expected_columns: list[str]) -> None:
    if df_schema.empty:
        raise ValueError(f"Aba obrigatoria ausente ou vazia na taxonomy: {sheet_name}")
    if "campo" not in df_schema.columns:
        raise ValueError(f"Aba {sheet_name} nao contem a coluna obrigatoria 'campo'.")

    actual_columns = df_schema["campo"].dropna().astype(str).tolist()
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
        raise ValueError(f"Schema divergente em {sheet_name}: {'; '.join(details)}")


def _schema_from_output_model(df_output_model: pd.DataFrame, schema_name: str) -> pd.DataFrame:
    columns = ["sheet", "ordem", "campo", "tipo_dado", "obrigatorio", "origem", "descricao"]
    if df_output_model.empty:
        return pd.DataFrame(columns=columns)

    schema = df_output_model[df_output_model["schema_origem"].astype(str) == schema_name].copy()
    if schema.empty:
        return pd.DataFrame(columns=columns)

    schema = schema.rename(columns={
        "sheet_name": "sheet",
        "ordem_campo": "ordem",
        "descricao_campo": "descricao",
    })
    schema = schema[columns]
    schema = schema.dropna(subset=["campo"]).drop_duplicates(subset=["campo"], keep="first")
    schema = _coerce_bool_column(schema, "obrigatorio", default=False)
    return schema.sort_values("ordem", na_position="last").reset_index(drop=True)


def _load_consolidated_frames(excel: pd.ExcelFile) -> dict[str, pd.DataFrame]:
    df_templates = _coerce_bool_column(_read_optional_sheet(excel, "templates"), "ativo")

    df_template_detection_rules = _read_optional_sheet(excel, "template_rules").rename(columns={
        "tipo_regra": "rule_type",
        "fonte": "source",
    })
    df_template_detection_rules = _coerce_bool_column(df_template_detection_rules, "ativo")

    df_output_model = _read_optional_sheet(excel, "output_model")
    if df_output_model.empty:
        df_output_sheets = pd.DataFrame(columns=["template_id", "theme_id", "sheet_name", "ordem", "ativo", "descricao"])
    else:
        output_columns = [
            "template_id",
            "theme_id",
            "sheet_name",
            "ordem_aba",
            "ativo_aba",
            "descricao_aba",
        ]
        df_output_sheets = (
            df_output_model[output_columns]
            .dropna(subset=["template_id", "sheet_name"])
            .drop_duplicates()
            .rename(columns={
                "ordem_aba": "ordem",
                "ativo_aba": "ativo",
                "descricao_aba": "descricao",
            })
        )
        df_output_sheets = _coerce_bool_column(df_output_sheets, "ativo")

    df_text_rules = _coerce_bool_column(_read_optional_sheet(excel, "text_extraction_rules"), "ativo")

    def text_rules(regra_origem: str, columns: list[str]) -> pd.DataFrame:
        if df_text_rules.empty:
            return pd.DataFrame(columns=columns)
        df = df_text_rules[df_text_rules["regra_origem"] == regra_origem].copy()
        df = df.rename(columns={"padrao_regex": "regex"})
        return df[[column for column in columns if column in df.columns]]

    df_metadata = text_rules("metadata_schema", ["template_id", "campo", "regex", "ativo"])
    df_client_schema = text_rules("client_schema", ["template_id", "campo", "regex", "descricao", "ativo"])
    df_sample_schema = text_rules("sample_schema", ["template_id", "campo", "regex", "ativo"])

    df_section_rules = _coerce_bool_columns(
        _read_optional_sheet(excel, "section_rules"),
        {"ativo", "extrair_subcategoria"},
    )

    def section_rules(regra_origem: str, columns: list[str]) -> pd.DataFrame:
        if df_section_rules.empty:
            return pd.DataFrame(columns=columns)
        df = df_section_rules[df_section_rules["regra_origem"] == regra_origem].copy()
        return df[[column for column in columns if column in df.columns]]

    df_sections = section_rules(
        "section_config",
        ["template_id", "padrao_regex", "categoria", "tipo_registro", "extrair_subcategoria", "ativo"],
    )
    df_section_aliases = section_rules(
        "section_aliases",
        ["template_id", "padrao_regex", "categoria", "subcategoria", "local", "ativo"],
    )
    df_section_subcategory_aliases = section_rules(
        "section_subcategory_aliases",
        [
            "template_id",
            "prioridade",
            "padrao_regex",
            "categoria",
            "subcategoria",
            "tipo_registro",
            "local",
            "ativo",
            "descricao",
        ],
    )

    df_result_layouts = _read_optional_sheet(excel, "table_extraction_rules")
    if not df_result_layouts.empty:
        df_result_layouts = df_result_layouts[df_result_layouts["regra_origem"] == "result_layouts"].copy()
        df_result_layouts = _coerce_bool_column(df_result_layouts, "ativo")
        df_result_layouts = df_result_layouts[["template_id", "tipo_registro", "campo", "coluna_origem", "ativo"]]

    df_continuation_rules = _read_optional_sheet(excel, "continuation_rules").rename(columns={
        "padrao_regex": "continuation_regex",
    })
    df_continuation_rules = _coerce_bool_column(df_continuation_rules, "ativo")
    if not df_continuation_rules.empty:
        df_continuation_rules = df_continuation_rules[
            ["template_id", "tipo_registro", "continuation_regex", "ativo"]
        ]

    return {
        "templates": df_templates,
        "section_config": df_sections,
        "metadata_schema": df_metadata,
        "section_aliases": df_section_aliases,
        "section_subcategory_aliases": df_section_subcategory_aliases,
        "sample_schema": df_sample_schema,
        "client_schema": df_client_schema,
        "results_extract_schema": _schema_from_output_model(df_output_model, "results_extract_schema"),
        "sample_output_schema": _schema_from_output_model(df_output_model, "sample_output_schema"),
        "client_output_schema": _schema_from_output_model(df_output_model, "client_output_schema"),
        "result_layouts": df_result_layouts,
        "continuation_rules": df_continuation_rules,
        "template_detection_rules": df_template_detection_rules,
        "output_sheets": df_output_sheets,
    }


def _load_taxonomy_frames(excel: pd.ExcelFile) -> dict[str, pd.DataFrame]:
    required_sheets = {"templates", "template_rules", "output_model", "text_extraction_rules", "table_extraction_rules"}
    missing = sorted(required_sheets - set(excel.sheet_names))
    if missing:
        raise ValueError(f"Taxonomia consolidada invalida. Abas obrigatorias ausentes: {missing}")
    return _load_consolidated_frames(excel)


def _build_template_detection_rules(df_template_detection_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if df_template_detection_rules.empty:
        return rules

    for _, row in df_template_detection_rules.iterrows():
        if _is_disabled(_value_or_none(row, "ativo")):
            continue

        template_id = str(_value_or_none(row, "template_id") or "").strip()
        rule_type = str(_value_or_none(row, "rule_type") or "").strip().lower()
        source = str(_value_or_none(row, "source") or "text").strip().lower()
        pattern = _value_or_none(row, "padrao_regex")
        if not template_id or rule_type not in {"required", "positive", "negative"} or pattern is None:
            continue

        peso = _value_or_none(row, "peso")
        rules.append({
            "template_id": template_id,
            "rule_type": rule_type,
            "source": source,
            "regex": re.compile(str(pattern), re.IGNORECASE),
            "peso": float(peso) if peso is not None else 0.0,
            "descricao": _value_or_none(row, "descricao"),
        })

    return rules


def _build_output_sheets(df_output_sheets: pd.DataFrame) -> dict[str, list[str]]:
    if df_output_sheets.empty:
        return {}

    rules = df_output_sheets.copy()
    if "ativo" in rules.columns:
        rules = rules[~rules["ativo"].map(_is_disabled)]
    if "ordem" in rules.columns:
        rules = rules.sort_values(["template_id", "ordem"], na_position="last")

    output_sheets: dict[str, list[str]] = {}
    for _, row in rules.iterrows():
        template_id = str(_value_or_none(row, "template_id") or "").strip()
        sheet_name = str(_value_or_none(row, "sheet_name") or "").strip()
        if not template_id or not sheet_name:
            continue
        output_sheets.setdefault(template_id, []).append(sheet_name)
    return output_sheets


def output_sheets_for_template(config: PipelineConfig, template_id: str) -> list[str]:
    return config.output_sheets.get(template_id) or [
        "results_extract",
        "sample",
        "client",
        "table_extraction_audit",
        "classification_audit",
        "validation_errors",
    ]


def filter_config_for_template(config: PipelineConfig, template_id: str) -> PipelineConfig:
    df_sections = _filter_rules_dataframe(config.df_sections, template_id)
    df_metadata = _filter_rules_dataframe(config.df_metadata, template_id)
    df_section_aliases = _filter_rules_dataframe(config.df_section_aliases, template_id)
    df_section_subcategory_aliases = _filter_rules_dataframe(config.df_section_subcategory_aliases, template_id)
    df_sample_schema = _filter_rules_dataframe(config.df_sample_schema, template_id)
    df_client_schema = _filter_rules_dataframe(config.df_client_schema, template_id)
    df_result_layouts = _filter_rules_dataframe(config.df_result_layouts, template_id)
    df_continuation_rules = _filter_rules_dataframe(config.df_continuation_rules, template_id)

    return replace(
        config,
        df_sections=df_sections,
        df_metadata=df_metadata,
        df_section_aliases=df_section_aliases,
        df_section_subcategory_aliases=df_section_subcategory_aliases,
        df_sample_schema=df_sample_schema,
        df_client_schema=df_client_schema,
        df_result_layouts=df_result_layouts,
        df_continuation_rules=df_continuation_rules,
        section_config_rules=_build_section_config_rules(df_sections),
        metadata_rules=_build_metadata_rules(df_metadata),
        section_rules=_build_section_rules(df_section_aliases),
        section_subcategory_rules=_build_section_subcategory_rules(df_section_subcategory_aliases),
        result_layouts=_build_result_layouts(df_result_layouts),
        continuation_rules=_build_continuation_rules(df_continuation_rules),
    )


def load_config(base_dir: Path, taxonomy_file: str = "config/taxonomy_config_consolidada_v1.xlsx") -> PipelineConfig:
    taxonomy_path = resolve_path(base_dir, "TAXONOMY_FILE", taxonomy_file)
    log.info("Carregando taxonomy: %s", taxonomy_path)

    excel = pd.ExcelFile(taxonomy_path)
    frames = _load_taxonomy_frames(excel)
    excel.close()
    df_templates = frames["templates"]
    df_sections = frames["section_config"]
    df_metadata = frames["metadata_schema"]
    df_section_aliases = frames["section_aliases"]
    df_section_subcategory_aliases = frames["section_subcategory_aliases"]
    df_sample_schema = frames["sample_schema"]
    df_client_schema = frames["client_schema"]
    df_results_extract_schema = frames["results_extract_schema"]
    df_sample_output_schema = frames["sample_output_schema"]
    df_client_output_schema = frames["client_output_schema"]
    df_result_layouts = frames["result_layouts"]
    df_continuation_rules = frames["continuation_rules"]
    df_template_detection_rules = frames["template_detection_rules"]
    df_output_sheets = frames["output_sheets"]

    _validate_output_schema("results_extract_schema", df_results_extract_schema, RESULTS_EXTRACT_COLUMNS)
    _validate_output_schema("sample_output_schema", df_sample_output_schema, SAMPLE_COLUMNS)
    _validate_output_schema("client_output_schema", df_client_output_schema, CLIENT_COLUMNS)

    section_config_rules = _build_section_config_rules(df_sections)
    metadata_rules = _build_metadata_rules(df_metadata)
    section_rules = _build_section_rules(df_section_aliases)
    section_subcategory_rules = _build_section_subcategory_rules(df_section_subcategory_aliases)
    result_layouts = _build_result_layouts(df_result_layouts)
    continuation_rules = _build_continuation_rules(df_continuation_rules)
    templates = _build_templates(df_templates)
    _validate_detection_sources("template_detection_rules", df_template_detection_rules)
    template_ids = set(templates)
    for sheet_name, df in {
        "templates": df_templates,
        "template_detection_rules": df_template_detection_rules,
        "output_sheets": df_output_sheets,
        "metadata_schema": df_metadata,
        "client_schema": df_client_schema,
        "sample_schema": df_sample_schema,
        "section_config": df_sections,
        "section_aliases": df_section_aliases,
        "section_subcategory_aliases": df_section_subcategory_aliases,
        "result_layouts": df_result_layouts,
        "continuation_rules": df_continuation_rules,
        "results_extract_schema": df_results_extract_schema,
        "sample_output_schema": df_sample_output_schema,
        "client_output_schema": df_client_output_schema,
    }.items():
        _validate_boolean_columns(sheet_name, df)
        _validate_template_ids(sheet_name, df, template_ids)
    template_detection_rules = _build_template_detection_rules(df_template_detection_rules)
    output_sheets = _build_output_sheets(df_output_sheets)

    log.info(
        "Taxonomy carregada: %d regras de secao, %d campos de metadata",
        len(df_sections) + len(section_rules) + len(section_subcategory_rules),
        len(df_metadata),
    )

    return PipelineConfig(
        taxonomy_path=taxonomy_path,
        df_templates=df_templates,
        df_sections=df_sections,
        df_metadata=df_metadata,
        df_section_aliases=df_section_aliases,
        df_section_subcategory_aliases=df_section_subcategory_aliases,
        df_sample_schema=df_sample_schema,
        df_client_schema=df_client_schema,
        df_results_extract_schema=df_results_extract_schema,
        df_sample_output_schema=df_sample_output_schema,
        df_client_output_schema=df_client_output_schema,
        df_template_detection_rules=df_template_detection_rules,
        df_output_sheets=df_output_sheets,
        df_result_layouts=df_result_layouts,
        df_continuation_rules=df_continuation_rules,
        templates=templates,
        section_config_rules=section_config_rules,
        metadata_rules=metadata_rules,
        section_rules=section_rules,
        section_subcategory_rules=section_subcategory_rules,
        result_layouts=result_layouts,
        continuation_rules=continuation_rules,
        template_detection_rules=template_detection_rules,
        output_sheets=output_sheets,
    )
