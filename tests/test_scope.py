import re
import unittest
from types import SimpleNamespace

from harpia_parser.core.scope import (
    classify_document,
    detect_document_template,
    detect_tipo_laudo,
    document_in_scope,
)


def _config():
    return SimpleNamespace(
        templates={
            "template_laudo_agua_v1": {
                "template_id": "template_laudo_agua_v1",
                "theme_id": "laudo_agua",
                "prioridade": 30,
                "score_minimo": 70,
            },
            "template_laudo_fito_v1": {
                "template_id": "template_laudo_fito_v1",
                "theme_id": "laudo_fito",
                "prioridade": 10,
                "score_minimo": 80,
            },
        },
        template_detection_rules=[
            {
                "template_id": "template_laudo_agua_v1",
                "rule_type": "required",
                "source": "text",
                "regex": re.compile(r"Relat.rio Anal.tico", re.IGNORECASE),
                "peso": 0,
            },
            {
                "template_id": "template_laudo_agua_v1",
                "rule_type": "positive",
                "source": "text",
                "regex": re.compile(r"Tipo de Amostra:\s*.gua", re.IGNORECASE),
                "peso": 40,
            },
            {
                "template_id": "template_laudo_agua_v1",
                "rule_type": "positive",
                "source": "text",
                "regex": re.compile(r"CONAMA\s*N.?\s*357", re.IGNORECASE),
                "peso": 40,
            },
            {
                "template_id": "template_laudo_agua_v1",
                "rule_type": "negative",
                "source": "text",
                "regex": re.compile(r"Fitopl.ncton|Comunidade Fitoplanct.nica", re.IGNORECASE),
                "peso": 0,
            },
            {
                "template_id": "template_laudo_fito_v1",
                "rule_type": "required",
                "source": "text",
                "regex": re.compile(r"Relat.rio Anal.tico", re.IGNORECASE),
                "peso": 0,
            },
            {
                "template_id": "template_laudo_fito_v1",
                "rule_type": "positive",
                "source": "text",
                "regex": re.compile(r"Fitopl.ncton", re.IGNORECASE),
                "peso": 40,
            },
            {
                "template_id": "template_laudo_fito_v1",
                "rule_type": "positive",
                "source": "text",
                "regex": re.compile(r"Comunidade Fitoplanct.nica", re.IGNORECASE),
                "peso": 40,
            },
        ],
    )


class ScopeTest(unittest.TestCase):
    def test_document_with_required_signals_is_in_scope(self):
        texto = "Relatorio Analitico Tipo de Amostra: Agua Salobra CONAMA N 357"

        self.assertTrue(document_in_scope(texto, _config()))
        self.assertEqual(detect_document_template(texto, _config()), "template_laudo_agua_v1")

    def test_document_without_required_signals_is_out_of_scope(self):
        texto = "Cadeia de Custodia Identificacao do Cliente Responsabilidade da Amostragem"

        self.assertFalse(document_in_scope(texto, _config()))

    def test_negative_rule_prevents_water_when_document_is_fito(self):
        texto = (
            "Relatorio Analitico Tipo de Amostra: Agua Doce CONAMA N 357 "
            "Fitoplancton Comunidade Fitoplanctonica"
        )

        self.assertEqual(detect_document_template(texto, _config()), "template_laudo_fito_v1")

    def test_tipo_laudo_uses_template_theme_id(self):
        texto = "Relatorio Analitico"

        self.assertEqual(
            detect_tipo_laudo(texto, r"L:\base\Agua\arquivo.pdf", _config(), "template_laudo_agua_v1"),
            "laudo_agua",
        )

    def test_classification_uses_template_rules_directly(self):
        texto = "Cadeia de Custodia Relatorio Analitico Tipo de Amostra: Agua Salobra CONAMA N 357"

        self.assertEqual(detect_document_template(texto, _config()), "template_laudo_agua_v1")

    def test_classification_audit_marks_winner(self):
        texto = "Relatorio Analitico Tipo de Amostra: Agua Salobra CONAMA N 357"

        classification = classify_document(texto, _config())

        self.assertEqual(classification.template_id, "template_laudo_agua_v1")
        self.assertIn("winner", {score.status for score in classification.scores})


if __name__ == "__main__":
    unittest.main()

