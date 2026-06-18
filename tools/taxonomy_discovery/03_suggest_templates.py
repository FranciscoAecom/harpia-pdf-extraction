import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_INVENTORY = Path("output/taxonomy_discovery/pdf_inventory.xlsx")
DEFAULT_DOCUMENT_TYPES = Path("output/taxonomy_discovery/document_type_suggestions.xlsx")
DEFAULT_OUTPUT = Path("output/taxonomy_discovery/template_suggestions.xlsx")

GENERIC_PATH_PARTS = {
    "laudos",
    "fichas de coleta",
    "coc_subcontratadas",
    "coc subcontratadas",
    "backup",
}
MONTHS = {
    "01_jan",
    "02_fev",
    "03_mar",
    "04_abr",
    "05_mai",
    "06_jun",
    "07_jul",
    "08_ago",
    "09_set",
    "10_out",
    "11_nov",
    "12_dez",
}
STOPWORDS = {
    "para",
    "com",
    "por",
    "das",
    "dos",
    "que",
    "uma",
    "relatorio",
    "ensaio",
    "analitico",
    "recebimento",
    "checklist",
    "amostra",
    "amostras",
    "coleta",
    "data",
    "hora",
    "cliente",
    "pagina",
}


def _sanitize(value: str) -> str:
    normalized = value.lower()
    replacements = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "õ": "o",
        "ô": "o",
        "ú": "u",
        "ç": "c",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return normalized or "indefinido"


def _path_parts(row: pd.Series) -> list[str]:
    path_relativo = str(row.get("path_relativo") or "")
    return [part for part in re.split(r"[\\/]+", path_relativo) if part]


def _is_noise_part(value: str) -> bool:
    clean = _sanitize(value)
    if clean in GENERIC_PATH_PARTS or clean in MONTHS:
        return True
    if re.fullmatch(r"20\d{2}", clean):
        return True
    if re.fullmatch(r"20\d{2}_\d{2}_c_\d+", clean):
        return True
    if re.fullmatch(r"\d{2}[-_]\d{2}", clean):
        return True
    return False


def _topic_from_path(row: pd.Series) -> str:
    parts = _path_parts(row)
    for part in reversed(parts[:-1]):
        if not _is_noise_part(part):
            return _sanitize(part)
    stem = str(row.get("stem") or row.get("arquivo") or "indefinido")
    tokens = re.findall(r"[A-Za-zÀ-ÿ]{3,}", stem)
    return _sanitize(tokens[-1] if tokens else stem)


def _top_text_terms(rows: pd.DataFrame, limit: int = 5) -> list[str]:
    counter: Counter[str] = Counter()
    for text in rows["text_sample"].fillna("").astype(str):
        for token in re.findall(r"[A-Za-zÀ-ÿ]{5,}", text.lower()):
            clean = _sanitize(token)
            if clean and clean not in STOPWORDS:
                counter[clean] += 1
    return [term for term, _ in counter.most_common(limit)]


def _regex_literal(value: str) -> str:
    return re.escape(value).replace("_", r"[_\s-]+")


def suggest_templates(inventory: pd.DataFrame, document_type_audit: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    merged = inventory.merge(
        document_type_audit[["caminho", "document_type_id"]],
        on="caminho",
        how="left",
    )
    merged["document_type_id"] = merged["document_type_id"].fillna("documento")
    merged["topic_candidate"] = merged.apply(_topic_from_path, axis=1)

    template_rows = []
    rule_rows = []
    output_sheet_rows = []
    sheet_defaults = [
        ("results_extract", 1, "Resultados extraidos do PDF para o template."),
        ("sample", 2, "Dados de amostra/cabecalho do PDF."),
        ("client", 3, "Dados de identificacao do cliente."),
        ("classification_audit", 98, "Auditoria da classificacao do PDF por template."),
        ("validation_errors", 99, "Erros de validacao da saida."),
    ]

    grouped = merged.groupby(["document_type_id", "topic_candidate"], dropna=False)
    for order, ((document_type_id, topic), group) in enumerate(grouped, start=1):
        theme_id = f"{document_type_id}_{topic}"
        template_id = f"template_{theme_id}_v1"
        template_rows.append({
            "template_id": template_id,
            "document_type_id": document_type_id,
            "theme_id": theme_id,
            "nome": theme_id.replace("_", " "),
            "schema_ref": "results_extract",
            "descricao": f"Template candidato inferido automaticamente para {theme_id}.",
            "prioridade": order * 10,
            "score_minimo": 80,
            "ativo": True,
            "quantidade_pdfs": len(group),
        })

        path_pattern = _regex_literal(str(topic))
        rule_rows.append({
            "template_id": template_id,
            "rule_type": "positive",
            "source": "path",
            "padrao_regex": path_pattern,
            "peso": 60,
            "ativo": True,
            "descricao": "Regra candidata inferida por pasta/caminho.",
        })

        filename_hits = [
            token for token in re.findall(r"[A-Za-zÀ-ÿ]{3,}", " ".join(group["stem"].fillna("").astype(str)))
            if _sanitize(token) == topic
        ]
        if filename_hits:
            rule_rows.append({
                "template_id": template_id,
                "rule_type": "positive",
                "source": "filename",
                "padrao_regex": _regex_literal(topic),
                "peso": 30,
                "ativo": True,
                "descricao": "Regra candidata inferida pelo nome do arquivo.",
            })

        terms = _top_text_terms(group)
        if terms:
            rule_rows.append({
                "template_id": template_id,
                "rule_type": "positive",
                "source": "text",
                "padrao_regex": "|".join(_regex_literal(term) for term in terms),
                "peso": 30,
                "ativo": True,
                "descricao": "Termos frequentes no texto do grupo; revisar antes de promover para regra forte.",
            })

        for sheet_name, sheet_order, description in sheet_defaults:
            output_sheet_rows.append({
                "template_id": template_id,
                "theme_id": theme_id,
                "sheet_name": sheet_name,
                "ordem": sheet_order,
                "ativo": True,
                "descricao": description,
            })

    return pd.DataFrame(template_rows), pd.DataFrame(rule_rows), pd.DataFrame(output_sheet_rows)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sugere templates e template_detection_rules a partir do inventario.")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY, help="Excel gerado pelo 01_scan_pdf_corpus.py.")
    parser.add_argument(
        "--document-types",
        type=Path,
        default=DEFAULT_DOCUMENT_TYPES,
        help="Excel gerado pelo 02_suggest_document_types.py.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Excel com templates candidatos.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    inventory = pd.read_excel(args.inventory, sheet_name="pdf_inventory")
    document_type_audit = pd.read_excel(args.document_types, sheet_name="document_type_audit")
    templates, rules, output_sheets = suggest_templates(inventory, document_type_audit)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        templates.to_excel(writer, sheet_name="templates", index=False)
        rules.to_excel(writer, sheet_name="template_detection_rules", index=False)
        output_sheets.to_excel(writer, sheet_name="output_sheets", index=False)
        templates[["document_type_id", "theme_id", "quantidade_pdfs"]].to_excel(
            writer,
            sheet_name="summary",
            index=False,
        )
    print(f"Sugestoes de templates salvas em: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
