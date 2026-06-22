import unittest

import pandas as pd

from harpia_parser.constants import RESULTS_EXTRACT_COLUMNS
from harpia_parser.validation.schemas import validate_results_extract


def _valid_row() -> dict:
    return {
        "nome_do_arquivo": "relatorio.pdf",
        "template_id": "relatorio_analitico_atual",
        "tipo_laudo": "agua",
        "id_sample": "717727",
        "tipo": "Duplicata",
        "categoria": "QA/QC",
        "subcategoria": None,
        "parameter": "pH",
        "resultado": "7,100",
        "resultado_tratado": 7.1,
        "qualificador": None,
        "unidade": "pH",
        "local": "laboratorio",
        "data_inicio": None,
        "conama": None,
        "copam_cerh": None,
        "lq": None,
        "lq_minimo": None,
        "lq_maximo": None,
        "lq_unidade": None,
        "referencia": None,
        "incerteza": None,
        "incerteza_valor": None,
        "incerteza_unidade": None,
        "numero_cq": "CQ1",
        "duplicata": "0,2",
        "faixa_aceitacao": "< 20 %",
        "faixa_aceitacao_operador": "<",
        "faixa_aceitacao_minimo": 20.0,
        "faixa_aceitacao_maximo": 20.0,
        "faixa_aceitacao_unidade": "%",
        "variacao_percentual": "4,5",
        "quantidade_adicionada": "10",
        "recuperacao_percentual": "98,5",
    }


class ValidationTest(unittest.TestCase):
    def test_simple_numeric_text_fields_are_validated(self):
        df = pd.DataFrame([_valid_row()], columns=RESULTS_EXTRACT_COLUMNS)

        errors = validate_results_extract(df)

        self.assertTrue(errors.empty)

    def test_invalid_simple_numeric_text_is_reported(self):
        row = _valid_row()
        row["recuperacao_percentual"] = "nao numerico"
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)

        errors = validate_results_extract(df)

        self.assertFalse(errors.empty)
        self.assertIn("recuperacao_percentual", set(errors["field"]))


if __name__ == "__main__":
    unittest.main()

