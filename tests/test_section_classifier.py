import re
import unittest
from types import SimpleNamespace

from harpia_parser.extraction.section_classifier import aplicar_section_pdf, estado_from_section_title, pending_section_from_page_text, tabela_resultado


class SectionClassifierTest(unittest.TestCase):
    def test_table_without_result_header_is_not_result_table(self):
        rows = [
            ["Polietileno 5000", "5 L", "0 a 6\u00baC"],
            ["Bombona", "1000 mL", "0 a 6\u00baC"],
        ]
        estado = {"tipo_registro": "AMOSTRA", "categoria": "Metais"}

        self.assertFalse(tabela_resultado(rows, estado))

    def test_table_with_result_header_is_result_table(self):
        rows = [
            ["Analise", "Resultado", "Data de Inicio"],
            ["pH", "7,10", "01/01/2025"],
        ]
        estado = {"tipo_registro": "AMOSTRA", "categoria": "Fisico-Quimico"}

        self.assertTrue(tabela_resultado(rows, estado))

    def test_result_table_continuation_without_header_is_result_table(self):
        rows = [
            ["Nitrato", "< 0,23 mg/L (como N)", "18/01/2025", "Max. 0,4 mg/L", "0,23 mg/L"],
            ["Nitrito", "< 0,015 mg/L (como N)", "18/01/2025", "Max. 0,07 mg/L", "0,015 mg/L"],
        ]
        estado = {"tipo_registro": "AMOSTRA", "categoria": "Constituintes inorganicos nao metalicos"}

        self.assertTrue(tabela_resultado(rows, estado))

    def test_result_table_continuation_uses_configured_result_column(self):
        rows = [
            ["Antimonio Dissolvido", "mg/L", "0,00001", "0,00005", "< 0,00001", "NA"],
            ["Arsenio Dissolvido", "mg/L", "0,00010", "0,00050", "< 0,00010", "NA"],
        ]
        estado = {"tipo_registro": "AMOSTRA", "categoria": "Metais"}
        config = SimpleNamespace(table_layouts={"AMOSTRA": {"resultado_col": 4}})

        self.assertTrue(tabela_resultado(rows, estado, config))

    def test_qaqc_recovery_section_without_alias_is_classified_generically(self):
        config = SimpleNamespace(
            category_alias_rules=[],
            subcategory_alias_rules=[{
                "regex": re.compile(r"^recuperacao\s+-\s+.+"),
                "categoria": "Controle de Qualidade",
                "subcategoria": None,
                "tipo_registro": "RECUPERACAO",
                "local": "laboratorio",
            }],
        )

        estado = estado_from_section_title("Recupera\u00e7\u00e3o - Especia\u00e7\u00e3o", config)

        self.assertIsNotNone(estado)
        assert estado is not None
        self.assertEqual(estado["categoria"], "Controle de Qualidade")
        self.assertEqual(estado["tipo_registro"], "RECUPERACAO")
        self.assertEqual(estado["subcategoria"], "Recupera\u00e7\u00e3o - Especia\u00e7\u00e3o")
        self.assertEqual(estado["local"], "laboratorio")

    def test_qaqc_section_prefers_registered_alias_when_available(self):
        config = SimpleNamespace(
            category_alias_rules=[],
            subcategory_alias_rules=[{
                "regex": re.compile(r"^recuperacao\s+-\s+metais$"),
                "categoria": "Controle de Qualidade",
                "subcategoria": "Recupera\u00e7\u00e3o - Metais",
                "tipo_registro": "RECUPERACAO",
                "local": "laboratorio",
            }],
        )

        estado = estado_from_section_title("Recupera\u00e7\u00e3o - Metais", config)

        self.assertIsNotNone(estado)
        assert estado is not None
        self.assertEqual(estado["tipo_registro"], "RECUPERACAO")
        self.assertEqual(estado["subcategoria"], "Recupera\u00e7\u00e3o - Metais")

    def test_pending_section_keeps_specific_subcategory_over_later_generic_line(self):
        config = SimpleNamespace(
            category_alias_rules=[{
                "regex": re.compile(r"^(provedores?\s+externos?|ethica\s+ambiental)", re.IGNORECASE),
                "categoria": "Provedores Externos",
                "subcategoria": None,
                "local": "laboratorio",
            }],
            subcategory_alias_rules=[{
                "regex": re.compile(r"^ethica\s+ambiental.*", re.IGNORECASE),
                "categoria": "Provedores Externos",
                "subcategoria": "Ethica Ambiental",
                "tipo_registro": "AMOSTRA",
                "local": "laboratorio",
            }],
        )

        pending = pending_section_from_page_text(
            "Provedores Externos\nEthica Ambiental - CRL 1371\nProvedores externos",
            config,
        )

        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertEqual(pending["subcategoria"], "Ethica Ambiental")

    def test_generic_section_line_does_not_clear_existing_specific_subcategory(self):
        config = SimpleNamespace(
            category_alias_rules=[{
                "regex": re.compile(r"^(provedores?\s+externos?|ethica\s+ambiental)", re.IGNORECASE),
                "categoria": "Provedores Externos",
                "subcategoria": None,
                "local": "laboratorio",
            }],
            subcategory_alias_rules=[],
            category_type_rules=[],
        )
        estado = {
            "categoria": "Provedores Externos",
            "subcategoria": "Ethica Ambiental",
            "tipo_registro": "AMOSTRA",
            "local": "laboratorio",
        }

        self.assertTrue(aplicar_section_pdf("Provedores externos", estado, config))
        self.assertEqual(estado["subcategoria"], "Ethica Ambiental")


if __name__ == "__main__":
    unittest.main()
