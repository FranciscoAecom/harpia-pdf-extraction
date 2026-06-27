import re
from typing import Any

import pandas as pd

from ..config.common import value_or_none
from ..constants import FIELD_EXTRACTION_AUDIT_COLUMNS
from ..core.context import DocumentContext


def _clean(value: Any, limit: int = 500) -> str | None:
    if value is None or (not isinstance(value, (list, dict, tuple)) and pd.isna(value)):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit] if text else None


def _first_value(frame: pd.DataFrame, field: str) -> Any:
    if frame.empty or field not in frame.columns:
        return None
    values = frame[field].dropna()
    return values.iloc[0] if not values.empty else None


def build_field_extraction_audit(
    pages: list[tuple[str, list]],
    context: DocumentContext,
    config,
    metadata: dict[str, Any],
    sample_df: pd.DataFrame,
    client_df: pd.DataFrame,
) -> pd.DataFrame:
    sources = [
        ("metadata", config.df_metadata_text_rules, metadata),
        ("sample", config.df_sample_text_rules, sample_df),
        ("client", config.df_client_text_rules, client_df),
    ]
    compiled_rules: list[tuple[str, str, re.Pattern[str]]] = []
    for schema_name, rules, _ in sources:
        for _, rule in rules.iterrows():
            field = str(value_or_none(rule, "campo") or "").strip()
            regex = str(value_or_none(rule, "regex") or "").strip()
            if field and regex and regex != "DERIVADO_DO_NOME_DO_PDF":
                label_end = regex.find(r":\s*")
                label_regex = regex[: label_end + 1] if label_end >= 0 else regex
                compiled_rules.append(
                    (schema_name, field, re.compile(label_regex, re.IGNORECASE | re.DOTALL))
                )

    rows: list[dict[str, Any]] = []
    for schema_name, rules, extracted_source in sources:
        for _, rule in rules.iterrows():
            field = str(value_or_none(rule, "campo") or "").strip()
            regex = str(value_or_none(rule, "regex") or "").strip()
            if not field or not regex or regex == "DERIVADO_DO_NOME_DO_PDF":
                continue

            pattern = re.compile(regex, re.IGNORECASE | re.DOTALL)
            page_matches = [(number, list(pattern.finditer(text))) for number, (text, _) in enumerate(pages, 1)]
            page_matches = [(number, matches) for number, matches in page_matches if matches]
            occurrences = sum(len(matches) for _, matches in page_matches)
            page_number = page_matches[0][0] if page_matches else None
            value = extracted_source.get(field) if isinstance(extracted_source, dict) else _first_value(extracted_source, field)
            clean_value = _clean(value)

            contaminating_fields = sorted({
                other_field
                for other_schema, other_field, other_pattern in compiled_rules
                if clean_value
                and (other_schema, other_field) != (schema_name, field)
                and other_pattern.search(clean_value)
            })

            if occurrences and not clean_value:
                status = "encontrado_sem_extracao"
                observation = "A regra foi encontrada no PDF, mas o campo de saida ficou vazio."
            elif not occurrences and clean_value:
                status = "extraido_sem_correspondencia"
                observation = "O campo foi preenchido sem correspondencia da regra no texto do PDF."
            elif contaminating_fields:
                status = "possivel_contaminacao"
                observation = "O valor extraido contem regra associada a outro campo."
            elif occurrences:
                status = "ok"
                observation = None
            else:
                status = "nao_aplicavel"
                observation = None

            rows.append({
                "nome_do_arquivo": context.nome_do_arquivo,
                "id_taxonomia": context.id_taxonomia,
                "nome_taxonomia": context.nome_taxonomia,
                "versao_template": context.versao_template,
                "schema_origem": schema_name,
                "campo": field,
                "pagina": page_number,
                "regra_encontrada": regex,
                "ocorrencias_detectadas": occurrences,
                "valor_extraido": clean_value,
                "campos_detectados_no_valor": "; ".join(contaminating_fields) or None,
                "status": status,
                "observacao": observation,
            })

    return pd.DataFrame(rows, columns=FIELD_EXTRACTION_AUDIT_COLUMNS)
