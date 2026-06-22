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
    df_category_type_rules: pd.DataFrame
    df_metadata_text_rules: pd.DataFrame
    df_category_alias_rules: pd.DataFrame
    df_subcategory_alias_rules: pd.DataFrame
    df_sample_text_rules: pd.DataFrame
    df_client_text_rules: pd.DataFrame
    df_results_extract_model: pd.DataFrame
    df_sample_output_model: pd.DataFrame
    df_client_output_model: pd.DataFrame
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


def _normalize_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    replacements = str.maketrans({
        "á": "a",
        "à": "a",
        "â": "a",
        "ã": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    })
    text = text.translate(replacements)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _is_empty_marker(value: Any) -> bool:
    if pd.isna(value):
        return True
    text = _normalize_token(value)
    return text in {
        "",
        "na",
        "nan",
        "none",
        "nao_aplicavel",
        "nao_se_aplica",
        "nao_aplica",
    }


def _value_or_none(row: pd.Series, column: str) -> Any:
    value = row[column] if column in row.index else None
    if _is_empty_marker(value):
        return None
    return None if pd.isna(value) else value


def _cell_or_none(value: Any) -> Any:
    return None if _is_empty_marker(value) else value


def _parse_attrs(value: Any) -> dict[str, str]:
    if _is_empty_marker(value):
        return {}

    attrs: dict[str, str] = {}
    for part in str(value).split(";"):
        if "=" not in part:
            continue
        key, attr_value = part.split("=", 1)
        key = _normalize_token(key)
        if key:
            attrs[key] = attr_value.strip()
    return attrs


def _parse_weight(value: Any) -> float:
    attrs = _parse_attrs(value)
    raw_weight = attrs.get("peso", value)
    if _is_empty_marker(raw_weight):
        return 0.0
    match = re.search(r"-?\d+(?:[,.]\d+)?", str(raw_weight))
    return float(match.group(0).replace(",", ".")) if match else 0.0


def _normalize_tipo_registro(value: Any) -> str | None:
    if _is_empty_marker(value):
        return None
    token = _normalize_token(value)
    mapping = {
        "amostra": "AMOSTRA",
        "branco": "BRANCO",
        "duplicata": "DUPLICATA",
        "recuperacao": "RECUPERACAO",
    }
    return mapping.get(token, str(value).strip().upper())


def _template_identity(taxonomy_name: Any, template_id: Any) -> dict[str, Any]:
    token = _normalize_token(taxonomy_name)
    version = int(template_id) if not _is_empty_marker(template_id) else 1

    if "agua" in token:
        theme_id = "laudo_agua"
        stable_template_id = "template_laudo_agua_v1"
        name = "Laudo analitico de agua"
    else:
        theme_id = f"laudo_{token}" if token else f"laudo_{version}"
        stable_template_id = f"template_{theme_id}_v{version}"
        name = str(taxonomy_name or theme_id).strip()

    return {
        "template_id": stable_template_id,
        "theme_id": theme_id,
        "nome": name,
        "schema_ref": "results_extract",
    }


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


def _build_category_alias_rules(df_category_alias_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []

    for _, row in df_category_alias_rules.iterrows():
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


def _build_subcategory_alias_rules(df_subcategory_alias_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if df_subcategory_alias_rules.empty:
        return rules

    source = df_subcategory_alias_rules.copy()
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


def _build_category_type_rules(df_category_type_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for _, row in df_category_type_rules.iterrows():
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


def _build_metadata_rules(df_metadata_text_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for _, row in df_metadata_text_rules.iterrows():
        regex = _value_or_none(row, "regex")
        campo = _value_or_none(row, "campo")
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

    if {"campo", "coluna_origem"}.issubset(df_table_extraction_rules.columns):
        for _, row in df_table_extraction_rules.iterrows():
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

    for _, row in df_table_extraction_rules.iterrows():
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


def _build_header_alias_rules(df_header_alias_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if df_header_alias_rules.empty:
        return rules

    for _, row in df_header_alias_rules.iterrows():
        campo = str(_value_or_none(row, "campo") or "").strip()
        pattern = _value_or_none(row, "header_regex")
        if not campo or pattern is None:
            continue
        field = campo if campo == "parameter" or campo.endswith("_col") else f"{campo}_col"
        if field != "parameter" and field not in LAYOUT_FIELD_KEYS:
            continue
        rules.append({
            "field": field,
            "regex": re.compile(str(pattern), re.IGNORECASE),
            "descricao": _value_or_none(row, "descricao"),
        })
    return rules


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


def _validate_output_model(sheet_name: str, df_model: pd.DataFrame, expected_columns: list[str]) -> None:
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


def _fields_from_item_schema(df_item_schema: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    columns = ["sheet", "ordem", "campo", "tipo_dado", "obrigatorio", "origem", "descricao"]
    if df_item_schema.empty:
        return pd.DataFrame(columns=columns)

    fields = df_item_schema[df_item_schema["schema"].astype(str) == sheet_name].copy()
    if fields.empty:
        return pd.DataFrame(columns=columns)

    fields = fields.sort_values("id", na_position="last").reset_index(drop=True)
    fields = pd.DataFrame({
        "sheet": sheet_name,
        "ordem": range(1, len(fields) + 1),
        "campo": fields["campo"],
        "tipo_dado": fields["tipo"],
        "obrigatorio": fields["nulo"].map(lambda value: not _bool_value(value, default=True)),
        "origem": "",
        "descricao": "",
    })
    fields = fields.dropna(subset=["campo"]).drop_duplicates(subset=["campo"], keep="first")
    return fields.sort_values("ordem", na_position="last").reset_index(drop=True)


def _load_taxonomy_frames(excel: pd.ExcelFile) -> dict[str, pd.DataFrame]:
    required_sheets = {"item_taxonomia", "template", "item_template", "schema", "item_schema"}
    missing = sorted(required_sheets - set(excel.sheet_names))
    if missing:
        raise ValueError(f"Taxonomia invalida. Abas obrigatorias ausentes: {missing}")

    df_taxonomy = pd.read_excel(excel, "item_taxonomia")
    df_template_source = pd.read_excel(excel, "template")
    df_item_template = pd.read_excel(excel, "item_template")
    df_schema = pd.read_excel(excel, "schema")
    df_item_schema = pd.read_excel(excel, "item_schema")

    if df_taxonomy.empty or df_template_source.empty:
        raise ValueError("Taxonomia invalida. item_taxonomia e template precisam ter ao menos um registro.")

    taxonomy_by_id = {
        row["id"]: row
        for _, row in df_taxonomy.iterrows()
        if "id" in row.index
    }

    template_rows: list[dict[str, Any]] = []
    template_identity_by_id: dict[Any, dict[str, Any]] = {}
    for _, row in df_template_source.iterrows():
        taxonomy_row = taxonomy_by_id.get(row.get("id_item_taxonomia"))
        taxonomy_name = taxonomy_row.get("nome") if taxonomy_row is not None else None
        identity = _template_identity(taxonomy_name, row.get("id"))
        template_identity_by_id[row.get("id")] = identity
        template_rows.append({
            **identity,
            "regex": row.get("regex"),
            "descricao": taxonomy_name,
            "prioridade": int(row.get("id") or 999),
            "score_minimo": 80.0,
            "ativo": _bool_value(row.get("ativo"), default=True),
        })
    df_templates = pd.DataFrame(template_rows)

    def template_id_for(row: pd.Series) -> str:
        identity = template_identity_by_id.get(row.get("id_template"))
        return str((identity or {}).get("template_id") or "")

    base_items = df_item_template.copy()
    base_items["template_id"] = base_items.apply(template_id_for, axis=1)
    base_items["ativo"] = True

    def by_schema(schema_name: str) -> pd.DataFrame:
        return base_items[base_items["schema"].astype(str) == schema_name].copy()

    def text_rules(schema_name: str, include_description: bool = False) -> pd.DataFrame:
        df = by_schema(schema_name)
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

    template_rule_rows: list[dict[str, Any]] = []
    rule_type_by_schema = {
        "template_required": "required",
        "template_positive": "positive",
        "template_negative": "negative",
    }
    for _, row in base_items[base_items["schema"].isin(rule_type_by_schema)].iterrows():
        template_rule_rows.append({
            "template_id": row["template_id"],
            "rule_type": rule_type_by_schema[str(row["schema"])],
            "source": "text",
            "padrao_regex": row["regex"],
            "peso": _parse_weight(row.get("coluna_origem")),
            "ativo": True,
            "descricao": "",
        })
    templates_with_detail_rules = {row["template_id"] for row in template_rule_rows}
    for _, row in df_template_source.iterrows():
        identity = template_identity_by_id.get(row.get("id")) or {}
        template_id = str(identity.get("template_id") or "")
        pattern = row.get("regex")
        if template_id and template_id not in templates_with_detail_rules and not _is_empty_marker(pattern):
            template_rule_rows.append({
                "template_id": template_id,
                "rule_type": "positive",
                "source": "text",
                "padrao_regex": pattern,
                "peso": 80.0,
                "ativo": True,
                "descricao": "Regex geral do template",
            })
    df_template_rules = pd.DataFrame(template_rule_rows)

    section_rows: list[dict[str, Any]] = []
    for schema_name in {"category_type", "category_alias", "subcategory_alias"}:
        for _, row in by_schema(schema_name).iterrows():
            attrs = _parse_attrs(row.get("coluna_origem"))
            section_rows.append({
                "regra_origem": schema_name,
                "template_id": row["template_id"],
                "prioridade": _cell_or_none(attrs.get("prioridade")),
                "padrao_regex": row["regex"],
                "categoria": _cell_or_none(attrs.get("categoria")) or row["campo"],
                "subcategoria": _cell_or_none(attrs.get("subcategoria")),
                "tipo_registro": _normalize_tipo_registro(row.get("tipo_registro")),
                "local": _cell_or_none(attrs.get("local")) or "laboratorio",
                "extrair_subcategoria": _bool_value(attrs.get("extrair_subcategoria"), default=False),
                "ativo": True,
                "descricao": "",
            })
    df_section_rules = pd.DataFrame(section_rows)

    def section_subset(schema_name: str, columns: list[str]) -> pd.DataFrame:
        if df_section_rules.empty:
            return pd.DataFrame(columns=columns)
        df = df_section_rules[df_section_rules["regra_origem"] == schema_name].copy()
        return df[columns]

    df_table_extraction_rules = by_schema("layout")
    if df_table_extraction_rules.empty:
        df_table_extraction_rules = pd.DataFrame(columns=["template_id", "tipo_registro", "campo", "coluna_origem", "ativo"])
    else:
        df_table_extraction_rules = df_table_extraction_rules[[
            "template_id",
            "tipo_registro",
            "campo",
            "coluna_origem",
            "ativo",
        ]].copy()
        df_table_extraction_rules["tipo_registro"] = df_table_extraction_rules["tipo_registro"].map(_normalize_tipo_registro)

    df_header_alias_rules = by_schema("header_alias")
    if df_header_alias_rules.empty:
        df_header_alias_rules = pd.DataFrame(columns=["template_id", "campo", "header_regex", "ativo", "descricao"])
    else:
        df_header_alias_rules = df_header_alias_rules[["template_id", "campo", "regex", "ativo"]].copy()
        df_header_alias_rules = df_header_alias_rules.rename(columns={"regex": "header_regex"})
        df_header_alias_rules["descricao"] = ""

    df_continuation_rules = by_schema("continuation")
    if df_continuation_rules.empty:
        df_continuation_rules = pd.DataFrame(columns=["template_id", "tipo_registro", "continuation_regex", "ativo"])
    else:
        df_continuation_rules = df_continuation_rules[["template_id", "tipo_registro", "regex", "ativo"]].copy()
        df_continuation_rules = df_continuation_rules.rename(columns={"regex": "continuation_regex"})
        df_continuation_rules["tipo_registro"] = df_continuation_rules["tipo_registro"].map(_normalize_tipo_registro)

    output_rows: list[dict[str, Any]] = []
    output_order = {
        "results_extract": 1,
        "sample": 2,
        "client": 3,
        "table_extraction_audit": 4,
        "classification_audit": 5,
        "validation_errors": 6,
    }
    output_schemas = df_schema[df_schema["nome"].astype(str) != "metadata"].copy()
    output_schemas["ordem_saida"] = output_schemas["nome"].map(output_order).fillna(999)
    output_schemas = output_schemas.sort_values(["ordem_saida", "id"], na_position="last")
    for _, template in df_templates.iterrows():
        for ordem, (_, row) in enumerate(output_schemas.iterrows(), start=1):
            output_rows.append({
                "template_id": template["template_id"],
                "theme_id": template["theme_id"],
                "sheet_name": row["nome"],
                "ordem": ordem,
                "ativo": True,
                "descricao": "",
            })
    df_output_tabs = pd.DataFrame(output_rows)

    return {
        "templates": df_templates,
        "category_type_rules": section_subset(
            "category_type",
            ["template_id", "padrao_regex", "categoria", "tipo_registro", "extrair_subcategoria", "ativo"],
        ),
        "metadata_text_rules": text_rules("metadata"),
        "category_alias_rules": section_subset(
            "category_alias",
            ["template_id", "padrao_regex", "categoria", "subcategoria", "local", "ativo"],
        ),
        "subcategory_alias_rules": section_subset(
            "subcategory_alias",
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
        ),
        "sample_text_rules": text_rules("sample"),
        "client_text_rules": text_rules("client", include_description=True),
        "results_extract_model": _fields_from_item_schema(df_item_schema, "results_extract"),
        "sample_output_model": _fields_from_item_schema(df_item_schema, "sample"),
        "client_output_model": _fields_from_item_schema(df_item_schema, "client"),
        "table_layouts": df_table_extraction_rules,
        "header_alias_rules": df_header_alias_rules,
        "continuation_rules": df_continuation_rules,
        "template_rules": df_template_rules,
        "output_tabs": df_output_tabs,
    }


def _build_template_rules(df_template_rules: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if df_template_rules.empty:
        return rules

    for _, row in df_template_rules.iterrows():
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
        template_id = str(_value_or_none(row, "template_id") or "").strip()
        sheet_name = str(_value_or_none(row, "sheet_name") or "").strip()
        if not template_id or not sheet_name:
            continue
        output_tabs.setdefault(template_id, []).append(sheet_name)
    return output_tabs


def output_tabs_for_template(config: PipelineConfig, template_id: str) -> list[str]:
    return config.output_tabs.get(template_id) or [
        "results_extract",
        "sample",
        "client",
        "table_extraction_audit",
        "classification_audit",
        "validation_errors",
    ]


def filter_config_for_template(config: PipelineConfig, template_id: str) -> PipelineConfig:
    df_category_type_rules = _filter_rules_dataframe(config.df_category_type_rules, template_id)
    df_metadata_text_rules = _filter_rules_dataframe(config.df_metadata_text_rules, template_id)
    df_category_alias_rules = _filter_rules_dataframe(config.df_category_alias_rules, template_id)
    df_subcategory_alias_rules = _filter_rules_dataframe(config.df_subcategory_alias_rules, template_id)
    df_sample_text_rules = _filter_rules_dataframe(config.df_sample_text_rules, template_id)
    df_client_text_rules = _filter_rules_dataframe(config.df_client_text_rules, template_id)
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

    excel = pd.ExcelFile(taxonomy_path)
    frames = _load_taxonomy_frames(excel)
    excel.close()
    df_templates = frames["templates"]
    df_category_type_rules = frames["category_type_rules"]
    df_metadata_text_rules = frames["metadata_text_rules"]
    df_category_alias_rules = frames["category_alias_rules"]
    df_subcategory_alias_rules = frames["subcategory_alias_rules"]
    df_sample_text_rules = frames["sample_text_rules"]
    df_client_text_rules = frames["client_text_rules"]
    df_results_extract_model = frames["results_extract_model"]
    df_sample_output_model = frames["sample_output_model"]
    df_client_output_model = frames["client_output_model"]
    df_table_extraction_rules = frames["table_layouts"]
    df_header_alias_rules = frames["header_alias_rules"]
    df_continuation_rules = frames["continuation_rules"]
    df_template_rules = frames["template_rules"]
    df_output_tabs = frames["output_tabs"]

    _validate_output_model("results_extract", df_results_extract_model, RESULTS_EXTRACT_COLUMNS)
    _validate_output_model("sample", df_sample_output_model, SAMPLE_COLUMNS)
    _validate_output_model("client", df_client_output_model, CLIENT_COLUMNS)

    category_type_rules = _build_category_type_rules(df_category_type_rules)
    metadata_rules = _build_metadata_rules(df_metadata_text_rules)
    category_alias_rules = _build_category_alias_rules(df_category_alias_rules)
    subcategory_alias_rules = _build_subcategory_alias_rules(df_subcategory_alias_rules)
    table_layouts = _build_table_layouts(df_table_extraction_rules)
    header_alias_rules = _build_header_alias_rules(df_header_alias_rules)
    continuation_rules = _build_continuation_rules(df_continuation_rules)
    templates = _build_templates(df_templates)
    _validate_detection_sources("template_rules", df_template_rules)
    template_ids = set(templates)
    for sheet_name, df in {
        "templates": df_templates,
        "template_rules": df_template_rules,
        "output_tabs": df_output_tabs,
        "metadata_text_rules": df_metadata_text_rules,
        "client_text_rules": df_client_text_rules,
        "sample_text_rules": df_sample_text_rules,
        "category_type_rules": df_category_type_rules,
        "category_alias_rules": df_category_alias_rules,
        "subcategory_alias_rules": df_subcategory_alias_rules,
        "table_layouts": df_table_extraction_rules,
        "header_alias_rules": df_header_alias_rules,
        "continuation_rules": df_continuation_rules,
        "results_extract_model": df_results_extract_model,
        "sample_output_model": df_sample_output_model,
        "client_output_model": df_client_output_model,
    }.items():
        _validate_boolean_columns(sheet_name, df)
        _validate_template_ids(sheet_name, df, template_ids)
    template_rules = _build_template_rules(df_template_rules)
    output_tabs = _build_output_tabs(df_output_tabs)

    log.info(
        "Taxonomy carregada: %d regras de secao, %d campos de metadata",
        len(df_category_type_rules) + len(category_alias_rules) + len(subcategory_alias_rules),
        len(df_metadata_text_rules),
    )

    return PipelineConfig(
        taxonomy_path=taxonomy_path,
        df_templates=df_templates,
        df_category_type_rules=df_category_type_rules,
        df_metadata_text_rules=df_metadata_text_rules,
        df_category_alias_rules=df_category_alias_rules,
        df_subcategory_alias_rules=df_subcategory_alias_rules,
        df_sample_text_rules=df_sample_text_rules,
        df_client_text_rules=df_client_text_rules,
        df_results_extract_model=df_results_extract_model,
        df_sample_output_model=df_sample_output_model,
        df_client_output_model=df_client_output_model,
        df_template_rules=df_template_rules,
        df_output_tabs=df_output_tabs,
        df_table_extraction_rules=df_table_extraction_rules,
        df_header_alias_rules=df_header_alias_rules,
        df_continuation_rules=df_continuation_rules,
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
