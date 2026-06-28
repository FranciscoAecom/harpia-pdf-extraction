from __future__ import annotations

from typing import Any
from datetime import date, datetime
import re

import pandas as pd

from ..constants import DOCUMENT_RECONCILIATION_AUDIT_COLUMNS


OK_TABLE_STATUSES = {
    "ok",
    "ok_com_opcional_ausente",
    "fallback_layout_confiavel",
    "fallback_cabecalho_texto_layout_confiavel",
}
OK_SECTION_STATUSES = {"ok", "nao_aplicavel"}
OK_FIELD_STATUSES = {"ok", "nao_aplicavel"}


def _for_document(frame: pd.DataFrame | None, filename: str) -> pd.DataFrame:
    if frame is None or frame.empty or "nome_do_arquivo" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["nome_do_arquivo"].astype(str) == filename]


def _index_by(frame: pd.DataFrame | None, column: str) -> dict[str, pd.DataFrame]:
    if frame is None or frame.empty or column not in frame.columns:
        return {}
    keys = frame[column].fillna("").astype(str)
    return {
        str(key): frame.iloc[indices]
        for key, indices in keys.groupby(keys, sort=False).indices.items()
        if str(key)
    }


def _first(frames: list[pd.DataFrame], column: str) -> Any:
    for frame in frames:
        if not frame.empty and column in frame.columns:
            values = frame[column].dropna()
            if not values.empty:
                return values.iloc[0]
    return None


def _identity_issue(frames: list[pd.DataFrame], column: str) -> bool:
    values: set[str] = set()
    for frame in frames:
        if not frame.empty and column in frame.columns:
            values.update(str(value).strip() for value in frame[column].dropna() if str(value).strip())
    return len(values) > 1


def _alert_count(frame: pd.DataFrame, accepted: set[str]) -> int:
    if frame.empty or "status" not in frame.columns:
        return 0
    return int((~frame["status"].fillna("").astype(str).isin(accepted)).sum())


def _temporal_consistency(sample: pd.DataFrame) -> tuple[str, str | None]:
    if sample.empty:
        return "nao_avaliado", None
    fields = ["data_coleta", "data_recebimento", "data_publicacao"]
    values: list[pd.Timestamp | None] = []
    for field in fields:
        raw = sample.iloc[0].get(field) if field in sample.columns else None
        if isinstance(raw, (date, datetime, pd.Timestamp)):
            parsed = pd.Timestamp(raw)
        else:
            text = str(raw or "").strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}", text):
                parsed = pd.to_datetime(text, errors="coerce")
            else:
                parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
        values.append(None if pd.isna(parsed) else parsed)
    available = [value for value in values if value is not None]
    if len(available) < 2:
        return "nao_avaliado", None
    if available != sorted(available):
        return "inconsistente", "Ordem temporal esperada: coleta <= recebimento <= publicacao."
    return "ok", None


def _unit_divergence_count(results: pd.DataFrame) -> int:
    if results.empty or "parametro" not in results.columns:
        return 0
    unit_column = "acm_unidade" if "acm_unidade" in results.columns else "unidade_resultado"
    if unit_column not in results.columns:
        return 0
    pairs = results[["parametro", unit_column]].dropna()
    pairs = pairs[(pairs["parametro"].astype(str).str.strip() != "") & (pairs[unit_column].astype(str).str.strip() != "")]
    if pairs.empty:
        return 0
    counts = pairs.groupby("parametro")[unit_column].nunique()
    return int((counts > 1).sum())


def build_document_reconciliation_audit(
    results: pd.DataFrame,
    sample: pd.DataFrame | None,
    client: pd.DataFrame | None,
    packaging: pd.DataFrame | None,
    table_audit: pd.DataFrame | None,
    section_audit: pd.DataFrame | None,
    field_audit: pd.DataFrame | None,
    validation_errors: pd.DataFrame | None,
) -> pd.DataFrame:
    sources = [frame for frame in [results, sample, client] if frame is not None and not frame.empty]
    filenames = sorted({
        str(value)
        for frame in sources
        if "nome_do_arquivo" in frame.columns
        for value in frame["nome_do_arquivo"].dropna()
    })
    indexes = {
        "results": _index_by(results, "nome_do_arquivo"),
        "sample": _index_by(sample, "nome_do_arquivo"),
        "client": _index_by(client, "nome_do_arquivo"),
        "packaging": _index_by(packaging, "nome_do_arquivo"),
        "table": _index_by(table_audit, "nome_do_arquivo"),
        "section": _index_by(section_audit, "nome_do_arquivo"),
        "field": _index_by(field_audit, "nome_do_arquivo"),
        "validation_file": _index_by(validation_errors, "nome_do_arquivo"),
        "validation_sample": _index_by(validation_errors, "id_amostra"),
    }
    rows: list[dict[str, Any]] = []
    for filename in filenames:
        result_rows = indexes["results"].get(filename, pd.DataFrame())
        sample_rows = indexes["sample"].get(filename, pd.DataFrame())
        client_rows = indexes["client"].get(filename, pd.DataFrame())
        packaging_rows = indexes["packaging"].get(filename, pd.DataFrame())
        table_rows = indexes["table"].get(filename, pd.DataFrame())
        section_rows = indexes["section"].get(filename, pd.DataFrame())
        field_rows = indexes["field"].get(filename, pd.DataFrame())
        identity_frames = [result_rows, sample_rows, client_rows, packaging_rows]
        document_sample_id = _first(identity_frames, "id_amostra")
        validation_rows = indexes["validation_file"].get(filename, pd.DataFrame())
        if validation_rows.empty and validation_errors is not None and not validation_errors.empty and "id_amostra" in validation_errors.columns and document_sample_id is not None:
            validation_rows = indexes["validation_sample"].get(str(document_sample_id), pd.DataFrame())

        issues: list[str] = []
        if result_rows.empty:
            issues.append("Nenhum resultado extraido.")
        if len(sample_rows) != 1:
            issues.append(f"Cardinalidade de sample diferente de 1: {len(sample_rows)}.")
        if len(client_rows) != 1:
            issues.append(f"Cardinalidade de client diferente de 1: {len(client_rows)}.")
        for column in ["id_amostra", "id_taxonomia", "nome_taxonomia", "versao_template"]:
            if _identity_issue(identity_frames, column):
                issues.append(f"Valores divergentes entre abas para {column}.")

        table_alerts = _alert_count(table_rows, OK_TABLE_STATUSES)
        section_alerts = _alert_count(section_rows, OK_SECTION_STATUSES)
        field_alerts = _alert_count(field_rows, OK_FIELD_STATUSES)
        if table_alerts:
            issues.append(f"Alertas de tabela: {table_alerts}.")
        if section_alerts:
            issues.append(f"Alertas de secao: {section_alerts}.")
        if field_alerts:
            issues.append(f"Alertas de campo: {field_alerts}.")

        missing_parameters = 0
        if not result_rows.empty and "parametro" in result_rows.columns:
            missing_parameters = int(result_rows["parametro"].fillna("").astype(str).str.strip().eq("").sum())
            if missing_parameters:
                issues.append(f"Resultados sem parametro: {missing_parameters}.")
        unit_divergences = _unit_divergence_count(result_rows)
        if unit_divergences:
            issues.append(f"Parametros com mais de uma unidade no documento: {unit_divergences}.")

        temporal_status, temporal_issue = _temporal_consistency(sample_rows)
        if temporal_issue:
            issues.append(temporal_issue)

        errors_count = len(validation_rows)
        if errors_count:
            issues.append(f"Erros de validacao associados ao documento: {errors_count}.")
        status = "erro" if any("Cardinalidade" in issue or "Valores divergentes" in issue or "Nenhum resultado" in issue for issue in issues) else "alerta" if issues or errors_count else "ok"
        rows.append({
            "nome_do_arquivo": filename,
            "id_taxonomia": _first(identity_frames, "id_taxonomia"),
            "nome_taxonomia": _first(identity_frames, "nome_taxonomia"),
            "versao_template": _first(identity_frames, "versao_template"),
            "id_amostra": document_sample_id,
            "resultados_extraidos": len(result_rows),
            "registros_sample": len(sample_rows),
            "registros_client": len(client_rows),
            "embalagens_extraidas": len(packaging_rows),
            "tabelas_auditadas": len(table_rows),
            "secoes_auditadas": len(section_rows),
            "alertas_tabela": table_alerts,
            "alertas_secao": section_alerts,
            "alertas_campo": field_alerts,
            "erros_validacao": errors_count,
            "parametros_sem_nome": missing_parameters,
            "parametros_com_unidades_divergentes": unit_divergences,
            "coerencia_temporal": temporal_status,
            "status": status,
            "observacao": " ".join(issues) or None,
        })
    return pd.DataFrame(rows, columns=DOCUMENT_RECONCILIATION_AUDIT_COLUMNS)
