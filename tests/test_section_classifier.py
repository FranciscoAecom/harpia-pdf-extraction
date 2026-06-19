import re
import unittest
from types import SimpleNamespace

from harpia_parser.extraction.section_classifier import estado_from_section_title, tabela_resultado


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

    def test_qaqc_recovery_section_without_alias_is_classified_generically(self):
        config = SimpleNamespace(
            section_rules=[],
            section_subcategory_rules=[{
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
            section_rules=[],
            section_subcategory_rules=[{
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


if __name__ == "__main__":
    unittest.main()
