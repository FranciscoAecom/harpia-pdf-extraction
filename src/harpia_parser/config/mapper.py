from typing import Any

import pandas as pd

from .common import (
    bool_value,
    cell_or_none,
    float_value,
    int_value,
    is_empty_marker,
    normalize_tipo_registro,
    normalize_token,
    parse_attrs,
    parse_weight,
)
from .reader import TaxonomyWorkbook


OUTPUT_ORDER = {
    "results_extract": 1,
    "sample": 2,
    "client": 3,
    "packaging_preservatives": 4,
    "notes": 5,
    "general_considerations": 6,
    "conformity_statement": 7,
    "validation_key": 8,
    "revision_reason": 9,
    "table_extraction_audit": 10,
    "section_extraction_audit": 11,
    "field_extraction_audit": 12,
    "classification_audit": 13,
    "duplicate_audit": 14,
    "validation_errors": 15,
    "document_reconciliation_audit": 16,
}

CONFIG_ONLY_SCHEMAS = {
    "metadata",
    "template_detection",
    "category_alias",
    "category_type",
    "continuation",
    "header_alias",
    "layout",
    "subcategory_alias",
    "section_discovery_ignore",
}


def map_taxonomy_to_runtime_frames(workbook: TaxonomyWorkbook) -> dict[str, pd.DataFrame]:
    template_identities = _template_identities(workbook)
    df_templates = _map_templates(workbook, template_identities)
    base_items = _item_template_with_runtime_template_id(workbook.item_template, template_identities)

    return {
        "templates": df_templates,
        "category_type_rules": _section_subset(base_items, "category_type", [
            "template_id",
            "padrao_regex",
            "categoria",
            "tipo_registro",
            "extrair_subcategoria",
            "ativo",
        ]),
        "metadata_text_rules": _text_rules(base_items, "metadata"),
        "category_alias_rules": _section_subset(base_items, "category_alias", [
            "template_id",
            "padrao_regex",
            "categoria",
            "subcategoria",
            "local",
            "ativo",
        ]),
        "subcategory_alias_rules": _section_subset(base_items, "subcategory_alias", [
            "template_id",
            "prioridade",
            "padrao_regex",
            "categoria",
            "subcategoria",
            "tipo_registro",
            "local",
            "ativo",
            "descricao",
        ]),
        "sample_text_rules": _text_rules(base_items, "sample"),
        "client_text_rules": _text_rules(base_items, "client", include_description=True),
        "packaging_preservatives_rules": _text_rules(base_items, "packaging_preservatives", include_description=True),
        "notes_rules": _text_rules(base_items, "notes", include_description=True),
        "general_considerations_rules": _text_rules(base_items, "general_considerations", include_description=True),
        "conformity_statement_rules": _text_rules(base_items, "conformity_statement", include_description=True),
        "validation_key_rules": _text_rules(base_items, "validation_key", include_description=True),
        "revision_reason_rules": _text_rules(base_items, "revision_reason", include_description=True),
        "section_discovery_ignore_rules": _text_rules(base_items, "section_discovery_ignore", include_description=True),
        "results_extract_model": _fields_from_item_schema(workbook.item_schema, "results_extract"),
        "sample_output_model": _fields_from_item_schema(workbook.item_schema, "sample"),
        "client_output_model": _fields_from_item_schema(workbook.item_schema, "client"),
        "packaging_preservatives_model": _fields_from_item_schema(workbook.item_schema, "packaging_preservatives"),
        "notes_model": _fields_from_item_schema(workbook.item_schema, "notes"),
        "general_considerations_model": _fields_from_item_schema(workbook.item_schema, "general_considerations"),
        "conformity_statement_model": _fields_from_item_schema(workbook.item_schema, "conformity_statement"),
        "validation_key_model": _fields_from_item_schema(workbook.item_schema, "validation_key"),
        "revision_reason_model": _fields_from_item_schema(workbook.item_schema, "revision_reason"),
        "duplicate_audit_model": _fields_from_item_schema(workbook.item_schema, "duplicate_audit"),
        "section_extraction_audit_model": _fields_from_item_schema(workbook.item_schema, "section_extraction_audit"),
        "field_extraction_audit_model": _fields_from_item_schema(workbook.item_schema, "field_extraction_audit"),
        "table_layouts": _layout_rules(base_items),
        "header_alias_rules": _header_alias_rules(base_items),
        "continuation_rules": _continuation_rules(base_items),
        "template_rules": _template_detection_rules(workbook, base_items, template_identities),
        "output_tabs": _output_tabs(workbook.schema, df_templates),
    }


def _template_identities(workbook: TaxonomyWorkbook) -> dict[Any, dict[str, Any]]:
    taxonomy_by_id = {
        row["id"]: row
        for _, row in workbook.item_taxonomia.iterrows()
        if "id" in row.index
    }

    identities: dict[Any, dict[str, Any]] = {}
    for _, row in workbook.template.iterrows():
        taxonomy_row = taxonomy_by_id.get(row.get("id_item_taxonomia"))
        taxonomy_name = taxonomy_row.get("nome") if taxonomy_row is not None else None
        identities[row.get("id")] = _template_identity(row, taxonomy_name)
    return identities


def _template_identity(template_row: pd.Series, taxonomy_name: Any) -> dict[str, Any]:
    explicit_template_id = _optional_text(template_row, "template_id")
    explicit_theme_id = _optional_text(template_row, "theme_id")
    explicit_name = _optional_text(template_row, "nome")
    explicit_schema_ref = _optional_text(template_row, "schema_ref")

    token = normalize_token(taxonomy_name)
    version = int_value(template_row.get("id"), default=1)

    if explicit_template_id and explicit_theme_id:
        template_id = explicit_template_id
        theme_id = explicit_theme_id
    elif "agua" in token:
        theme_id = "laudo_agua"
        template_id = "template_laudo_agua_v1"
    else:
        theme_id = f"laudo_{token}" if token else f"laudo_{version}"
        template_id = f"template_{theme_id}_v{version}"

    return {
        "template_id": template_id,
        "theme_id": theme_id,
        "nome": explicit_name or ("Laudo analitico de agua" if theme_id == "laudo_agua" else str(taxonomy_name or theme_id).strip()),
        "schema_ref": explicit_schema_ref or "results_extract",
    }


def _map_templates(workbook: TaxonomyWorkbook, identities: dict[Any, dict[str, Any]]) -> pd.DataFrame:
    taxonomy_by_id = {
        row["id"]: row
        for _, row in workbook.item_taxonomia.iterrows()
        if "id" in row.index
    }

    rows: list[dict[str, Any]] = []
    for _, row in workbook.template.iterrows():
        taxonomy_row = taxonomy_by_id.get(row.get("id_item_taxonomia"))
        taxonomy_name = taxonomy_row.get("nome") if taxonomy_row is not None else None
        id_taxonomia = taxonomy_row.get("id_taxonomia") if taxonomy_row is not None else None
        rows.append({
            **identities[row.get("id")],
            "id_taxonomia": id_taxonomia,
            "nome_taxonomia": taxonomy_name,
            "versao_template": _optional_text(row, "versao_template"),
            "regex": row.get("regex"),
            "descricao": taxonomy_name,
            "prioridade": int_value(_optional_number(row, "prioridade", row.get("id") or 999), default=999),
            "score_minimo": float_value(_optional_number(row, "score_minimo", 80.0), default=80.0),
            "ativo": bool_value(row.get("ativo"), default=True),
        })
    return pd.DataFrame(rows)


def _item_template_with_runtime_template_id(
    df_item_template: pd.DataFrame,
    identities: dict[Any, dict[str, Any]],
) -> pd.DataFrame:
    result = df_item_template.copy()
    result["template_id"] = result["id_template"].map(
        lambda value: str((identities.get(value) or {}).get("template_id") or "")
    )
    result["ativo"] = True
    return result


def _text_rules(base_items: pd.DataFrame, schema_name: str, include_description: bool = False) -> pd.DataFrame:
    df = _by_schema(base_items, schema_name)
    if df.empty:
        columns = ["template_id", "campo", "regex", "ativo"]
        if include_description:
            columns.insert(3, "descricao")
        return pd.DataFrame(columns=columns)

    df = df[["template_id", "campo", "regex", "ativo"]].copy()
    if include_description:
        df["descricao"] = ""
        df = df[["template_id", "campo", "regex", "descricao", "ativo"]]
    return df


def _template_detection_rules(
    workbook: TaxonomyWorkbook,
    base_items: pd.DataFrame,
    identities: dict[Any, dict[str, Any]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rule_type_by_schema = {
        "template_required": "required",
        "template_positive": "positive",
        "template_negative": "negative",
    }

    for _, row in base_items[base_items["schema"].isin(rule_type_by_schema)].iterrows():
        rows.append({
            "template_id": row["template_id"],
            "rule_type": rule_type_by_schema[str(row["schema"])],
            "source": "text",
            "padrao_regex": row["regex"],
            "peso": parse_weight(row.get("coluna_origem")),
            "ativo": True,
            "descricao": "",
        })

    for _, row in _by_schema(base_items, "template_detection").iterrows():
        attrs = parse_attrs(row.get("coluna_origem"))
        rule_type = normalize_token(attrs.get("rule_type"))
        if rule_type not in {"required", "positive", "negative"}:
            continue
        rows.append({
            "template_id": row["template_id"],
            "rule_type": rule_type,
            "source": "text",
            "padrao_regex": row["regex"],
            "peso": parse_weight(row.get("coluna_origem")),
            "ativo": True,
            "descricao": "",
        })

    templates_with_detail_rules = {row["template_id"] for row in rows}
    for _, row in workbook.template.iterrows():
        identity = identities.get(row.get("id")) or {}
        template_id = str(identity.get("template_id") or "")
        pattern = row.get("regex")
        if template_id and template_id not in templates_with_detail_rules and not is_empty_marker(pattern):
            rows.append({
                "template_id": template_id,
                "rule_type": "positive",
                "source": "text",
                "padrao_regex": pattern,
                "peso": 80.0,
                "ativo": True,
                "descricao": "Regex geral do template",
            })
    return pd.DataFrame(rows)


def _section_subset(base_items: pd.DataFrame, schema_name: str, columns: list[str]) -> pd.DataFrame:
    section_rules = _section_rules(base_items)
    if section_rules.empty:
        return pd.DataFrame(columns=columns)
    df = section_rules[section_rules["regra_origem"] == schema_name].copy()
    return df[columns]


def _section_rules(base_items: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for schema_name in {"category_type", "category_alias", "subcategory_alias"}:
        for _, row in _by_schema(base_items, schema_name).iterrows():
            attrs = parse_attrs(row.get("coluna_origem"))
            rows.append({
                "regra_origem": schema_name,
                "template_id": row["template_id"],
                "prioridade": cell_or_none(attrs.get("prioridade")),
                "padrao_regex": row["regex"],
                "categoria": cell_or_none(attrs.get("categoria")) or row["campo"],
                "subcategoria": cell_or_none(attrs.get("subcategoria")),
                "tipo_registro": normalize_tipo_registro(row.get("tipo_registro")),
                "local": cell_or_none(attrs.get("local")) or "laboratorio",
                "extrair_subcategoria": bool_value(attrs.get("extrair_subcategoria"), default=False),
                "ativo": True,
                "descricao": "",
            })
    return pd.DataFrame(rows)


def _layout_rules(base_items: pd.DataFrame) -> pd.DataFrame:
    df = _by_schema(base_items, "layout")
    columns = ["template_id", "tipo_registro", "campo", "coluna_origem", "ativo"]
    if df.empty:
        return pd.DataFrame(columns=columns)

    result = df[columns].copy()
    result["tipo_registro"] = result["tipo_registro"].map(normalize_tipo_registro)
    return result


def _header_alias_rules(base_items: pd.DataFrame) -> pd.DataFrame:
    df = _by_schema(base_items, "header_alias")
    if df.empty:
        return pd.DataFrame(columns=["template_id", "campo", "header_regex", "ativo", "descricao"])

    result = df[["template_id", "campo", "regex", "ativo"]].copy()
    result = result.rename(columns={"regex": "header_regex"})
    result["descricao"] = ""
    return result


def _continuation_rules(base_items: pd.DataFrame) -> pd.DataFrame:
    df = _by_schema(base_items, "continuation")
    if df.empty:
        return pd.DataFrame(columns=["template_id", "tipo_registro", "continuation_regex", "ativo"])

    result = df[["template_id", "tipo_registro", "regex", "ativo"]].copy()
    result = result.rename(columns={"regex": "continuation_regex"})
    result["tipo_registro"] = result["tipo_registro"].map(normalize_tipo_registro)
    return result


def _fields_from_item_schema(df_item_schema: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    columns = ["sheet", "ordem", "campo", "tipo_dado", "obrigatorio", "origem", "descricao"]
    fields = df_item_schema[df_item_schema["schema"].astype(str) == sheet_name].copy()
    if fields.empty:
        return pd.DataFrame(columns=columns)

    fields = fields.sort_values("id", na_position="last").reset_index(drop=True)
    fields = pd.DataFrame({
        "sheet": sheet_name,
        "ordem": range(1, len(fields) + 1),
        "campo": fields["campo"],
        "tipo_dado": fields["tipo"],
        "obrigatorio": fields["nulo"].map(lambda value: not bool_value(value, default=True)),
        "origem": "",
        "descricao": "",
    })
    fields = fields.dropna(subset=["campo"]).drop_duplicates(subset=["campo"], keep="first")
    return fields.sort_values("ordem", na_position="last").reset_index(drop=True)


def _output_tabs(df_schema: pd.DataFrame, df_templates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    schema_names = df_schema["nome"].astype(str)
    output_schemas = df_schema[~schema_names.isin(CONFIG_ONLY_SCHEMAS)].copy()
    output_schemas["ordem_saida"] = output_schemas["nome"].map(OUTPUT_ORDER).fillna(999)
    output_schemas = output_schemas.sort_values(["ordem_saida", "id"], na_position="last")

    for _, template in df_templates.iterrows():
        for ordem, (_, row) in enumerate(output_schemas.iterrows(), start=1):
            rows.append({
                "template_id": template["template_id"],
                "theme_id": template["theme_id"],
                "sheet_name": row["nome"],
                "ordem": ordem,
                "ativo": True,
                "descricao": "",
            })
    return pd.DataFrame(rows)


def _by_schema(base_items: pd.DataFrame, schema_name: str) -> pd.DataFrame:
    return base_items[base_items["schema"].astype(str) == schema_name].copy()


def _optional_text(row: pd.Series, column: str) -> str | None:
    if column not in row.index or is_empty_marker(row[column]):
        return None
    return str(row[column]).strip()


def _optional_number(row: pd.Series, column: str, default: Any) -> Any:
    if column not in row.index or is_empty_marker(row[column]):
        return default
    return row[column]
