from dataclasses import dataclass
from pathlib import Path

from ..core.outputs import PipelineOutputs


@dataclass
class DocumentExtraction:
    path: Path
    outputs: PipelineOutputs
    summary: dict
