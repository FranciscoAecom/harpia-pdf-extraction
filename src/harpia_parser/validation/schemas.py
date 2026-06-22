import re
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..constants import RESULTS_EXTRACT_COLUMNS


TIPO_REGISTRO = Literal["Amostra", "Branco", "Duplicata", "Recupera\u00e7\u00e3o"]
LOCAL = Literal["campo", "laboratorio"]
OPERADOR = Literal["max", "min", "<", ">", "<=", ">=", "="]
NUMERO_PT = re.compile(r"^([+-]?\d+(?:[,.]\d+)?)(?:\s*x\s*10\s*([+-]?\d+))?$", re.IGNORECASE)


def _parse_numero_pt(value: Any) -> float:
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    text = str(value).strip()
    match = NUMERO_PT.match(text)
    if not match:
        raise ValueError("valor deve ser numerico")
    number = float(match.group(1).replace(",", "."))
    exponent = match.group(2)
    return number * (10 ** int(exponent)) if exponent is not None else number


def _empty_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class ResultsExtractRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome_do_arquivo: str
    template_id: str
    tipo_laudo: str | None = None
    id_sample: int | str
    tipo: TIPO_REGISTRO
    categoria: str
    subcategoria: str | None = None
    parameter: str
    resultado: str | None = None
    resultado_tratado: float | None = None
    qualificador: Literal["<", ">"] | None = None
    unidade: str | None = None
    local: LOCAL
    data_inicio: str | None = Field(default=None, pattern=r"^\d{2}/\d{2}/\d{4}$")

    conama: str | None = None
    conama_operador: OPERADOR | None = None
    conama_minimo: float | None = None
    conama_maximo: float | None = None
    conama_unidade: str | None = None
    copam_cerh: str | None = None
    copam_cerh_operador: OPERADOR | None = None
    copam_cerh_minimo: float | None = None
    copam_cerh_maximo: float | None = None
    copam_cerh_unidade: str | None = None

    ld: str | None = None
    ld_minimo: float | None = None
    ld_maximo: float | None = None
    ld_unidade: str | None = None

    lq: str | None = None
    lq_minimo: float | None = None
    lq_maximo: float | None = None
    lq_unidade: str | None = None

    referencia: str | None = None
    incerteza: str | None = None
    incerteza_valor: float | None = None
    incerteza_unidade: str | None = None
    numero_cq: str | None = None
    duplicata: str | None = None

    faixa_aceitacao: str | None = None
    faixa_aceitacao_operador: OPERADOR | None = None
    faixa_aceitacao_minimo: float | None = None
    faixa_aceitacao_maximo: float | None = None
    faixa_aceitacao_unidade: str | None = None

    variacao_percentual: float | None = None
    quantidade_adicionada: float | None = None
    recuperacao_percentual: float | None = None

    @field_validator("*", mode="before")
    @classmethod
    def normalize_empty(cls, value: Any) -> Any:
        return _empty_to_none(value)

    @field_validator("nome_do_arquivo", "template_id", "id_sample", "categoria", "parameter")
    @classmethod
    def required_text(cls, value: Any) -> Any:
        if value is None or str(value).strip() == "":
            raise ValueError("campo obrigatorio vazio")
        return value

    @field_validator(
        "duplicata",
    )
    @classmethod
    def numeric_text(cls, value: Any) -> Any:
        if value is None:
            return value
        text = str(value).strip()
        if not NUMERO_PT.match(text):
            raise ValueError("valor deve ser numerico em formato texto")
        return text

    @field_validator(
        "resultado_tratado",
        "variacao_percentual",
        "quantidade_adicionada",
        "recuperacao_percentual",
        mode="before",
    )
    @classmethod
    def numeric_value(cls, value: Any) -> Any:
        if value is None:
            return value
        return _parse_numero_pt(value)

    @model_validator(mode="after")
    def validate_structured_measures(self) -> "ResultsExtractRow":
        self._validate_measure("conama")
        self._validate_measure("copam_cerh")
        self._validate_measure("ld")
        self._validate_measure("lq")
        self._validate_measure("faixa_aceitacao")
        return self

    def _validate_measure(self, prefix: str) -> None:
        minimo = getattr(self, f"{prefix}_minimo")
        maximo = getattr(self, f"{prefix}_maximo")

        if minimo is not None and maximo is not None and minimo > maximo:
            raise ValueError(f"{prefix}_minimo maior que {prefix}_maximo")


def validate_results_extract(df: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [column for column in RESULTS_EXTRACT_COLUMNS if column not in df.columns]
    extra_columns = [column for column in df.columns if column not in RESULTS_EXTRACT_COLUMNS]
    errors: list[dict[str, Any]] = []

    for column in missing_columns:
        errors.append({
            "row_number": None,
            "id_sample": None,
            "parameter": None,
            "field": column,
            "error_type": "missing_column",
            "message": "Coluna obrigatoria ausente.",
            "value": None,
        })

    for column in extra_columns:
        errors.append({
            "row_number": None,
            "id_sample": None,
            "parameter": None,
            "field": column,
            "error_type": "extra_column",
            "message": "Coluna nao prevista no schema.",
            "value": None,
        })

    if missing_columns:
        return pd.DataFrame(errors)

    for row_index, (_, row) in enumerate(df[RESULTS_EXTRACT_COLUMNS].iterrows(), start=2):
        payload = {column: _empty_to_none(row[column]) for column in RESULTS_EXTRACT_COLUMNS}
        try:
            ResultsExtractRow.model_validate(payload)
        except ValidationError as exc:
            for error in exc.errors():
                field = ".".join(str(part) for part in error["loc"]) or "__row__"
                errors.append({
                    "row_number": row_index,
                    "id_sample": payload.get("id_sample"),
                    "parameter": payload.get("parameter"),
                    "field": field,
                    "error_type": error["type"],
                    "message": error["msg"],
                    "value": payload.get(field),
                })

    return pd.DataFrame(
        errors,
        columns=["row_number", "id_sample", "parameter", "field", "error_type", "message", "value"],
    )


def validate_outputs(
    df: pd.DataFrame,
    sample_df: pd.DataFrame | None = None,
    client_df: pd.DataFrame | None = None,
    output_tabs: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    sheets = output_tabs or [
        "results_extract",
        "sample",
        "client",
        "table_extraction_audit",
        "classification_audit",
        "validation_errors",
    ]
    validations: dict[str, pd.DataFrame] = {}
    if "results_extract" in sheets:
        validations["results_extract"] = validate_results_extract(df)
    return validations
