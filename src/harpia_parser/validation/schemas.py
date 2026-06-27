import re
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..constants import (
    ACM_EXTRACTION_TIMESTAMP_COLUMN,
    CLIENT_COLUMNS,
    PACKAGING_PRESERVATIVES_COLUMNS,
    RESULTS_EXTRACT_COLUMNS,
    SAMPLE_COLUMNS,
)
from ..parsing.measure_parser import possui_unidade_aparente, texto_vazio, unidade_from_partes
from ..utils import normalizar


TIPO_REGISTRO = Literal["Amostra", "Branco", "Duplicata", "Recupera\u00e7\u00e3o"]
LOCAL = Literal["campo", "laboratorio"]
OPERADOR = Literal["max", "min", "<", ">", "<=", ">=", "="]
NUMERO_PT = re.compile(r"^([+-]?\d+(?:[,.]\d+)?)(?:\s*x\s*10\s*([+-]?\d+))?$", re.IGNORECASE)
DATA_PT = r"^\d{2}/\d{2}/\d{4}$"
HORA_PT = r"^\d{2}:\d{2}(?::\d{2})?$"
DATA_HORA_PT = r"^\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?$"


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


def _parse_decimal_pt(value: Any) -> float:
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    return float(str(value).strip().replace(",", "."))


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
    id_taxonomia: int
    nome_taxonomia: str | None = None
    versao_template: int | None = None
    acm_data_hora_extracao: str | None = Field(default=None, pattern=DATA_HORA_PT)
    id_amostra: int
    tipo: TIPO_REGISTRO
    categoria: str
    subcategoria: str | None = None
    codigo_laudo: str | None = None
    acm_codigo_laudo: str | None = None
    codigo_laudo_substituido: str | None = None
    parameter: str
    resultado: str | None = None
    unidade: str | None = None
    acm_resultado_tratado: float | None = None
    acm_qualificador: Literal["<", ">"] | None = None
    acm_unidade: str | None = None
    local: LOCAL
    data_inicio: str | None = Field(default=None, pattern=DATA_PT)
    acm_data_inicio: str | None = Field(default=None, pattern=DATA_HORA_PT)

    conama: str | None = None
    acm_conama_operador: OPERADOR | None = None
    acm_conama_minimo: float | None = None
    acm_conama_maximo: float | None = None
    acm_conama_unidade: str | None = None
    copam_cerh: str | None = None
    acm_copam_cerh_operador: OPERADOR | None = None
    acm_copam_cerh_minimo: float | None = None
    acm_copam_cerh_maximo: float | None = None
    acm_copam_cerh_unidade: str | None = None

    ld: str | None = None
    acm_ld_minimo: float | None = None
    acm_ld_maximo: float | None = None
    acm_ld_unidade: str | None = None

    lq: str | None = None
    acm_lq_minimo: float | None = None
    acm_lq_maximo: float | None = None
    acm_lq_unidade: str | None = None

    referencia: str | None = None
    incerteza: str | None = None
    acm_incerteza_valor: float | None = None
    acm_incerteza_unidade: str | None = None
    numero_cq: str | None = None
    duplicata: str | None = None

    faixa_aceitacao: str | None = None
    acm_faixa_aceitacao_operador: OPERADOR | None = None
    acm_faixa_aceitacao_minimo: float | None = None
    acm_faixa_aceitacao_maximo: float | None = None
    acm_faixa_aceitacao_unidade: str | None = None

    variacao_percentual: float | None = None
    quantidade_adicionada: float | None = None
    recuperacao_percentual: float | None = None

    @field_validator("*", mode="before")
    @classmethod
    def normalize_empty(cls, value: Any) -> Any:
        return _empty_to_none(value)

    @field_validator("nome_do_arquivo", "id_taxonomia", "id_amostra", "categoria", "parameter")
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
        "acm_resultado_tratado",
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
        self._validate_derived_field_lineage()
        self._validate_units_from_original_text()
        return self

    def _validate_measure(self, prefix: str) -> None:
        minimo = getattr(self, f"acm_{prefix}_minimo")
        maximo = getattr(self, f"acm_{prefix}_maximo")

        if minimo is not None and maximo is not None and minimo > maximo:
            raise ValueError(f"acm_{prefix}_minimo maior que acm_{prefix}_maximo")

    def _validate_derived_field_lineage(self) -> None:
        lineage = {
            "codigo_laudo": ["acm_codigo_laudo"],
            "data_inicio": ["acm_data_inicio"],
            "resultado": ["acm_resultado_tratado", "acm_qualificador"],
            "conama": ["acm_conama_operador", "acm_conama_minimo", "acm_conama_maximo"],
            "copam_cerh": [
                "acm_copam_cerh_operador",
                "acm_copam_cerh_minimo",
                "acm_copam_cerh_maximo",
            ],
            "ld": ["acm_ld_minimo", "acm_ld_maximo"],
            "lq": ["acm_lq_minimo", "acm_lq_maximo"],
            "incerteza": ["acm_incerteza_valor"],
            "faixa_aceitacao": [
                "acm_faixa_aceitacao_operador",
                "acm_faixa_aceitacao_minimo",
                "acm_faixa_aceitacao_maximo",
            ],
        }
        for source_field, derived_fields in lineage.items():
            if getattr(self, source_field) is not None:
                continue
            for derived_field in derived_fields:
                if getattr(self, derived_field) is not None:
                    raise ValueError(f"{derived_field} preenchido com {source_field} vazio")

    def _validate_units_from_original_text(self) -> None:
        for source_field, unit_field in [
            ("resultado", "acm_unidade"),
            ("conama", "acm_conama_unidade"),
            ("copam_cerh", "acm_copam_cerh_unidade"),
            ("ld", "acm_ld_unidade"),
            ("lq", "acm_lq_unidade"),
            ("incerteza", "acm_incerteza_unidade"),
            ("faixa_aceitacao", "acm_faixa_aceitacao_unidade"),
        ]:
            source_value = getattr(self, source_field)
            parsed_unit = getattr(self, unit_field)
            if source_value is None:
                if parsed_unit is not None:
                    raise ValueError(f"{unit_field} preenchido com campo de origem vazio")
                continue
            if source_field in {"conama", "copam_cerh"} and _complex_normative_note(source_value):
                continue
            expected_unit = unidade_from_partes([source_value])
            unit_is_present = expected_unit is not None or possui_unidade_aparente(source_value)
            if source_field == "resultado" and not texto_vazio(self.unidade):
                unit_is_present = True
            if unit_is_present and parsed_unit is None:
                raise ValueError(f"{unit_field} vazio para texto com unidade: {source_value}")
            if not unit_is_present and parsed_unit is not None:
                raise ValueError(f"{unit_field} preenchido sem unidade no campo de origem: {source_value}")


def _complex_normative_note(value: Any) -> bool:
    text = str(value or "")
    normalized = normalizar(text)
    return "para ph" in normalized and len(re.findall(r"\d+(?:[,.]\d+)?\s*mg/l", normalized)) > 1


class PackagingPreservativesRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome_do_arquivo: str
    id_taxonomia: int
    nome_taxonomia: str | None = None
    versao_template: int | None = None
    acm_data_hora_extracao: str | None = Field(default=None, pattern=DATA_HORA_PT)
    id_amostra: int
    identificacao_amostra: str
    embalagem: str
    volume: str
    preservacao: str
    metodos: str

    @field_validator("*", mode="before")
    @classmethod
    def normalize_empty(cls, value: Any) -> Any:
        return _empty_to_none(value)

    @field_validator(
        "nome_do_arquivo",
        "id_taxonomia",
        "id_amostra",
        "identificacao_amostra",
        "embalagem",
        "volume",
        "preservacao",
        "metodos",
    )
    @classmethod
    def required_text(cls, value: Any) -> Any:
        if value is None or str(value).strip() == "":
            raise ValueError("campo obrigatorio vazio")
        return value


class SampleRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome_do_arquivo: str
    id_taxonomia: int
    nome_taxonomia: str | None = None
    versao_template: int | None = None
    acm_data_hora_extracao: str | None = Field(default=None, pattern=DATA_HORA_PT)
    id_amostra: int
    identificacao_amostra: str | None = None
    tipo_amostra: str | None = None
    criterio_conformidade: str | None = None
    data_coleta: str | None = Field(default=None, pattern=DATA_HORA_PT)
    data_publicacao: str | None = Field(default=None, pattern=DATA_HORA_PT)
    data_recebimento: str | None = Field(default=None, pattern=DATA_HORA_PT)
    observacoes: str | None = None
    localizacao: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    latitude_real: float | None = None
    longitude_real: float | None = None
    condicoes_climaticas_nas_ultimas_24_horas: str | None = None
    condicoes_climaticas_no_momento_da_coleta: str | None = None
    tipo_coleta: str | None = None
    responsavel_amostra: str | None = None
    planejamento_amostragem: str | None = None
    descricao_nao_conformidade: str | None = None
    codigo_laudo_substituido: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def normalize_empty(cls, value: Any) -> Any:
        return _empty_to_none(value)

    @field_validator("nome_do_arquivo", "id_taxonomia", "id_amostra")
    @classmethod
    def required_text(cls, value: Any) -> Any:
        if value is None or str(value).strip() == "":
            raise ValueError("campo obrigatorio vazio")
        return value

    @field_validator("latitude", "longitude", "latitude_real", "longitude_real", mode="before")
    @classmethod
    def decimal_value(cls, value: Any) -> Any:
        if value is None:
            return value
        try:
            return _parse_decimal_pt(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("valor deve ser decimal") from exc


class ClientRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome_do_arquivo: str
    id_taxonomia: int
    nome_taxonomia: str | None = None
    versao_template: int | None = None
    acm_data_hora_extracao: str | None = Field(default=None, pattern=DATA_HORA_PT)
    id_amostra: int
    proposta_comercial: str | None = None
    cliente: str | None = None
    cnpj_cpf: str | None = None
    contato: str | None = None
    telefone: str | None = None
    endereco: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def normalize_empty(cls, value: Any) -> Any:
        return _empty_to_none(value)

    @field_validator("nome_do_arquivo", "id_taxonomia", "id_amostra")
    @classmethod
    def required_text(cls, value: Any) -> Any:
        if value is None or str(value).strip() == "":
            raise ValueError("campo obrigatorio vazio")
        return value


VALIDATION_ERROR_COLUMNS = [
    ACM_EXTRACTION_TIMESTAMP_COLUMN,
    "sheet",
    "row_number",
    "id_amostra",
    "parameter",
    "field",
    "error_type",
    "message",
    "value",
]


def _error_frame(errors: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(errors, columns=VALIDATION_ERROR_COLUMNS)


def _validate_dataframe(
    df: pd.DataFrame,
    *,
    sheet_name: str,
    expected_columns: list[str],
    row_model: type[BaseModel],
    parameter_field: str | None = None,
) -> pd.DataFrame:
    missing_columns = [column for column in expected_columns if column not in df.columns]
    extra_columns = [column for column in df.columns if column not in expected_columns]
    errors: list[dict[str, Any]] = []

    for column in missing_columns:
        errors.append({
            "sheet": sheet_name,
            "row_number": None,
            "id_amostra": None,
            "parameter": None,
            "field": column,
            "error_type": "missing_column",
            "message": "Coluna obrigatoria ausente.",
            "value": None,
        })

    for column in extra_columns:
        errors.append({
            "sheet": sheet_name,
            "row_number": None,
            "id_amostra": None,
            "parameter": None,
            "field": column,
            "error_type": "extra_column",
            "message": "Coluna nao prevista no schema.",
            "value": None,
        })

    if missing_columns:
        return _error_frame(errors)

    for row_index, (_, row) in enumerate(df[expected_columns].iterrows(), start=2):
        payload = {column: _empty_to_none(row[column]) for column in expected_columns}
        try:
            row_model.model_validate(payload)
        except ValidationError as exc:
            for error in exc.errors():
                field = ".".join(str(part) for part in error["loc"]) or "__row__"
                for suffix in (".int", ".str", ".float"):
                    if field.endswith(suffix):
                        field = field[: -len(suffix)]
                errors.append({
                    "sheet": sheet_name,
                    "row_number": row_index,
                    "id_amostra": payload.get("id_amostra"),
                    "parameter": payload.get(parameter_field) if parameter_field else None,
                    "field": field,
                    "error_type": error["type"],
                    "message": error["msg"],
                    "value": payload.get(field),
                })

    return _error_frame(errors)


def validate_results_extract(df: pd.DataFrame) -> pd.DataFrame:
    return _validate_dataframe(
        df,
        sheet_name="results_extract",
        expected_columns=RESULTS_EXTRACT_COLUMNS,
        row_model=ResultsExtractRow,
        parameter_field="parameter",
    )


def validate_packaging_preservatives(df: pd.DataFrame) -> pd.DataFrame:
    return _validate_dataframe(
        df,
        sheet_name="packaging_preservatives",
        expected_columns=PACKAGING_PRESERVATIVES_COLUMNS,
        row_model=PackagingPreservativesRow,
        parameter_field="metodos",
    )


def validate_sample(df: pd.DataFrame) -> pd.DataFrame:
    return _validate_dataframe(
        df,
        sheet_name="sample",
        expected_columns=SAMPLE_COLUMNS,
        row_model=SampleRow,
    )


def validate_client(df: pd.DataFrame) -> pd.DataFrame:
    return _validate_dataframe(
        df,
        sheet_name="client",
        expected_columns=CLIENT_COLUMNS,
        row_model=ClientRow,
    )


def validate_outputs(
    df: pd.DataFrame,
    sample_df: pd.DataFrame | None = None,
    client_df: pd.DataFrame | None = None,
    packaging_preservatives_df: pd.DataFrame | None = None,
    output_tabs: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    sheets = output_tabs or [
        "results_extract",
        "sample",
        "client",
        "packaging_preservatives",
        "table_extraction_audit",
        "classification_audit",
        "validation_errors",
    ]
    validations: dict[str, pd.DataFrame] = {}
    if "results_extract" in sheets:
        validations["results_extract"] = validate_results_extract(df)
    if "sample" in sheets and sample_df is not None:
        validations["sample"] = validate_sample(sample_df)
    if "client" in sheets and client_df is not None:
        validations["client"] = validate_client(client_df)
    if "packaging_preservatives" in sheets and packaging_preservatives_df is not None:
        validations["packaging_preservatives"] = validate_packaging_preservatives(packaging_preservatives_df)
    return validations
