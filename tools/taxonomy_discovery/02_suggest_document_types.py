import argparse
import re
from pathlib import Path
from typing import Any, Sequence

import pandas as pd


DEFAULT_INVENTORY = Path("output/taxonomy_discovery/pdf_inventory.xlsx")
DEFAULT_TAXONOMY = Path("config/taxonomy_config_v5.xlsx")
DEFAULT_OUTPUT = Path("output/taxonomy_discovery/document_type_suggestions.xlsx")


def _is_disabled(value: Any) -> bool:
    return value is False or str(value).strip().lower() in {"false", "0", "nao", "não"}


def _value_or_none(row: pd.Series, column: str) -> Any:
    value = row[column] if column in row.index else None
    return None if pd.isna(value) else value


def _active_rows(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty or "ativo" not in dataframe.columns:
        return dataframe.copy()
    return dataframe[~dataframe["ativo"].map(_is_disabled)].copy()


def _haystack(row: pd.Series, source: str) -> str:
    if source == "path":
        return f"{row.get('caminho', '')} {row.get('path_relativo', '')}"
    if source == "filename":
        return f"{row.get('arquivo', '')} {row.get('stem', '')}"
    if source == "tokens":
        return str(row.get("tokens", ""))
    return str(row.get("text_sample", ""))


def _rule_description(rule: pd.Series) -> str:
    descricao = _value_or_none(rule, "descricao")
    return str(descricao or _value_or_none(rule, "padrao_regex") or "")


def _score_document_type(
    row: pd.Series,
    document_type_id: str,
    rules: pd.DataFrame,
) -> tuple[float, str, list[str]]:
    selected_rules = rules[rules["document_type_id"].astype(str) == document_type_id]
    required_rules = selected_rules[selected_rules["rule_type"].astype(str).str.lower() == "required"]
    positive_rules = selected_rules[selected_rules["rule_type"].astype(str).str.lower() == "positive"]
    negative_rules = selected_rules[selected_rules["rule_type"].astype(str).str.lower() == "negative"]
    matched_rules: list[str] = []

    for _, rule in required_rules.iterrows():
        source = str(_value_or_none(rule, "source") or "text").strip().lower()
        pattern = str(_value_or_none(rule, "padrao_regex") or "")
        if not re.search(pattern, _haystack(row, source), flags=re.IGNORECASE):
            return 0.0, f"required_missing:{_rule_description(rule)}", matched_rules
        matched_rules.append(f"required:{_rule_description(rule)}")

    for _, rule in negative_rules.iterrows():
        source = str(_value_or_none(rule, "source") or "text").strip().lower()
        pattern = str(_value_or_none(rule, "padrao_regex") or "")
        if re.search(pattern, _haystack(row, source), flags=re.IGNORECASE):
            matched_rules.append(f"negative:{_rule_description(rule)}")
            return 0.0, f"negative_matched:{_rule_description(rule)}", matched_rules

    score = 0.0
    for _, rule in positive_rules.iterrows():
        source = str(_value_or_none(rule, "source") or "text").strip().lower()
        pattern = str(_value_or_none(rule, "padrao_regex") or "")
        if re.search(pattern, _haystack(row, source), flags=re.IGNORECASE):
            weight = _value_or_none(rule, "peso")
            score += float(weight) if weight is not None else 0.0
            matched_rules.append(f"positive:{_rule_description(rule)}")

    return score, "scored", matched_rules


def load_document_type_taxonomy(taxonomy_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    document_types = pd.read_excel(taxonomy_path, sheet_name="document_types")
    detection_rules = pd.read_excel(taxonomy_path, sheet_name="document_type_detection_rules")
    return _active_rows(document_types), _active_rows(detection_rules)


def classify_document_types(
    inventory: pd.DataFrame,
    document_types: pd.DataFrame,
    detection_rules: pd.DataFrame,
) -> pd.DataFrame:
    audit_rows = []
    for _, row in inventory.iterrows():
        candidates = []
        evaluated = []

        for _, document_type in document_types.iterrows():
            document_type_id = str(_value_or_none(document_type, "document_type_id") or "").strip()
            if not document_type_id:
                continue

            score, status, matched_rules = _score_document_type(row, document_type_id, detection_rules)
            score_minimo = float(_value_or_none(document_type, "score_minimo") or 0)
            prioridade = int(_value_or_none(document_type, "prioridade") or 999)
            evaluated.append(f"{document_type_id}:{status}:{score}/{score_minimo}")
            if status == "scored" and score >= score_minimo:
                candidates.append((score, -prioridade, document_type_id, score_minimo, matched_rules))

        if candidates:
            score, _, document_type_id, score_minimo, matched_rules = max(candidates)
            status = "identificado"
            matched_rules_text = "; ".join(matched_rules)
        else:
            document_type_id = None
            status = "sem_tipo"
            score = 0.0
            score_minimo = None
            matched_rules_text = ""

        audit_rows.append({
            "arquivo": row.get("arquivo"),
            "caminho": row.get("caminho"),
            "document_type_id": document_type_id,
            "status": status,
            "score": score,
            "score_minimo": score_minimo,
            "matched_rules": matched_rules_text,
            "scores_avaliados": "; ".join(evaluated),
        })
    return pd.DataFrame(audit_rows)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classifica tipos macro de documento usando regras oficiais da taxonomy.",
    )
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY, help="Excel gerado pelo 01_scan_pdf_corpus.py.")
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY, help="Excel oficial de taxonomia.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Excel com auditoria de tipos de documento.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    inventory = pd.read_excel(args.inventory, sheet_name="pdf_inventory")
    document_types, detection_rules = load_document_type_taxonomy(args.taxonomy)
    audit = classify_document_types(inventory, document_types, detection_rules)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        document_types.to_excel(writer, sheet_name="document_types", index=False)
        detection_rules.to_excel(writer, sheet_name="document_type_detection_rules", index=False)
        audit.to_excel(writer, sheet_name="document_type_audit", index=False)
        audit["document_type_id"].fillna("NA").value_counts().reset_index(name="quantidade").to_excel(
            writer,
            sheet_name="summary",
            index=False,
        )
    print(f"Auditoria de tipos de documento salva em: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
