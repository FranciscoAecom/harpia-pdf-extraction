from pathlib import Path
from dataclasses import replace

from .context import ClassificationResult, TemplateScore


def _rule_haystack(texto: str, path_text: str, source: str) -> str:
    return path_text if source == "path" else texto


def _rule_description(rule: dict) -> str:
    return str(rule.get("descricao") or rule["regex"].pattern)


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

    for template_id, template in config.templates.items():
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
