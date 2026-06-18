import argparse
import hashlib
import re
from pathlib import Path
from typing import Sequence

import pandas as pd
import pdfplumber


DEFAULT_INPUT_DIR = Path(r"L:\Secure_DCS\BRBLH1PINFW001\COE_Digital\others\harpia_rd")
DEFAULT_OUTPUT = Path("output/taxonomy_discovery/pdf_inventory.xlsx")


def _list_pdfs(input_dir: Path, limit: int | None = None) -> list[Path]:
    pdfs = sorted(input_dir.rglob("*.pdf"))
    return pdfs[:limit] if limit else pdfs


def _extract_text(pdf_path: Path, max_pages: int | None) -> tuple[str, int]:
    parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        for page in pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts), page_count


def _tokenize(value: str) -> str:
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", value.lower())
    return " ".join(sorted(set(tokens)))


def _path_parts(path: Path, root: Path) -> list[str]:
    try:
        return list(path.relative_to(root).parts)
    except ValueError:
        return list(path.parts)


def build_inventory(input_dir: Path, max_pages: int | None, limit: int | None = None) -> pd.DataFrame:
    rows = []
    for index, pdf_path in enumerate(_list_pdfs(input_dir, limit), start=1):
        print(f"[{index}] {pdf_path}")
        parts = _path_parts(pdf_path, input_dir)
        try:
            text, page_count = _extract_text(pdf_path, max_pages)
            error = None
        except Exception as exc:
            text = ""
            page_count = 0
            error = f"{type(exc).__name__}: {exc}"

        text_sample = re.sub(r"\s+", " ", text).strip()[:4000]
        hash_text = hashlib.sha1(text_sample.encode("utf-8", errors="ignore")).hexdigest()
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
            "text_hash": hash_text,
            "text_sample": text_sample,
            "tokens": _tokenize(" ".join(parts) + " " + pdf_path.stem + " " + text_sample),
            "erro": error,
        })
    return pd.DataFrame(rows)


def write_inventory(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="pdf_inventory", index=False)
        summary = (
            df.assign(status=df["erro"].fillna("ok"))
            .groupby(["pasta_nivel_1", "status"], dropna=False)
            .size()
            .reset_index(name="quantidade")
        )
        summary.to_excel(writer, sheet_name="summary", index=False)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cria inventario textual agnostico de uma pasta de PDFs.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_DIR, help="Pasta raiz dos PDFs.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Arquivo Excel de inventario.")
    parser.add_argument("--pages", type=int, default=3, help="Paginas lidas por PDF. Use 0 para ler todas.")
    parser.add_argument("--limit", type=int, default=None, help="Limite opcional de PDFs para amostra.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    max_pages = args.pages if args.pages > 0 else None
    df = build_inventory(args.input, max_pages=max_pages, limit=args.limit)
    write_inventory(df, args.output)
    print(f"Inventario salvo em: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
