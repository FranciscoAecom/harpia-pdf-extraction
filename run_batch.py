import argparse
import logging
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harpia_parser.config.loader import load_config, output_sheets_for_template  # noqa: E402
from harpia_parser.core.pipeline import run_pipeline_document  # noqa: E402
from harpia_parser.core.scope import classify_document  # noqa: E402
from harpia_parser.extraction.pdf_reader import read_pdf  # noqa: E402
from harpia_parser.formatting.output_writer import salvar  # noqa: E402


DEFAULT_INPUT_DIR = Path(r"L:\Secure_DCS\BRBLH1PINFW001\COE_Digital\others\harpia_rd")
log = logging.getLogger(__name__)


def _first_value(dataframes: list[pd.DataFrame], column: str) -> str | None:
    for dataframe in dataframes:
        if column in dataframe.columns and not dataframe.empty:
            values = dataframe[column].dropna()
            if not values.empty:
                return str(values.iloc[0])
    return None


def _list_pdfs(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Pasta de entrada nao encontrada: {input_dir}")
    return sorted(input_dir.rglob("*.pdf"))


def classify_batch(input_dir: Path, output_path: Path) -> None:
    config = load_config(ROOT)
    rows = []
    pdfs = _list_pdfs(input_dir)

    for index, pdf in enumerate(pdfs, start=1):
        log.info("[%d/%d] Classificando %s", index, len(pdfs), pdf.name)
        try:
            texto, _ = read_pdf(pdf)
            result = classify_document(texto, config, pdf)
            rows.append({
                "arquivo": pdf.name,
                "caminho": str(pdf),
                "template_id": result.template_id,
                "tipo_laudo": result.tipo_laudo,
                "status": "identificado" if result.template_id else "fora_escopo",
                "scores": "; ".join(
                    f"{score.template_id}:{score.status}:{score.score}/{score.score_minimo}"
                    for score in result.scores
                ),
            })
        except Exception as exc:
            rows.append({
                "arquivo": pdf.name,
                "caminho": str(pdf),
                "template_id": None,
                "tipo_laudo": None,
                "status": "erro",
                "scores": f"{type(exc).__name__}: {exc}",
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(output_path, index=False)
    log.info("Auditoria de classificacao salva em: %s", output_path)


def extract_batch(input_dir: Path, output_dir: Path) -> None:
    config = load_config(ROOT)
    all_results: dict[str, list[pd.DataFrame]] = {}
    all_samples: dict[str, list[pd.DataFrame]] = {}
    all_clients: dict[str, list[pd.DataFrame]] = {}
    all_audits: dict[str, list[pd.DataFrame]] = {}
    summary = []
    pdfs = _list_pdfs(input_dir)

    for index, pdf in enumerate(pdfs, start=1):
        log.info("[%d/%d] Extraindo %s", index, len(pdfs), pdf.name)
        try:
            df, sample_df, client_df, audit_df = run_pipeline_document(pdf, config)
            template_id = _first_value([df, sample_df, client_df], "template_id")
            tipo_laudo = _first_value([df, sample_df, client_df], "tipo_laudo")

            if not template_id or not tipo_laudo:
                summary.append({
                    "arquivo": pdf.name,
                    "caminho": str(pdf),
                    "status": "fora_escopo",
                    "template_id": None,
                    "tipo_laudo": None,
                    "results_rows": 0,
                    "sample_rows": 0,
                    "client_rows": 0,
                })
                continue

            all_results.setdefault(tipo_laudo, []).append(df)
            all_samples.setdefault(tipo_laudo, []).append(sample_df)
            all_clients.setdefault(tipo_laudo, []).append(client_df)
            all_audits.setdefault(tipo_laudo, []).append(audit_df)
            summary.append({
                "arquivo": pdf.name,
                "caminho": str(pdf),
                "status": "extraido",
                "template_id": template_id,
                "tipo_laudo": tipo_laudo,
                "results_rows": len(df),
                "sample_rows": len(sample_df),
                "client_rows": len(client_df),
            })
        except Exception as exc:
            summary.append({
                "arquivo": pdf.name,
                "caminho": str(pdf),
                "status": "erro",
                "template_id": None,
                "tipo_laudo": None,
                "results_rows": 0,
                "sample_rows": 0,
                "client_rows": 0,
                "erro": f"{type(exc).__name__}: {exc}",
            })

    output_dir.mkdir(parents=True, exist_ok=True)
    for tipo_laudo in sorted(set(all_results) | set(all_samples) | set(all_clients)):
        results_df = pd.concat(all_results.get(tipo_laudo, []), ignore_index=True) if all_results.get(tipo_laudo) else pd.DataFrame()
        sample_df = pd.concat(all_samples.get(tipo_laudo, []), ignore_index=True) if all_samples.get(tipo_laudo) else pd.DataFrame()
        client_df = pd.concat(all_clients.get(tipo_laudo, []), ignore_index=True) if all_clients.get(tipo_laudo) else pd.DataFrame()
        audit_df = pd.concat(all_audits.get(tipo_laudo, []), ignore_index=True) if all_audits.get(tipo_laudo) else pd.DataFrame()

        template_id = _first_value([results_df, sample_df, client_df], "template_id")
        output_sheets = output_sheets_for_template(config, template_id) if template_id else None
        salvar(
            results_df,
            output_dir / tipo_laudo / "extracted_data.xlsx",
            sample_df=sample_df,
            client_df=client_df,
            output_sheets=output_sheets,
            classification_audit_df=audit_df,
        )

    summary_df = pd.DataFrame(summary)
    summary_path = output_dir / "batch_extraction_summary.xlsx"
    summary_df.to_excel(summary_path, index=False)
    log.info("Resumo salvo em: %s", summary_path)
    if not summary_df.empty:
        log.info("Status:\n%s", summary_df["status"].value_counts(dropna=False).to_string())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Processa lotes de PDFs do Harpia.")
    parser.add_argument(
        "mode",
        choices=["classify", "extract"],
        help="Use classify para auditar templates ou extract para extrair os dados.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Pasta raiz contendo PDFs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output",
        help="Pasta de saida.",
    )
    args = parser.parse_args(argv)

    if args.mode == "classify":
        classify_batch(args.input, args.output / "template_classification_audit.xlsx")
    else:
        extract_batch(args.input, args.output)
    return 0


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


if __name__ == "__main__":
    sys.exit(main())
