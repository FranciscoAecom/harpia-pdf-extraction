from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class TemplateScore:
    template_id: str
    score: float
    score_minimo: float
    prioridade: int
    status: str
    matched_rules: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClassificationResult:
    template_id: str | None
    tipo_laudo: str | None
    id_taxonomia: int | str | None
    nome_taxonomia: str | None
    scores: list[TemplateScore]

    def to_dataframe(self, nome_do_arquivo: str) -> pd.DataFrame:
        rows = []
        for score in self.scores:
            rows.append({
                "nome_do_arquivo": nome_do_arquivo,
                "id_taxonomia": self.id_taxonomia,
                "nome_taxonomia": self.nome_taxonomia,
                "template_avaliado": score.template_id,
                "score": score.score,
                "score_minimo": score.score_minimo,
                "prioridade": score.prioridade,
                "status": score.status,
                "regras_encontradas": "; ".join(score.matched_rules),
            })
        return pd.DataFrame(rows, columns=[
            "nome_do_arquivo",
            "id_taxonomia",
            "nome_taxonomia",
            "template_avaliado",
            "score",
            "score_minimo",
            "prioridade",
            "status",
            "regras_encontradas",
        ])


@dataclass(frozen=True)
class DocumentContext:
    pdf_path: Path
    nome_do_arquivo: str
    template_id: str
    tipo_laudo: str | None
    id_taxonomia: int | str | None
    nome_taxonomia: str | None
    classification: ClassificationResult
