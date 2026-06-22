import unittest
from types import SimpleNamespace

import pandas as pd

from harpia_parser.normalization import normalize_outputs


class NormalizationTest(unittest.TestCase):
    def test_common_normalization_strips_text_but_preserves_original_pdf_values(self):
        context = SimpleNamespace(tipo_laudo="laudo_agua")
        df = pd.DataFrame([{
            "parameter": " pH ",
            "resultado": " 7,100 mg/L ",
            "lq": " 0,100 mg/L ",
        }])
        sample_df = pd.DataFrame([{"localizacao": " Local  "}])
        client_df = pd.DataFrame([{"cliente": " Cliente  "}])

        out, sample_out, client_out = normalize_outputs(df, sample_df, client_df, context)

        self.assertEqual(out.loc[0, "parameter"], "pH")
        self.assertEqual(out.loc[0, "resultado"], " 7,100 mg/L ")
        self.assertEqual(out.loc[0, "lq"], " 0,100 mg/L ")
        self.assertEqual(sample_out.loc[0, "localizacao"], "Local")
        self.assertEqual(client_out.loc[0, "cliente"], "Cliente")

    def test_laudo_agua_normalization_structures_measures(self):
        context = SimpleNamespace(tipo_laudo="laudo_agua")
        df = pd.DataFrame([{
            "parameter": "Condutividade",
            "resultado": "< 0,500 mg/L",
            "resultado_tratado": None,
            "qualificador": None,
            "unidade": None,
            "lq": "0,1 \u00b5S/cm",
            "lq_minimo": None,
            "lq_maximo": None,
            "lq_unidade": None,
            "incerteza": "0,030 %",
            "incerteza_valor": None,
            "incerteza_unidade": None,
            "faixa_aceitacao": "< 20 %",
            "faixa_aceitacao_operador": None,
            "faixa_aceitacao_minimo": None,
            "faixa_aceitacao_maximo": None,
            "faixa_aceitacao_unidade": None,
        }])

        out, _, _ = normalize_outputs(df, pd.DataFrame(), pd.DataFrame(), context)

        self.assertEqual(out.loc[0, "resultado"], "< 0,500 mg/L")
        self.assertEqual(out.loc[0, "resultado_tratado"], 0.5)
        self.assertEqual(out.loc[0, "qualificador"], "<")
        self.assertEqual(out.loc[0, "unidade"], "mg/L")
        self.assertEqual(out.loc[0, "lq"], "0,1 \u00b5S/cm")
        self.assertEqual(out.loc[0, "lq_minimo"], 0.1)
        self.assertEqual(out.loc[0, "lq_maximo"], 0.1)
        self.assertEqual(out.loc[0, "lq_unidade"], "\u00b5S/cm")
        self.assertEqual(out.loc[0, "incerteza"], "0,030 %")
        self.assertEqual(out.loc[0, "incerteza_valor"], 0.03)
        self.assertEqual(out.loc[0, "incerteza_unidade"], "%")
        self.assertEqual(out.loc[0, "faixa_aceitacao"], "< 20 %")
        self.assertEqual(out.loc[0, "faixa_aceitacao_operador"], "<")
        self.assertEqual(out.loc[0, "faixa_aceitacao_minimo"], 20.0)
        self.assertEqual(out.loc[0, "faixa_aceitacao_maximo"], 20.0)
        self.assertEqual(out.loc[0, "faixa_aceitacao_unidade"], "%")

    def test_laudo_agua_normalization_sets_ph_unit(self):
        context = SimpleNamespace(tipo_laudo="laudo_agua")
        df = pd.DataFrame([{
            "parameter": "pH",
            "resultado": "7,10",
            "resultado_tratado": None,
            "qualificador": None,
            "unidade": None,
        }])

        out, _, _ = normalize_outputs(df, pd.DataFrame(), pd.DataFrame(), context)

        self.assertEqual(out.loc[0, "resultado_tratado"], 7.1)
        self.assertEqual(out.loc[0, "unidade"], "pH")


if __name__ == "__main__":
    unittest.main()

