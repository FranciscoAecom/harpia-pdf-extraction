from dataclasses import dataclass
from pathlib import Path

from .cache import BatchCache
from .discovery import read_pdf_text
from ..config.loader import PipelineConfig
from ..core.outputs import PipelineOutputs
from ..core.pipeline import run_pipeline_document
from ..core.scope import classify_document
from ..extraction.pdf_reader import read_pdf


@dataclass
class ExtractionResult:
    path: Path
    text: str | None
    outputs: PipelineOutputs | None
    error: Exception | None
    from_cache: bool = False


def extract_pdf_once(
    pdf: Path,
    config: PipelineConfig,
    file_hash: str,
    runtime_signature: str,
    cache: BatchCache,
    preclassify_pages: int,
) -> ExtractionResult:
    try:
        cached = cache.load_extraction(runtime_signature, file_hash)
        if cached is not None:
            text, outputs = cached
            return ExtractionResult(pdf, text, outputs, None, True)
        preview = read_pdf_text(pdf, max_pages=preclassify_pages) if preclassify_pages > 0 else ""
        if preview and not classify_document(preview, config, pdf).template_id:
            text = preview
            outputs = run_pipeline_document(pdf, config, pdf_content=(preview, [(preview, [])]))
        else:
            text, pages = read_pdf(pdf)
            outputs = run_pipeline_document(pdf, config, pdf_content=(text, pages))
        cache.save_extraction(runtime_signature, file_hash, text, outputs)
        return ExtractionResult(pdf, text, outputs, None)
    except Exception as exc:
        return ExtractionResult(pdf, None, None, exc)
