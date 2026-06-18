import argparse
import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
import pdfplumber


DEFAULT_INPUT_DIR = Path(r"L:\Secure_DCS\BRBLH1PINFW001\COE_Digital\others\harpia_rd")
DEFAULT_OUTPUT = Path("output/taxonomy_discovery/pdf_corpus_profile.xlsx")
STOPWORDS = {
    "a",
    "as",
    "de",
    "do",
    "da",
    "das",
    "dos",
    "e",
    "em",
    "na",
    "no",
    "nas",
    "nos",
    "o",
    "os",
    "para",
    "por",
    "com",
    "sem",
    "the",
    "and",
    "for",
    "from",
    "with",
}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


def _clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _tokens(value: str) -> list[str]:
    normalized = _normalize_text(value)
    return [
        token
        for token in re.findall(r"[a-z0-9]{3,}", normalized)
        if token not in STOPWORDS and not token.isdigit()
    ]


def _phrases(value: str, max_phrases: int = 80) -> list[str]:
    phrases = []
    for raw_line in value.splitlines():
        line = _clean_spaces(raw_line)
        if len(line) < 8 or len(line) > 120:
            continue
        if len(re.findall(r"[A-Za-zÀ-ÿ]", line)) < 5:
            continue
        phrases.append(line)
        if len(phrases) >= max_phrases:
            break
    return phrases


def _regex_candidate(value: str) -> str:
    escaped = re.escape(_clean_spaces(value))
    return re.sub(r"\\\s+", r"\\s+", escaped)


def _list_pdfs(input_dir: Path, limit: int | None = None) -> list[Path]:
    pdfs = sorted(input_dir.rglob("*.pdf"))
    return pdfs[:limit] if limit else pdfs


def _path_parts(path: Path, root: Path) -> list[str]:
    try:
        return list(path.relative_to(root).parts)
    except ValueError:
        return list(path.parts)


def _extract_text(pdf_path: Path, max_pages: int | None) -> tuple[str, int, str | None]:
    try:
        parts = []
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            pages = pdf.pages[:max_pages] if max_pages else pdf.pages
            for page in pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts), page_count, None
    except Exception as exc:
        return "", 0, f"{type(exc).__name__}: {exc}"


def build_inventory(input_dir: Path, max_pages: int | None, limit: int | None = None) -> pd.DataFrame:
    rows = []
    pdfs = _list_pdfs(input_dir, limit)
    for index, pdf_path in enumerate(pdfs, start=1):
        print(f"[{index}/{len(pdfs)}] {pdf_path}")
        text, page_count, error = _extract_text(pdf_path, max_pages)
        parts = _path_parts(pdf_path, input_dir)
        path_text = " ".join(parts)
        text_sample = _clean_spaces(text)[:5000]
        feature_text = f"{path_text} {pdf_path.stem} {text_sample}"
        row_tokens = sorted(set(_tokens(feature_text)))
        row_phrases = _phrases(text)
        rows.append({
            "arquivo": pdf_path.name,
            "caminho": str(pdf_path),
            "path_relativo": str(Path(*parts)) if parts else pdf_path.name,
            "pasta_nivel_1": parts[0] if len(parts) > 0 else "",
            "pasta_nivel_2": parts[1] if len(parts) > 1 else "",
            "pasta_nivel_3": parts[2] if len(parts) > 2 else "",
            "pasta_pai": pdf_path.parent.name,
            "stem": pdf_path.stem,
            "page_count": page_count,
            "text_len": len(text),
            "text_hash": hashlib.sha1(text_sample.encode("utf-8", errors="ignore")).hexdigest(),
            "text_sample": text_sample,
            "tokens": " ".join(row_tokens),
            "phrases": " | ".join(row_phrases),
            "erro": error,
        })
    return pd.DataFrame(rows)


def _feature_set(row: pd.Series, max_features: int) -> set[str]:
    token_features = str(row.get("tokens") or "").split()
    phrase_features = [
        f"phrase:{_normalize_text(phrase)}"
        for phrase in str(row.get("phrases") or "").split(" | ")
        if phrase
    ]
    path_features = [
        f"path:{_normalize_text(part)}"
        for part in re.split(r"[\\/]+", str(row.get("path_relativo") or ""))
        if part
    ]
    features = token_features + phrase_features[:20] + path_features
    return set(features[:max_features])


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def assign_clusters(inventory: pd.DataFrame, threshold: float = 0.42, max_features: int = 220) -> pd.DataFrame:
    clusters: list[dict] = []
    rows = []
    for row_number, row in inventory.iterrows():
        features = _feature_set(row, max_features=max_features)
        best_index = None
        best_score = 0.0
        for cluster_index, cluster in enumerate(clusters):
            score = _jaccard(features, cluster["centroid"])
            if score > best_score:
                best_score = score
                best_index = cluster_index

        if best_index is None or best_score < threshold:
            best_index = len(clusters)
            clusters.append({"centroid": set(features), "count": 0})
            best_score = 1.0

        cluster = clusters[best_index]
        cluster["count"] += 1
        cluster["centroid"] = set(list((cluster["centroid"] | features))[:max_features])
        rows.append({
            "row_number": row_number,
            "cluster_id": f"cluster_{best_index + 1:03d}",
            "cluster_score": round(best_score, 4),
        })

    return inventory.reset_index(drop=True).join(pd.DataFrame(rows).drop(columns=["row_number"]))


def _top_items(values: Iterable[str], limit: int = 20) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for value in values:
        counter.update(item for item in value.split(" ") if item)
    return counter.most_common(limit)


def summarize_clusters(clustered: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    candidate_rows = []
    total_docs = len(clustered)

    for cluster_id, group in clustered.groupby("cluster_id", sort=True):
        count = len(group)
        examples = "; ".join(group["arquivo"].head(8).astype(str))
        top_text_tokens = _top_items(group["tokens"].fillna("").astype(str), limit=15)
        path_terms = _top_items(
            group["path_relativo"].fillna("").astype(str).map(lambda value: " ".join(_tokens(value))),
            limit=15,
        )
        phrases = []
        for phrase_blob in group["phrases"].fillna("").astype(str):
            phrases.extend([phrase for phrase in phrase_blob.split(" | ") if phrase])
        phrase_counts = Counter(phrases).most_common(15)

        summary_rows.append({
            "cluster_id": cluster_id,
            "qtd_pdfs": count,
            "percentual_corpus": round(count / total_docs, 4) if total_docs else 0,
            "exemplos": examples,
            "top_tokens": "; ".join(f"{term} ({freq})" for term, freq in top_text_tokens),
            "top_path_terms": "; ".join(f"{term} ({freq})" for term, freq in path_terms),
            "top_phrases": "; ".join(f"{phrase} ({freq})" for phrase, freq in phrase_counts[:8]),
            "suggested_document_type_id": "",
            "suggested_template_id": "",
            "review_status": "",
            "review_notes": "",
        })

        for source, candidates in [
            ("text_token", top_text_tokens),
            ("path_token", path_terms),
            ("text_phrase", phrase_counts),
        ]:
            for candidate, frequency in candidates:
                if source != "text_phrase" and len(candidate) < 4:
                    continue
                candidate_rows.append({
                    "cluster_id": cluster_id,
                    "source": source,
                    "candidate": candidate,
                    "suggested_regex": _regex_candidate(candidate),
                    "qtd_pdfs_cluster": count,
                    "qtd_ocorrencias": frequency,
                    "support_pct_cluster": round(frequency / count, 4) if count else 0,
                    "example_files": examples,
                    "promote_to": "",
                    "review_status": "",
                    "review_notes": "",
                })

    return pd.DataFrame(summary_rows), pd.DataFrame(candidate_rows)


def write_profile(clustered: pd.DataFrame, clusters: pd.DataFrame, candidates: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        clusters.to_excel(writer, sheet_name="clusters", index=False)
        candidates.to_excel(writer, sheet_name="regex_candidates", index=False)
        clustered.to_excel(writer, sheet_name="pdf_inventory", index=False)
        status = clustered["erro"].fillna("ok").value_counts().reset_index()
        status.columns = ["status", "quantidade"]
        status.to_excel(writer, sheet_name="summary", index=False)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Perfila um corpus de PDFs e gera grupos/padroes candidatos sem regra de negocio fixa.",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_DIR, help="Pasta raiz dos PDFs.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Excel de profiling do corpus.")
    parser.add_argument("--pages", type=int, default=3, help="Paginas lidas por PDF. Use 0 para ler todas.")
    parser.add_argument("--limit", type=int, default=None, help="Limite opcional de PDFs para amostra.")
    parser.add_argument("--cluster-threshold", type=float, default=0.42, help="Similaridade minima para entrar em um cluster.")
    parser.add_argument("--max-features", type=int, default=220, help="Maximo de features por PDF/cluster.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    max_pages = args.pages if args.pages > 0 else None
    inventory = build_inventory(args.input, max_pages=max_pages, limit=args.limit)
    clustered = assign_clusters(inventory, threshold=args.cluster_threshold, max_features=args.max_features)
    clusters, candidates = summarize_clusters(clustered)
    write_profile(clustered, clusters, candidates, args.output)
    print(f"Perfil do corpus salvo em: {args.output}")
    print(f"PDFs: {len(clustered)} | clusters: {len(clusters)} | candidatos: {len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
