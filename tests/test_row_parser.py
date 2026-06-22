import unittest
import re
from types import SimpleNamespace

from harpia_parser.extraction.row_parser import processar_linha


class RowParserTest(unittest.TestCase):
    def test_header_without_ld_does_not_reuse_base_ld_column(self):
        config = SimpleNamespace(
            table_layouts={
                "AMOSTRA": {
                    "resultado_col": 4,
                    "unidade_col": 1,
                    "ld_col": 2,
                    "lq_col": 3,
                    "incerteza_col": 5,
                    "criterio_conformidade_col": 6,
                    "referencia_col": 7,
                    "data_inicio_col": 8,
                }
            },
            header_alias_rules=[],
        )
        estado = {
            "categoria": "Resultados Analiticos",
            "subcategoria": "Amostragem",
            "tipo_registro": "AMOSTRA",
            "local": "campo",
        }

        header = [
            "Analise",
            "Resultado",
            "Data de Inicio",
            "Resolucao CONAMA",
            "LQ",
            "Referencia",
            "Incerteza",
        ]
        self.assertIsNone(processar_linha(header, estado, config))

        dado = processar_linha(
            [
                "pH",
                "7,46",
                "04/12/2024",
                "6,0 a 9,0",
                "2,00 - 12,00",
                "SMWW, metodo 4500-H+",
                "0,09",
            ],
            estado,
            config,
        )

        self.assertIsNotNone(dado)
        assert dado is not None
        self.assertEqual(dado["resultado"], "7,46")
        self.assertEqual(dado["data_inicio"], "04/12/2024")
        self.assertIsNone(dado["ld"])
        self.assertEqual(dado["lq"], "2,00 - 12,00")

    def test_header_alias_from_taxonomy_maps_copam_criterion(self):
        config = SimpleNamespace(
            table_layouts={
                "AMOSTRA": {
                    "resultado_col": 1,
                    "criterio_conformidade_col": 2,
                }
            },
            header_alias_rules=[
                {
                    "field": "criterio_conformidade_col",
                    "regex": re.compile(r"copam|cerh|deliberacao normativa", re.IGNORECASE),
                }
            ],
        )
        estado = {
            "categoria": "Resultados Analiticos",
            "subcategoria": "Amostragem",
            "tipo_registro": "AMOSTRA",
            "local": "campo",
        }

        self.assertIsNone(processar_linha([
            "Analise",
            "Resultado",
            "Deliberação Normativa COPAM/CERH MG Nº01, de 05/05/2008 - Art.14 - Lótico",
        ], estado, config))
        dado = processar_linha(["pH", "7,46", "6,0 a 9,0"], estado, config)

        self.assertIsNotNone(dado)
        assert dado is not None
        self.assertEqual(dado["criterio_conformidade"], "6,0 a 9,0")


if __name__ == "__main__":
    unittest.main()
