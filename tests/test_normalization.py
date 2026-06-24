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
            "acm_resultado_tratado": None,
            "acm_qualificador": None,
            "acm_unidade": None,
            "conama": "6,5 a 8,5",
            "acm_conama_operador": None,
            "acm_conama_minimo": None,
            "acm_conama_maximo": None,
            "acm_conama_unidade": None,
            "copam_cerh": "Mín. 5 mg/L",
            "acm_copam_cerh_operador": None,
            "acm_copam_cerh_minimo": None,
            "acm_copam_cerh_maximo": None,
            "acm_copam_cerh_unidade": None,
            "lq": "0,1 \u00b5S/cm",
            "acm_lq_minimo": None,
            "acm_lq_maximo": None,
            "acm_lq_unidade": None,
            "incerteza": "0,030 %",
            "acm_incerteza_valor": None,
            "acm_incerteza_unidade": None,
            "faixa_aceitacao": "< 20 %",
            "acm_faixa_aceitacao_operador": None,
            "acm_faixa_aceitacao_minimo": None,
            "acm_faixa_aceitacao_maximo": None,
            "acm_faixa_aceitacao_unidade": None,
        }])

        out, _, _ = normalize_outputs(df, pd.DataFrame(), pd.DataFrame(), context)

        self.assertEqual(out.loc[0, "resultado"], "< 0,500 mg/L")
        self.assertEqual(out.loc[0, "acm_resultado_tratado"], 0.5)
        self.assertEqual(out.loc[0, "acm_qualificador"], "<")
        self.assertEqual(out.loc[0, "acm_unidade"], "mg/L")
        self.assertEqual(out.loc[0, "conama"], "6,5 a 8,5")
        self.assertEqual(out.loc[0, "acm_conama_minimo"], 6.5)
        self.assertEqual(out.loc[0, "acm_conama_maximo"], 8.5)
        self.assertIsNone(out.loc[0, "acm_conama_unidade"])
        self.assertEqual(out.loc[0, "copam_cerh"], "Mín. 5 mg/L")
        self.assertEqual(out.loc[0, "acm_copam_cerh_operador"], "min")
        self.assertEqual(out.loc[0, "acm_copam_cerh_minimo"], 5.0)
        self.assertIsNone(out.loc[0, "acm_copam_cerh_maximo"])
        self.assertEqual(out.loc[0, "acm_copam_cerh_unidade"], "mg/L")
        self.assertEqual(out.loc[0, "lq"], "0,1 \u00b5S/cm")
        self.assertEqual(out.loc[0, "acm_lq_minimo"], 0.1)
        self.assertEqual(out.loc[0, "acm_lq_maximo"], 0.1)
        self.assertEqual(out.loc[0, "acm_lq_unidade"], "\u00b5S/cm")
        self.assertEqual(out.loc[0, "incerteza"], "0,030 %")
        self.assertEqual(out.loc[0, "acm_incerteza_valor"], 0.03)
        self.assertEqual(out.loc[0, "acm_incerteza_unidade"], "%")
        self.assertEqual(out.loc[0, "faixa_aceitacao"], "< 20 %")
        self.assertEqual(out.loc[0, "acm_faixa_aceitacao_operador"], "<")
        self.assertEqual(out.loc[0, "acm_faixa_aceitacao_minimo"], 20.0)
        self.assertEqual(out.loc[0, "acm_faixa_aceitacao_maximo"], 20.0)
        self.assertEqual(out.loc[0, "acm_faixa_aceitacao_unidade"], "%")

    def test_laudo_agua_normative_na_is_preserved_as_pdf_text(self):
        context = SimpleNamespace(tipo_laudo="laudo_agua")
        df = pd.DataFrame([{
            "parameter": "Parametro",
            "resultado": "1,0",
            "acm_resultado_tratado": None,
            "acm_qualificador": None,
            "acm_unidade": None,
            "conama": "NA",
            "acm_conama_operador": None,
            "acm_conama_minimo": None,
            "acm_conama_maximo": None,
            "acm_conama_unidade": None,
        }])

        out, _, _ = normalize_outputs(df, pd.DataFrame(), pd.DataFrame(), context)

        self.assertEqual(out.loc[0, "conama"], "NA")
        self.assertIsNone(out.loc[0, "acm_conama_minimo"])
        self.assertIsNone(out.loc[0, "acm_conama_maximo"])

    def test_laudo_agua_normalization_sets_ph_unit(self):
        context = SimpleNamespace(tipo_laudo="laudo_agua")
        df = pd.DataFrame([{
            "parameter": "pH",
            "resultado": "7,10",
            "acm_resultado_tratado": None,
            "acm_qualificador": None,
            "acm_unidade": None,
        }])

        out, _, _ = normalize_outputs(df, pd.DataFrame(), pd.DataFrame(), context)

        self.assertEqual(out.loc[0, "acm_resultado_tratado"], 7.1)
        self.assertEqual(out.loc[0, "acm_unidade"], "pH")


if __name__ == "__main__":
    unittest.main()

