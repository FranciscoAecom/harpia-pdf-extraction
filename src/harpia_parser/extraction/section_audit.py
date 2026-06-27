import re
from typing import Any, Pattern

import pandas as pd

from ..config.common import value_or_none
from ..constants import SECTION_EXTRACTION_AUDIT_COLUMNS
from ..core.context import DocumentContext
from ..utils import normalizar


def _clean(value: Any, limit: int = 300) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()
    return text[:limit] if text else None


def _patterns(rules_df: pd.DataFrame, field: str | None = None) -> list[Pattern[str]]:
    patterns: list[Pattern[str]] = []
    if rules_df.empty:
        return patterns
    source = rules_df
    if field is not None and "campo" in source.columns:
        selected = source[source["campo"].astype(str) == field]
        if not selected.empty:
            source = selected
    for _, row in source.iterrows():
        regex = value_or_none(row, "regex")
        if regex is not None:
            patterns.append(re.compile(str(regex), re.IGNORECASE | re.DOTALL))
    return patterns


def _base(context: DocumentContext) -> dict[str, Any]:
    return {
        "nome_do_arquivo": context.nome_do_arquivo,
        "id_taxonomia": context.id_taxonomia,
        "nome_taxonomia": context.nome_taxonomia,
        "versao_template": context.versao_template,
    }


def _known_section_rows(
    paginas,
    context: DocumentContext,
    config,
    outputs: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section_name, output_df in outputs.items():
        rules_df = getattr(config, f"df_{section_name}_rules", pd.DataFrame())
        title_patterns = _patterns(rules_df, "section_start")
        if not title_patterns:
            title_patterns = _patterns(rules_df)

        occurrences: list[tuple[int, str, str]] = []
        for page_number, (page_text, _) in enumerate(paginas, start=1):
            for pattern in title_patterns:
                for match in pattern.finditer(page_text or ""):
                    title = _clean(match.group(0))
                    if title:
                        occurrences.append((page_number, title, pattern.pattern))

        extracted_count = len(output_df)
        if occurrences and extracted_count:
            status = "ok"
            observation = "Secao reconhecida e dados extraidos."
        elif occurrences:
            status = "encontrada_sem_extracao"
            observation = "A secao foi encontrada, mas nenhum registro foi gerado."
        elif extracted_count:
            status = "extraida_sem_titulo"
            observation = "Foram gerados registros sem localizar a regra de inicio da secao."
        else:
            status = "nao_aplicavel"
            observation = "Secao opcional nao encontrada no documento."

        first = occurrences[0] if occurrences else (None, None, None)
        rows.append({
            **_base(context),
            "pagina": first[0],
            "tabela_indice": None,
            "objeto_tipo": "secao",
            "secao": section_name,
            "titulo_detectado": first[1],
            "modo_auditoria": "conhecida",
            "regra_encontrada": first[2],
            "ocorrencias_detectadas": len(occurrences),
            "registros_extraidos": extracted_count,
            "status": status,
            "observacao": observation,
        })
    return rows


def _all_known_patterns(config) -> list[Pattern[str]]:
    patterns: list[Pattern[str]] = []
    for attribute, frame in vars(config).items():
        if not attribute.startswith("df_") or not attribute.endswith("_rules") or not isinstance(frame, pd.DataFrame):
            continue
        for column in ["regex", "padrao_regex", "header_regex", "continuation_regex"]:
            if column not in frame.columns:
                continue
            for value in frame[column].dropna():
                patterns.append(re.compile(str(value), re.IGNORECASE))
    for rule in config.template_rules:
        pattern = rule.get("regex")
        if isinstance(pattern, re.Pattern):
            patterns.append(pattern)
    return patterns


def _matches_known(line: str, patterns: list[Pattern[str]]) -> bool:
    normalized = normalizar(line)
    return any(pattern.search(line) or pattern.search(normalized) for pattern in patterns)


def _looks_like_heading(line: str) -> bool:
    if not 3 <= len(line) <= 100 or re.search(r"\d", line):
        return False
    if line.endswith((".", ",", ";")) or ":" in line or not re.search(r"[A-Za-z\u00c0-\u00ff]", line):
        return False
    words = re.findall(r"[A-Za-z\u00c0-\u00ff]+", line)
    if not 1 <= len(words) <= 10 or re.fullmatch(r"[IVXLCDM]+", line, re.IGNORECASE):
        return False
    stopwords = {"a", "as", "da", "das", "de", "do", "dos", "e", "em", "para"}
    title_words = [word for word in words if normalizar(word) not in stopwords]
    return line.upper() == line or bool(title_words) and all(word[0].isupper() for word in title_words)


def _table_content_texts(tables) -> set[str]:
    values: set[str] = set()
    for table in tables:
        for row in table or []:
            row_values = []
            for cell in row or []:
                cleaned = _clean(cell)
                if cleaned:
                    normalized = normalizar(cleaned)
                    values.add(normalized)
                    row_values.append(normalized)
            if row_values:
                values.add(" ".join(row_values))
    return values


def _discovered_heading_rows(paginas, context: DocumentContext, config) -> list[dict[str, Any]]:
    known_patterns = _all_known_patterns(config)
    candidates: dict[str, dict[str, Any]] = {}
    for page_number, (page_text, tables) in enumerate(paginas, start=1):
        table_texts = _table_content_texts(tables)
        table_words = set(re.findall(r"[a-z\u00e0-\u00ff]+", " ".join(table_texts)))
        for raw_line in (page_text or "").splitlines():
            line = _clean(raw_line, limit=100)
            if not line or not _looks_like_heading(line):
                continue
            normalized = normalizar(line)
            if any(normalized == value or normalized in value for value in table_texts):
                continue
            line_words = set(re.findall(r"[a-z\u00e0-\u00ff]+", normalized))
            if line_words and line_words <= table_words:
                continue
            if _matches_known(line, known_patterns):
                continue
            candidate = candidates.setdefault(normalized, {"title": line, "pages": []})
            candidate["pages"].append(page_number)

    rows = []
    for candidate in candidates.values():
        pages = sorted(set(candidate["pages"]))
        rows.append({
            **_base(context),
            "pagina": pages[0],
            "tabela_indice": None,
            "objeto_tipo": "secao",
            "secao": None,
            "titulo_detectado": candidate["title"],
            "modo_auditoria": "descoberta",
            "regra_encontrada": None,
            "ocorrencias_detectadas": len(candidate["pages"]),
            "registros_extraidos": 0,
            "status": "secao_nao_mapeada",
            "observacao": f"Possivel titulo sem regra na taxonomia; paginas: {', '.join(map(str, pages))}.",
        })
    return rows


def _mapped_table_keys(table_audit_df: pd.DataFrame) -> set[tuple[int, int]]:
    if table_audit_df.empty:
        return set()
    return {
        (int(row["pagina"]), int(row["tabela_indice"]))
        for _, row in table_audit_df.dropna(subset=["pagina", "tabela_indice"]).iterrows()
    }


def _discovered_table_rows(paginas, context: DocumentContext, config, table_audit_df: pd.DataFrame) -> list[dict[str, Any]]:
    known_patterns = _all_known_patterns(config)
    mapped_keys = _mapped_table_keys(table_audit_df)
    rows: list[dict[str, Any]] = []
    for page_number, (_, tables) in enumerate(paginas, start=1):
        for table_index, table in enumerate(tables, start=1):
            if (page_number, table_index) in mapped_keys or not table:
                continue
            table_text = _clean(" ".join(_clean(cell) or "" for row in table for cell in (row or [])), limit=2000)
            if not table_text or _matches_known(table_text, known_patterns):
                continue
            nonempty_rows = [row for row in table if sum(_clean(cell) is not None for cell in (row or [])) >= 2]
            if len(nonempty_rows) < 2:
                continue
            header = _clean(" | ".join(_clean(cell) or "" for cell in nonempty_rows[0]), limit=300)
            rows.append({
                **_base(context),
                "pagina": page_number,
                "tabela_indice": table_index,
                "objeto_tipo": "tabela",
                "secao": None,
                "titulo_detectado": header,
                "modo_auditoria": "descoberta",
                "regra_encontrada": None,
                "ocorrencias_detectadas": 1,
                "registros_extraidos": 0,
                "status": "tabela_nao_mapeada",
                "observacao": "Estrutura tabular sem correspondencia nas regras conhecidas da taxonomia.",
            })
    return rows


def build_section_extraction_audit(
    paginas,
    context: DocumentContext,
    config,
    outputs: dict[str, pd.DataFrame],
    table_audit_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = _known_section_rows(paginas, context, config, outputs)
    rows.extend(_discovered_heading_rows(paginas, context, config))
    rows.extend(_discovered_table_rows(paginas, context, config, table_audit_df))
    return pd.DataFrame(rows, columns=SECTION_EXTRACTION_AUDIT_COLUMNS)
