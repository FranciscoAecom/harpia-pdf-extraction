import argparse
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_INVENTORY = Path("output/taxonomy_discovery/pdf_inventory.xlsx")
DEFAULT_OUTPUT = Path("output/taxonomy_discovery/document_type_suggestions.xlsx")


DEFAULT_TYPE_RULES = [
    {
        "document_type_id": "ficha_subcontratacao",
        "nome": "Ficha de subcontratacao",
        "prioridade": 10,
        "score_minimo": 80,
        "rules": [
            ("positive", "text", r"SUBCONTRATA..O\s+DE\s+SERVI.OS\s+DE\s+AN.LISE|Provedor\s+Externo", 70),
            ("positive", "path", r"COC_subcontratadas|subcontratad", 30),
            ("positive", "filename", r"subcontrat|FO-ANL", 20),
        ],
    },
    {
        "document_type_id": "ficha_recebimento",
        "nome": "Ficha de recebimento",
        "prioridade": 20,
        "score_minimo": 80,
        "rules": [
            ("positive", "text", r"Confirma..o\s+de\s+Recebimento|Checklist\s+de\s+Recebimento|RESPONS.VEL\s+PELA\s+ENTREGA", 70),
            ("positive", "filename", r"recebimento|checklist", 30),
            ("positive", "path", r"COC_subcontratadas|recebimento", 20),
        ],
    },
    {
        "document_type_id": "ficha_coleta",
        "nome": "Ficha de coleta",
        "prioridade": 30,
        "score_minimo": 80,
        "rules": [
            ("positive", "text", r"Cadeia\s+de\s+Cust.dia|Planejamento\s+de\s+Amostragem|Amostra\s+Id", 70),
            ("positive", "path", r"Fichas?\s+de\s+coleta|coleta", 30),
        ],
    },
    {
        "document_type_id": "ficha_campo",
        "nome": "Ficha de campo",
        "prioridade": 40,
        "score_minimo": 80,
        "rules": [
            ("positive", "text", r"Ficha\s+de\s+Campo|Dados\s+de\s+Campo|Medi..o\s+em\s+Campo", 80),
            ("positive", "filename", r"campo", 20),
        ],
    },
    {
        "document_type_id": "laudo",
        "nome": "Laudo",
        "prioridade": 50,
        "score_minimo": 80,
        "rules": [
            ("positive", "text", r"Relat.rio\s+Anal.tico|Relat.rio\s+de\s+Ensaio|Relat.rio\s+de\s+an.lises", 70),
            ("positive", "path", r"Laudos?|relat.rio", 30),
        ],
    },
]


def _haystack(row: pd.Series, source: str) -> str:
    if source == "path":
        return f"{row.get('caminho', '')} {row.get('path_relativo', '')}"
    if source == "filename":
        return f"{row.get('arquivo', '')} {row.get('stem', '')}"
    return str(row.get("text_sample", ""))


def _score_row(row: pd.Series, type_rule: dict) -> tuple[int, list[str]]:
    score = 0
    matches = []
    for rule_type, source, pattern, weight in type_rule["rules"]:
        if rule_type != "positive":
            continue
        if re.search(pattern, _haystack(row, source), flags=re.IGNORECASE):
            score += int(weight)
            matches.append(f"{source}:{pattern}")
    return score, matches


def suggest_document_types(inventory: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    document_types = pd.DataFrame([
        {
            "document_type_id": item["document_type_id"],
            "nome": item["nome"],
            "descricao": f"Tipo macro de documento: {item['nome']}.",
            "prioridade": item["prioridade"],
            "score_minimo": item["score_minimo"],
            "ativo": True,
        }
        for item in DEFAULT_TYPE_RULES
    ])

    rule_rows = []
    for item in DEFAULT_TYPE_RULES:
        for rule_type, source, pattern, weight in item["rules"]:
            rule_rows.append({
                "document_type_id": item["document_type_id"],
                "rule_type": rule_type,
                "source": source,
                "padrao_regex": pattern,
                "peso": weight,
                "ativo": True,
                "descricao": f"Regra candidata para {item['nome']}.",
            })
    detection_rules = pd.DataFrame(rule_rows)

    audit_rows = []
    for _, row in inventory.iterrows():
        candidates = []
        for item in DEFAULT_TYPE_RULES:
            score, matches = _score_row(row, item)
            if score >= item["score_minimo"]:
                candidates.append((score, -item["prioridade"], item, matches))
        if candidates:
            score, _, winner, matches = max(candidates)
            document_type_id = winner["document_type_id"]
            status = "identificado"
            score_minimo = winner["score_minimo"]
            matched_rules = "; ".join(matches)
        else:
            document_type_id = None
            status = "sem_tipo"
            score = 0
            score_minimo = None
            matched_rules = ""

        audit_rows.append({
            "arquivo": row.get("arquivo"),
            "caminho": row.get("caminho"),
            "document_type_id": document_type_id,
            "status": status,
            "score": score,
            "score_minimo": score_minimo,
            "matched_rules": matched_rules,
        })
    audit = pd.DataFrame(audit_rows)
    return document_types, detection_rules, audit


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sugere tipos macro de documento antes do cadastro de templates.")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY, help="Excel gerado pelo 01_scan_pdf_corpus.py.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Excel com document_types e auditoria.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    inventory = pd.read_excel(args.inventory, sheet_name="pdf_inventory")
    document_types, detection_rules, audit = suggest_document_types(inventory)
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
    print(f"Sugestoes de tipo de documento salvas em: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
