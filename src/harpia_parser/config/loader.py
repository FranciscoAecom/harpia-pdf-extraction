import logging
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Pattern

import pandas as pd

from ..constants import LAYOUT_FIELD_KEYS
from ..utils import resolve_path
from .common import float_value, int_value, value_or_none
from .mapper import map_taxonomy_to_runtime_frames
from .reader import read_taxonomy_workbook
from .validators import validate_contract_frames, validate_raw_taxonomy


log = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    taxonomy_path: Path
    df_templates: pd.DataFrame
    df_category_type_rules: pd.DataFrame
    df_metadata_text_rules: pd.DataFrame
    df_category_alias_rules: pd.DataFrame
    df_subcategory_alias_rules: pd.DataFrame
    df_sample_text_rules: pd.DataFrame
    df_client_text_rules: pd.DataFrame
    df_packaging_preservatives_rules: pd.DataFrame
    df_notes_rules: pd.DataFrame
    df_general_considerations_rules: pd.DataFrame
    df_conformity_statement_rules: pd.DataFrame
    df_validation_key_rules: pd.DataFrame
    df_revision_reason_rules: pd.DataFrame
    df_section_discovery_ignore_rules: pd.DataFrame
    df_results_extract_model: pd.DataFrame
    df_sample_output_model: pd.DataFrame
    df_client_output_model: pd.DataFrame
    df_packaging_preservatives_model: pd.DataFrame
    df_notes_model: pd.DataFrame
    df_general_considerations_model: pd.DataFrame
    df_conformity_statement_model: pd.DataFrame
    df_validation_key_model: pd.DataFrame
    df_revision_reason_model: pd.DataFrame
    df_duplicate_audit_model: pd.DataFrame
    df_section_extraction_audit_model: pd.DataFrame
    df_field_extraction_audit_model: pd.DataFrame
    df_template_rules: pd.DataFrame
    df_output_tabs: pd.DataFrame
    df_table_extraction_rules: pd.DataFrame
    df_header_alias_rules: pd.DataFrame
    df_continuation_rules: pd.DataFrame
    templates: dict[str, dict[str, Any]]
    category_type_rules: list[dict[str, Any]]
    metadata_rules: list[dict[str, Any]]
    category_alias_rules: list[dict[str, Any]]
    subcategory_alias_rules: list[dict[str, Any]]
    table_layouts: dict[str, dict[str, int | None]]
    header_alias_rules: list[dict[str, Any]]
    continuation_rules: list[dict[str, str | Pattern[str]]]
    template_rules: list[dict[str, Any]]
    output_tabs: dict[str, list[str]]


def _row_to_str_dict(row: pd.Series) -> dict[str, Any]:
    return {str(key): value for key, value in row.dropna().items()}


def _is_disabled(value: Any) -> bool:
    return value is False or str(value).strip().lower() in {"false", "0", "nao", "não", "nÃ£o", "nÃƒÂ£o"}


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


def _build_category_alias_rules(df_category_alias_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []

    for _, row in df_category_alias_rules.iterrows():
        padrao = value_or_none(row, "padrao_regex")
        categoria = value_or_none(row, "categoria")
        if pd.isna(padrao) or pd.isna(categoria):
            continue
        rules.append({
            "regex": re.compile(str(padrao), re.IGNORECASE),
            "categoria": categoria,
            "subcategoria": value_or_none(row, "subcategoria"),
            "local": value_or_none(row, "local") or "laboratorio",
        })
    return rules


def _build_subcategory_alias_rules(df_subcategory_alias_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if df_subcategory_alias_rules.empty:
        return rules

    source = df_subcategory_alias_rules.copy()
    if "prioridade" in source.columns:
        source = source.sort_values("prioridade", na_position="last")

    for _, row in source.iterrows():
        padrao = value_or_none(row, "padrao_regex")
        categoria = value_or_none(row, "categoria")
        if padrao is None or categoria is None:
            continue
        rules.append({
            "regex": re.compile(str(padrao), re.IGNORECASE),
            "categoria": categoria,
            "subcategoria": value_or_none(row, "subcategoria"),
            "tipo_registro": str(value_or_none(row, "tipo_registro") or "AMOSTRA").strip().upper(),
            "local": value_or_none(row, "local") or "laboratorio",
        })
    return rules


def _build_category_type_rules(df_category_type_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for _, row in df_category_type_rules.iterrows():
        padrao = value_or_none(row, "padrao_regex")
        if padrao is None:
            continue
        rules.append({
            "regex": re.compile(str(padrao), re.IGNORECASE),
            "categoria": value_or_none(row, "categoria"),
            "tipo_registro": value_or_none(row, "tipo_registro"),
            "extrair_subcategoria": bool(value_or_none(row, "extrair_subcategoria")),
        })
    return rules


def _build_metadata_rules(df_metadata_text_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for _, row in df_metadata_text_rules.iterrows():
        regex = value_or_none(row, "regex")
        campo = value_or_none(row, "campo")
        if regex is None or campo is None:
            continue
        rules.append({
            "campo": campo,
            "regex": re.compile(str(regex), re.IGNORECASE),
        })
    return rules


def _build_table_layouts(df_table_extraction_rules: pd.DataFrame) -> dict[str, dict[str, int | None]]:
    layouts: dict[str, dict[str, int | None]] = {}
    if df_table_extraction_rules.empty:
        return layouts

    for _, row in df_table_extraction_rules.iterrows():
        tipo = str(value_or_none(row, "tipo_registro") or "").strip().upper()
        campo = str(value_or_none(row, "campo") or "").strip()
        value = value_or_none(row, "coluna_origem")
        if not tipo or not campo or value is None:
            continue
        key = campo if campo.endswith("_col") else f"{campo}_col"
        if key not in LAYOUT_FIELD_KEYS:
            continue
        layout = layouts.setdefault(tipo, {field: None for field in LAYOUT_FIELD_KEYS})
        layout[key] = int_value(value)
    return layouts


def _build_header_alias_rules(df_header_alias_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if df_header_alias_rules.empty:
        return rules

    for _, row in df_header_alias_rules.iterrows():
        campo = str(value_or_none(row, "campo") or "").strip()
        pattern = value_or_none(row, "header_regex")
        if not campo or pattern is None:
            continue
        field = campo if campo == "parameter" or campo.endswith("_col") else f"{campo}_col"
        if field != "parameter" and field not in LAYOUT_FIELD_KEYS:
            continue
        rules.append({
            "field": field,
            "regex": re.compile(str(pattern), re.IGNORECASE),
            "descricao": value_or_none(row, "descricao"),
        })
    return rules


def _build_continuation_rules(df_continuation_rules: pd.DataFrame) -> list[dict[str, str | Pattern[str]]]:
    if df_continuation_rules.empty:
        return []

    rules: list[dict[str, str | Pattern[str]]] = []
    for _, row in df_continuation_rules.iterrows():
        tipo = str(value_or_none(row, "tipo_registro") or "").strip().upper()
        pattern = value_or_none(row, "continuation_regex")
        if not tipo or pd.isna(pattern):
            continue
        rules.append({"tipo_registro": tipo, "regex": re.compile(str(pattern), re.IGNORECASE)})
    return rules


def _build_templates(df_templates: pd.DataFrame) -> dict[str, dict[str, Any]]:
    templates: dict[str, dict[str, Any]] = {}
    if df_templates.empty:
        return templates

    for _, row in df_templates.iterrows():
        if _is_disabled(value_or_none(row, "ativo")):
            continue
        template_id = str(value_or_none(row, "template_id") or "").strip()
        if not template_id:
            continue
        template = _row_to_str_dict(row)
        template["template_id"] = template_id
        template["prioridade"] = int_value(value_or_none(row, "prioridade"), default=999)
        template["score_minimo"] = float_value(value_or_none(row, "score_minimo"), default=0.0)
        templates[template_id] = template
    return templates


def _build_template_rules(df_template_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if df_template_rules.empty:
        return rules

    for _, row in df_template_rules.iterrows():
        if _is_disabled(value_or_none(row, "ativo")):
            continue

        template_id = str(value_or_none(row, "template_id") or "").strip()
        rule_type = str(value_or_none(row, "rule_type") or "").strip().lower()
        source = str(value_or_none(row, "source") or "text").strip().lower()
        pattern = value_or_none(row, "padrao_regex")
        if not template_id or rule_type not in {"required", "positive", "negative"} or pattern is None:
            continue

        peso = value_or_none(row, "peso")
        rules.append({
            "template_id": template_id,
            "rule_type": rule_type,
            "source": source,
            "regex": re.compile(str(pattern), re.IGNORECASE),
            "peso": float_value(peso, default=0.0),
            "descricao": value_or_none(row, "descricao"),
        })

    return rules


def _build_output_tabs(df_output_tabs: pd.DataFrame) -> dict[str, list[str]]:
    if df_output_tabs.empty:
        return {}

    rules = df_output_tabs.copy()
    if "ativo" in rules.columns:
        rules = rules[~rules["ativo"].map(_is_disabled)]
    if "ordem" in rules.columns:
        rules = rules.sort_values(["template_id", "ordem"], na_position="last")

    output_tabs: dict[str, list[str]] = {}
    for _, row in rules.iterrows():
        template_id = str(value_or_none(row, "template_id") or "").strip()
        sheet_name = str(value_or_none(row, "sheet_name") or "").strip()
        if not template_id or not sheet_name:
            continue
        output_tabs.setdefault(template_id, []).append(sheet_name)
    return output_tabs


def output_tabs_for_template(config: PipelineConfig, template_id: str) -> list[str]:
    return config.output_tabs.get(template_id) or [
        "results_extract",
        "sample",
        "client",
        "packaging_preservatives",
        "notes",
        "general_considerations",
        "conformity_statement",
        "validation_key",
        "revision_reason",
        "table_extraction_audit",
        "section_extraction_audit",
        "field_extraction_audit",
        "classification_audit",
        "duplicate_audit",
        "validation_errors",
    ]


def filter_config_for_template(config: PipelineConfig, template_id: str) -> PipelineConfig:
    df_category_type_rules = _filter_rules_dataframe(config.df_category_type_rules, template_id)
    df_metadata_text_rules = _filter_rules_dataframe(config.df_metadata_text_rules, template_id)
    df_category_alias_rules = _filter_rules_dataframe(config.df_category_alias_rules, template_id)
    df_subcategory_alias_rules = _filter_rules_dataframe(config.df_subcategory_alias_rules, template_id)
    df_sample_text_rules = _filter_rules_dataframe(config.df_sample_text_rules, template_id)
    df_client_text_rules = _filter_rules_dataframe(config.df_client_text_rules, template_id)
    df_packaging_preservatives_rules = _filter_rules_dataframe(config.df_packaging_preservatives_rules, template_id)
    df_notes_rules = _filter_rules_dataframe(config.df_notes_rules, template_id)
    df_general_considerations_rules = _filter_rules_dataframe(config.df_general_considerations_rules, template_id)
    df_conformity_statement_rules = _filter_rules_dataframe(config.df_conformity_statement_rules, template_id)
    df_validation_key_rules = _filter_rules_dataframe(config.df_validation_key_rules, template_id)
    df_revision_reason_rules = _filter_rules_dataframe(config.df_revision_reason_rules, template_id)
    df_section_discovery_ignore_rules = _filter_rules_dataframe(config.df_section_discovery_ignore_rules, template_id)
    df_table_extraction_rules = _filter_rules_dataframe(config.df_table_extraction_rules, template_id)
    df_header_alias_rules = _filter_rules_dataframe(config.df_header_alias_rules, template_id)
    df_continuation_rules = _filter_rules_dataframe(config.df_continuation_rules, template_id)

    return replace(
        config,
        df_category_type_rules=df_category_type_rules,
        df_metadata_text_rules=df_metadata_text_rules,
        df_category_alias_rules=df_category_alias_rules,
        df_subcategory_alias_rules=df_subcategory_alias_rules,
        df_sample_text_rules=df_sample_text_rules,
        df_client_text_rules=df_client_text_rules,
        df_packaging_preservatives_rules=df_packaging_preservatives_rules,
        df_notes_rules=df_notes_rules,
        df_general_considerations_rules=df_general_considerations_rules,
        df_conformity_statement_rules=df_conformity_statement_rules,
        df_validation_key_rules=df_validation_key_rules,
        df_revision_reason_rules=df_revision_reason_rules,
        df_section_discovery_ignore_rules=df_section_discovery_ignore_rules,
        df_table_extraction_rules=df_table_extraction_rules,
        df_header_alias_rules=df_header_alias_rules,
        df_continuation_rules=df_continuation_rules,
        category_type_rules=_build_category_type_rules(df_category_type_rules),
        metadata_rules=_build_metadata_rules(df_metadata_text_rules),
        category_alias_rules=_build_category_alias_rules(df_category_alias_rules),
        subcategory_alias_rules=_build_subcategory_alias_rules(df_subcategory_alias_rules),
        table_layouts=_build_table_layouts(df_table_extraction_rules),
        header_alias_rules=_build_header_alias_rules(df_header_alias_rules),
        continuation_rules=_build_continuation_rules(df_continuation_rules),
    )


def load_config(base_dir: Path, taxonomy_file: str = "config/taxonomy.xlsx") -> PipelineConfig:
    taxonomy_path = resolve_path(base_dir, "TAXONOMY_FILE", taxonomy_file)
    log.info("Carregando taxonomy: %s", taxonomy_path)

    workbook = read_taxonomy_workbook(taxonomy_path)
    validate_raw_taxonomy(workbook)
    frames = map_taxonomy_to_runtime_frames(workbook)

    templates = _build_templates(frames["templates"])
    validate_contract_frames(frames, set(templates))

    category_type_rules = _build_category_type_rules(frames["category_type_rules"])
    metadata_rules = _build_metadata_rules(frames["metadata_text_rules"])
    category_alias_rules = _build_category_alias_rules(frames["category_alias_rules"])
    subcategory_alias_rules = _build_subcategory_alias_rules(frames["subcategory_alias_rules"])
    table_layouts = _build_table_layouts(frames["table_layouts"])
    header_alias_rules = _build_header_alias_rules(frames["header_alias_rules"])
    continuation_rules = _build_continuation_rules(frames["continuation_rules"])
    template_rules = _build_template_rules(frames["template_rules"])
    output_tabs = _build_output_tabs(frames["output_tabs"])

    log.info(
        "Taxonomy carregada: %d regras de secao, %d campos de metadata",
        len(frames["category_type_rules"]) + len(category_alias_rules) + len(subcategory_alias_rules),
        len(frames["metadata_text_rules"]),
    )

    return PipelineConfig(
        taxonomy_path=taxonomy_path,
        df_templates=frames["templates"],
        df_category_type_rules=frames["category_type_rules"],
        df_metadata_text_rules=frames["metadata_text_rules"],
        df_category_alias_rules=frames["category_alias_rules"],
        df_subcategory_alias_rules=frames["subcategory_alias_rules"],
        df_sample_text_rules=frames["sample_text_rules"],
        df_client_text_rules=frames["client_text_rules"],
        df_packaging_preservatives_rules=frames["packaging_preservatives_rules"],
        df_notes_rules=frames["notes_rules"],
        df_general_considerations_rules=frames["general_considerations_rules"],
        df_conformity_statement_rules=frames["conformity_statement_rules"],
        df_validation_key_rules=frames["validation_key_rules"],
        df_revision_reason_rules=frames["revision_reason_rules"],
        df_section_discovery_ignore_rules=frames["section_discovery_ignore_rules"],
        df_results_extract_model=frames["results_extract_model"],
        df_sample_output_model=frames["sample_output_model"],
        df_client_output_model=frames["client_output_model"],
        df_packaging_preservatives_model=frames["packaging_preservatives_model"],
        df_notes_model=frames["notes_model"],
        df_general_considerations_model=frames["general_considerations_model"],
        df_conformity_statement_model=frames["conformity_statement_model"],
        df_validation_key_model=frames["validation_key_model"],
        df_revision_reason_model=frames["revision_reason_model"],
        df_duplicate_audit_model=frames["duplicate_audit_model"],
        df_section_extraction_audit_model=frames["section_extraction_audit_model"],
        df_field_extraction_audit_model=frames["field_extraction_audit_model"],
        df_template_rules=frames["template_rules"],
        df_output_tabs=frames["output_tabs"],
        df_table_extraction_rules=frames["table_layouts"],
        df_header_alias_rules=frames["header_alias_rules"],
        df_continuation_rules=frames["continuation_rules"],
        templates=templates,
        category_type_rules=category_type_rules,
        metadata_rules=metadata_rules,
        category_alias_rules=category_alias_rules,
        subcategory_alias_rules=subcategory_alias_rules,
        table_layouts=table_layouts,
        header_alias_rules=header_alias_rules,
        continuation_rules=continuation_rules,
        template_rules=template_rules,
        output_tabs=output_tabs,
    )
