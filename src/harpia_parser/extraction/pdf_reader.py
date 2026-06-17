from pathlib import Path

import pdfplumber


def read_pdf(pdf_path: Path) -> tuple[str, list[tuple[str, list]]]:
    texto = ""
    paginas = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            texto += page_text
            paginas.append((page_text, page.extract_tables() or []))

    return texto, paginas
