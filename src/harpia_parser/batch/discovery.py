from pathlib import Path

import pdfplumber


def list_pdfs(input_dirs: list[Path]) -> list[Path]:
    pdfs: dict[str, Path] = {}
    for input_dir in input_dirs:
        if not input_dir.exists():
            raise FileNotFoundError(f"Pasta de entrada nao encontrada: {input_dir}")
        for pdf in input_dir.rglob("*.pdf"):
            pdfs[str(pdf)] = pdf
    return sorted(pdfs.values(), key=lambda path: str(path).lower())


def read_pdf_text(pdf_path: Path, max_pages: int | None = None) -> str:
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        for page in pages:
            texts.append(page.extract_text() or "")
    return "\n".join(texts)

