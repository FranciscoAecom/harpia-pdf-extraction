from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from pathlib import Path
from typing import Any

import pandas as pd

from ..constants import DUPLICATE_AUDIT_COLUMNS


VERSION_PATTERN = re.compile(
    r"cancela\s+e\s+substitui|substitui\s+o\s+relat.rio|relat.rio\s+revisad|retifica",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DuplicateCandidate:
    nome_do_arquivo: str
    caminho_arquivo: str
    id_taxonomia: Any
    nome_taxonomia: Any
    versao_template: Any
    id_amostra: Any
    identificacao_amostra: Any
    data_publicacao: Any
    data_coleta: Any
    hash_arquivo: str
    hash_texto: str
    chave_laudo: str
    assinatura_resultados: str
    possui_indicador_versao: bool


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(text: str) -> str:
    normalized = " ".join((text or "").split()).lower()
    return hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()


def has_version_marker(text: str) -> bool:
    return bool(VERSION_PATTERN.search(text or ""))


def build_duplicate_candidate(
    pdf_path: Path,
    text: str,
    result_df: pd.DataFrame,
    sample_df: pd.DataFrame,
) -> DuplicateCandidate:
    sample = _first_record(sample_df)
    result_identity = _first_record(result_df)
    identity = {**result_identity, **sample}
    id_amostra = _value(identity, "id_amostra")
    identificacao_amostra = _value(identity, "identificacao_amostra")
    data_publicacao = _value(identity, "data_publicacao")
    data_coleta = _value(identity, "data_coleta")
    chave_laudo = _logical_key(identity)

    return DuplicateCandidate(
        nome_do_arquivo=pdf_path.name,
        caminho_arquivo=str(pdf_path),
        id_taxonomia=_value(identity, "id_taxonomia"),
        nome_taxonomia=_value(identity, "nome_taxonomia"),
        versao_template=_value(identity, "versao_template"),
        id_amostra=id_amostra,
        identificacao_amostra=identificacao_amostra,
        data_publicacao=data_publicacao,
        data_coleta=data_coleta,
        hash_arquivo=file_sha256(pdf_path),
        hash_texto=text_sha256(text),
        chave_laudo=chave_laudo,
        assinatura_resultados=_results_signature(result_df),
        possui_indicador_versao=has_version_marker(text),
    )


def build_duplicate_audit(candidates: list[DuplicateCandidate]) -> pd.DataFrame:
    if not candidates:
        return pd.DataFrame(columns=DUPLICATE_AUDIT_COLUMNS)

    by_file_hash = _group_by(candidates, "hash_arquivo")
    by_text_hash = _group_by(candidates, "hash_texto")
    by_key = _group_by(candidates, "chave_laudo", ignore_empty=True)
    by_sample = _group_by(candidates, "id_amostra", ignore_empty=True)

    rows = []
    for candidate in candidates:
        status, group, reference, reason = _classify_candidate(
            candidate,
            by_file_hash,
            by_text_hash,
            by_key,
            by_sample,
        )
        rows.append({
            "nome_do_arquivo": candidate.nome_do_arquivo,
            "caminho_arquivo": candidate.caminho_arquivo,
            "id_taxonomia": candidate.id_taxonomia,
            "nome_taxonomia": candidate.nome_taxonomia,
            "versao_template": candidate.versao_template,
            "id_amostra": candidate.id_amostra,
            "identificacao_amostra": candidate.identificacao_amostra,
            "data_publicacao": candidate.data_publicacao,
            "data_coleta": candidate.data_coleta,
            "hash_arquivo": candidate.hash_arquivo,
            "hash_texto": candidate.hash_texto,
            "grupo_duplicidade": group,
            "tipo_duplicidade": status,
            "arquivo_referencia": reference,
            "motivo": reason,
            "status": status,
        })

    return pd.DataFrame(rows, columns=DUPLICATE_AUDIT_COLUMNS)


def _classify_candidate(
    candidate: DuplicateCandidate,
    by_file_hash: dict[str, list[DuplicateCandidate]],
    by_text_hash: dict[str, list[DuplicateCandidate]],
    by_key: dict[str, list[DuplicateCandidate]],
    by_sample: dict[str, list[DuplicateCandidate]],
) -> tuple[str, str, str | None, str]:
    exact = by_file_hash.get(candidate.hash_arquivo, [])
    if len(exact) > 1:
        return _status("duplicado_exato_arquivo", "hash_arquivo", candidate.hash_arquivo, candidate, exact)

    textual = by_text_hash.get(candidate.hash_texto, [])
    if len(textual) > 1:
        return _status("duplicado_textual", "hash_texto", candidate.hash_texto, candidate, textual)

    same_key = by_key.get(candidate.chave_laudo, []) if candidate.chave_laudo else []
    if len(same_key) > 1 and candidate.possui_indicador_versao:
        return _status("possivel_versao_substituta", "chave_laudo", candidate.chave_laudo, candidate, same_key)

    same_sample = by_sample.get(str(candidate.id_amostra), []) if _filled(candidate.id_amostra) else []
    if len(same_sample) > 1:
        signatures = {item.assinatura_resultados for item in same_sample if item.assinatura_resultados}
        if len(signatures) > 1:
            return _status("conflito_mesma_amostra", "id_amostra", str(candidate.id_amostra), candidate, same_sample)

    if len(same_key) > 1:
        return _status("possivel_duplicado_laudo", "chave_laudo", candidate.chave_laudo, candidate, same_key)

    return "unico", "", None, "Nenhuma duplicidade detectada no lote."


def _status(
    status: str,
    group_field: str,
    group_value: str,
    candidate: DuplicateCandidate,
    group: list[DuplicateCandidate],
) -> tuple[str, str, str | None, str]:
    reference = next((item.nome_do_arquivo for item in group if item.nome_do_arquivo != candidate.nome_do_arquivo), None)
    return status, f"{group_field}:{group_value}", reference, _reason(status)


def _reason(status: str) -> str:
    reasons = {
        "duplicado_exato_arquivo": "Outro PDF possui o mesmo hash binario SHA256.",
        "duplicado_textual": "Outro PDF possui o mesmo hash do texto normalizado.",
        "possivel_duplicado_laudo": "Outro PDF possui a mesma chave logica de laudo/amostra.",
        "possivel_versao_substituta": "Ha indicador textual de relatorio substituto/revisado.",
        "conflito_mesma_amostra": "A mesma amostra aparece em PDFs com assinatura de resultados diferente.",
    }
    return reasons.get(status, "")


def _group_by(
    candidates: list[DuplicateCandidate],
    attr: str,
    *,
    ignore_empty: bool = False,
) -> dict[str, list[DuplicateCandidate]]:
    groups: dict[str, list[DuplicateCandidate]] = {}
    for candidate in candidates:
        value = getattr(candidate, attr)
        if ignore_empty and not _filled(value):
            continue
        groups.setdefault(str(value), []).append(candidate)
    return groups


def _logical_key(identity: dict[str, Any]) -> str:
    identificacao = _value(identity, "identificacao_amostra")
    if _filled(identificacao):
        return f"identificacao_amostra={identificacao}"

    parts = [
        ("id_amostra", _value(identity, "id_amostra")),
        ("data_publicacao", _value(identity, "data_publicacao")),
        ("data_coleta", _value(identity, "data_coleta")),
    ]
    values = [f"{key}={value}" for key, value in parts if _filled(value)]
    return "|".join(values)


def _results_signature(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    columns = [
        column
        for column in ["id_amostra", "categoria", "subcategoria", "parameter", "resultado", "lq", "ld"]
        if column in df.columns
    ]
    if not columns:
        return ""
    data = df[columns].fillna("").astype(str).sort_values(columns).to_csv(index=False)
    return hashlib.sha256(data.encode("utf-8", errors="ignore")).hexdigest()


def _first_record(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}
    return {str(key): value for key, value in df.iloc[0].dropna().items()}


def _value(row: dict[str, Any], field: str) -> Any:
    value = row.get(field)
    return None if not _filled(value) else value


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    return str(value).strip() != ""
