from pathlib import Path
from dataclasses import replace

from .context import ClassificationResult, TemplateScore


def _rule_haystack(texto: str, path_text: str, source: str) -> str:
    if source == "path":
        return path_text
    if source == "filename":
        return Path(path_text).name
    return texto


def _rule_description(rule: dict) -> str:
    return str(rule.get("descricao") or rule["regex"].pattern)


def _document_type_score(document_type_id: str, texto: str, path_text: str, config) -> tuple[float, list[str], str]:
    rules = [
        rule
        for rule in getattr(config, "document_type_detection_rules", [])
        if rule["document_type_id"] == document_type_id
    ]
    required_rules = [rule for rule in rules if rule["rule_type"] == "required"]
    positive_rules = [rule for rule in rules if rule["rule_type"] == "positive"]
    negative_rules = [rule for rule in rules if rule["rule_type"] == "negative"]
    matched_rules: list[str] = []

    for rule in required_rules:
        haystack = _rule_haystack(texto, path_text, rule["source"])
        if not rule["regex"].search(haystack):
            return 0.0, matched_rules, f"required_missing:{_rule_description(rule)}"
        matched_rules.append(f"required:{_rule_description(rule)}")

    for rule in negative_rules:
        haystack = _rule_haystack(texto, path_text, rule["source"])
        if rule["regex"].search(haystack):
            matched_rules.append(f"negative:{_rule_description(rule)}")
            return 0.0, matched_rules, f"negative_matched:{_rule_description(rule)}"

    score = 0.0
    for rule in positive_rules:
        haystack = _rule_haystack(texto, path_text, rule["source"])
        if rule["regex"].search(haystack):
            score += rule["peso"]
            matched_rules.append(f"positive:{_rule_description(rule)}")
    return score, matched_rules, "scored"


def detect_document_type(texto: str, config, pdf_path: str | Path | None = None) -> str | None:
    document_types = getattr(config, "document_types", {})
    if not document_types:
        return None

    path_text = str(pdf_path or "")
    candidates: list[tuple[float, int, str]] = []
    for document_type_id, document_type in document_types.items():
        score, _, status = _document_type_score(document_type_id, texto, path_text, config)
        if status != "scored":
            continue
        score_minimo = float(document_type.get("score_minimo") or 0)
        prioridade = int(document_type.get("prioridade") or 999)
        if score >= score_minimo:
            candidates.append((score, -prioridade, document_type_id))
    return max(candidates)[2] if candidates else None


def _template_score(template_id: str, texto: str, path_text: str, config) -> tuple[float, list[str], str]:
    rules = [rule for rule in config.template_detection_rules if rule["template_id"] == template_id]
    required_rules = [rule for rule in rules if rule["rule_type"] == "required"]
    positive_rules = [rule for rule in rules if rule["rule_type"] == "positive"]
    negative_rules = [rule for rule in rules if rule["rule_type"] == "negative"]
    matched_rules: list[str] = []

    for rule in required_rules:
        haystack = _rule_haystack(texto, path_text, rule["source"])
        if not rule["regex"].search(haystack):
            return 0.0, matched_rules, f"required_missing:{_rule_description(rule)}"
        matched_rules.append(f"required:{_rule_description(rule)}")

    for rule in negative_rules:
        haystack = _rule_haystack(texto, path_text, rule["source"])
        if rule["regex"].search(haystack):
            matched_rules.append(f"negative:{_rule_description(rule)}")
            return 0.0, matched_rules, f"negative_matched:{_rule_description(rule)}"

    score = 0.0
    for rule in positive_rules:
        haystack = _rule_haystack(texto, path_text, rule["source"])
        if rule["regex"].search(haystack):
            score += rule["peso"]
            matched_rules.append(f"positive:{_rule_description(rule)}")
    return score, matched_rules, "scored"


def classify_document(texto: str, config, pdf_path: str | Path | None = None) -> ClassificationResult:
    path_text = str(pdf_path or "")
    candidates: list[tuple[float, int, str]] = []
    scores: list[TemplateScore] = []
    document_type_id = detect_document_type(texto, config, pdf_path)

    for template_id, template in config.templates.items():
        template_document_type_id = str(template.get("document_type_id") or "").strip()
        if document_type_id and template_document_type_id and template_document_type_id != document_type_id:
            scores.append(TemplateScore(
                template_id,
                0.0,
                float(template.get("score_minimo") or 0),
                int(template.get("prioridade") or 999),
                "document_type_filtered",
                [],
            ))
            continue

        score, matched_rules, status = _template_score(template_id, texto, path_text, config)
        score_minimo = float(template.get("score_minimo") or 0)
        prioridade = int(template.get("prioridade") or 999)
        if status != "scored":
            scores.append(TemplateScore(template_id, score, score_minimo, prioridade, status, matched_rules))
            continue

        if score < score_minimo:
            scores.append(TemplateScore(template_id, score, score_minimo, prioridade, "below_minimum", matched_rules))
            continue

        scores.append(TemplateScore(template_id, score, score_minimo, prioridade, "candidate", matched_rules))
        candidates.append((score, -prioridade, template_id))

    if not candidates:
        return ClassificationResult(None, None, scores)

    template_id = max(candidates)[2]
    scores = [
        replace(score, status="winner") if score.template_id == template_id and score.status == "candidate" else score
        for score in scores
    ]
    tipo_laudo = detect_tipo_laudo(texto, pdf_path or "", config, template_id)
    return ClassificationResult(template_id, tipo_laudo, scores)


def detect_document_template(texto: str, config, pdf_path: str | Path | None = None) -> str | None:
    return classify_document(texto, config, pdf_path).template_id


def document_in_scope(texto: str, config) -> bool:
    return detect_document_template(texto, config) is not None


def detect_tipo_laudo(texto: str, pdf_path: str | Path, config, template_id: str) -> str | None:
    template = config.templates.get(template_id, {})
    theme_id = template.get("theme_id")
    return str(theme_id) if theme_id else None
