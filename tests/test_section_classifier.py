import unittest

from harpia_parser.extraction.section_classifier import tabela_resultado


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


if __name__ == "__main__":
    unittest.main()

