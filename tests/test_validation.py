import unittest

import pandas as pd

from harpia_parser.constants import CLIENT_COLUMNS, PACKAGING_PRESERVATIVES_COLUMNS, RESULTS_EXTRACT_COLUMNS, SAMPLE_COLUMNS
from harpia_parser.validation.schemas import (
    validate_client,
    validate_packaging_preservatives,
    validate_results_extract,
    validate_sample,
)


def _valid_row() -> dict:
    return {
        "nome_do_arquivo": "relatorio.pdf",
        "id_taxonomia": 1,
        "nome_taxonomia": "Agua Superficial",
        "id_amostra": "717727",
        "tipo": "Duplicata",
        "categoria": "QA/QC",
        "subcategoria": None,
        "codigo_laudo": None,
        "acm_codigo_laudo": None,
        "codigo_laudo_substituido": None,
        "parameter": "pH",
        "resultado": "7,100",
        "unidade": "pH",
        "acm_resultado_tratado": 7.1,
        "acm_qualificador": None,
        "acm_unidade": "pH",
        "local": "laboratorio",
        "data_inicio": None,
        "acm_data_inicio": None,
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

    def test_missing_structured_unit_is_reported_when_original_has_unit(self):
        row = _valid_row()
        row["resultado"] = "10 Pt/Co (mgPt/L)"
        row["acm_resultado_tratado"] = 10
        row["acm_unidade"] = None
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)

        errors = validate_results_extract(df)

        self.assertFalse(errors.empty)
        self.assertTrue(errors["message"].astype(str).str.contains("acm_unidade vazio").any())

    def test_unknown_unit_is_reported_when_structured_unit_is_empty(self):
        row = _valid_row()
        row["resultado"] = "10 unidadeNova/L"
        row["acm_resultado_tratado"] = 10
        row["acm_unidade"] = None
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)

        errors = validate_results_extract(df)

        self.assertFalse(errors.empty)
        self.assertTrue(errors["message"].astype(str).str.contains("acm_unidade vazio").any())

    def test_unitless_range_does_not_raise_missing_unit_error(self):
        row = _valid_row()
        row["conama"] = "6,5 a 8,5"
        row["acm_conama_minimo"] = 6.5
        row["acm_conama_maximo"] = 8.5
        row["acm_conama_unidade"] = None
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)

        errors = validate_results_extract(df)

        self.assertTrue(errors.empty)

    def test_structured_unit_without_unit_in_source_is_reported(self):
        row = _valid_row()
        row["lq"] = "2,00 - 12,00"
        row["acm_lq_minimo"] = 2.0
        row["acm_lq_maximo"] = 12.0
        row["acm_lq_unidade"] = "pH"
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)

        errors = validate_results_extract(df)

        self.assertFalse(errors.empty)
        self.assertTrue(
            errors["message"].astype(str).str.contains("acm_lq_unidade preenchido sem unidade").any()
        )

    def test_structured_unit_with_empty_source_is_reported(self):
        row = _valid_row()
        row["incerteza"] = None
        row["acm_incerteza_valor"] = None
        row["acm_incerteza_unidade"] = "pH"
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)

        errors = validate_results_extract(df)

        self.assertFalse(errors.empty)
        self.assertTrue(
            errors["message"].astype(str).str.contains("acm_incerteza_unidade preenchido com campo de origem vazio").any()
        )

    def test_derived_value_with_empty_source_is_reported(self):
        row = _valid_row()
        row["lq"] = None
        row["acm_lq_minimo"] = 2.0
        row["acm_lq_maximo"] = None
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)

        errors = validate_results_extract(df)

        self.assertFalse(errors.empty)
        self.assertTrue(
            errors["message"].astype(str).str.contains("acm_lq_minimo preenchido com lq vazio").any()
        )

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

    def test_sample_dates_are_validated(self):
        row = {
            "nome_do_arquivo": "relatorio.pdf",
            "id_taxonomia": 1,
            "nome_taxonomia": "Agua Superficial",
            "id_amostra": "687944",
            "identificacao_amostra": "687944 - ECR 01R - P50",
            "tipo_amostra": "Agua superficial",
            "criterio_conformidade": None,
            "data_coleta": "2025-01-22",
            "data_publicacao": "22/01/2025",
            "data_recebimento": "22/01/2025",
            "observacoes": None,
            "localizacao": None,
            "latitude": "-19,123",
            "longitude": "-43.123",
            "clima_ultimas_24h": None,
            "clima": None,
            "tipo_coleta": None,
            "responsavel_amostra": None,
            "planejamento_amostragem": None,
            "descricao_nao_conformidade": None,
        }
        df = pd.DataFrame([row], columns=SAMPLE_COLUMNS)

        errors = validate_sample(df)

        self.assertFalse(errors.empty)
        self.assertEqual(errors.loc[0, "sheet"], "sample")
        self.assertEqual(errors.loc[0, "field"], "data_coleta")

    def test_client_required_keys_are_validated(self):
        row = {
            "nome_do_arquivo": "relatorio.pdf",
            "id_taxonomia": 1,
            "nome_taxonomia": "Agua Superficial",
            "id_amostra": "",
            "proposta_comercial": "PC-1",
            "cliente": "Cliente",
            "cnpj_cpf": "00.000.000/0001-00",
            "contato": None,
            "telefone": None,
            "endereco": None,
        }
        df = pd.DataFrame([row], columns=CLIENT_COLUMNS)

        errors = validate_client(df)

        self.assertFalse(errors.empty)
        self.assertEqual(errors.loc[0, "sheet"], "client")
        self.assertEqual(errors.loc[0, "field"], "id_amostra")


if __name__ == "__main__":
    unittest.main()

