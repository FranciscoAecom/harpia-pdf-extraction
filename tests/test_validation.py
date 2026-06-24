import unittest

import pandas as pd

from harpia_parser.constants import PACKAGING_PRESERVATIVES_COLUMNS, RESULTS_EXTRACT_COLUMNS
from harpia_parser.validation.schemas import validate_packaging_preservatives, validate_results_extract


def _valid_row() -> dict:
    return {
        "nome_do_arquivo": "relatorio.pdf",
        "id_taxonomia": 1,
        "nome_taxonomia": "Agua Superficial",
        "id_amostra": "717727",
        "tipo": "Duplicata",
        "categoria": "QA/QC",
        "subcategoria": None,
        "parameter": "pH",
        "resultado": "7,100",
        "acm_resultado_tratado": 7.1,
        "acm_qualificador": None,
        "acm_unidade": "pH",
        "local": "laboratorio",
        "data_inicio": None,
        "conama": None,
        "acm_conama_operador": None,
        "acm_conama_minimo": None,
        "acm_conama_maximo": None,
        "acm_conama_unidade": None,
        "copam_cerh": None,
        "acm_copam_cerh_operador": None,
        "acm_copam_cerh_minimo": None,
        "acm_copam_cerh_maximo": None,
        "acm_copam_cerh_unidade": None,
        "lq": None,
        "acm_lq_minimo": None,
        "acm_lq_maximo": None,
        "acm_lq_unidade": None,
        "referencia": None,
        "incerteza": None,
        "acm_incerteza_valor": None,
        "acm_incerteza_unidade": None,
        "numero_cq": "CQ1",
        "duplicata": "0,2",
        "faixa_aceitacao": "< 20 %",
        "acm_faixa_aceitacao_operador": "<",
        "acm_faixa_aceitacao_minimo": 20.0,
        "acm_faixa_aceitacao_maximo": 20.0,
        "acm_faixa_aceitacao_unidade": "%",
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
        fields = set(errors["field"].astype(str).tolist())
        self.assertIn("recuperacao_percentual", fields)

    def test_packaging_preservatives_required_fields_are_validated(self):
        row = {
            "nome_do_arquivo": "relatorio.pdf",
            "id_taxonomia": 1,
            "nome_taxonomia": "Agua Superficial",
            "id_amostra": "687944",
            "identificacao_amostra": "687944 - ECR 01R - P50",
            "embalagem": "Polietileno",
            "volume": "1000 mL",
            "preservacao": "0 a 6ºC",
            "metodos": "",
        }
        df = pd.DataFrame([row], columns=PACKAGING_PRESERVATIVES_COLUMNS)

        errors = validate_packaging_preservatives(df)

        self.assertFalse(errors.empty)
        self.assertEqual(errors.loc[0, "sheet"], "packaging_preservatives")
        self.assertEqual(errors.loc[0, "field"], "metodos")


if __name__ == "__main__":
    unittest.main()

