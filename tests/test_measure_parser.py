import math
import unittest

from harpia_parser.parsing.measure_parser import parse_medida, parse_resultado


class MeasureParserTest(unittest.TestCase):
    def test_lq_single_value_repeats_min_and_max(self):
        parsed = parse_medida("0,1 \u00b5S/cm", "lq")

        self.assertEqual(parsed["lq"], "0,1 \u00b5S/cm")
        self.assertEqual(parsed["lq_minimo"], 0.1)
        self.assertEqual(parsed["lq_maximo"], 0.1)
        self.assertEqual(parsed["lq_unidade"], "\u00b5S/cm")

    def test_lq_range_extracts_min_and_max(self):
        parsed = parse_medida("2,00 - 12,00", "lq")

        self.assertEqual(parsed["lq_minimo"], 2.0)
        self.assertEqual(parsed["lq_maximo"], 12.0)

    def test_acceptance_limit_repeats_min_and_max(self):
        parsed = parse_medida("< 20 %", "faixa_aceitacao", duplicar_valor_simples=True)

        self.assertEqual(parsed["faixa_aceitacao_operador"], "<")
        self.assertEqual(parsed["faixa_aceitacao_minimo"], 20.0)
        self.assertEqual(parsed["faixa_aceitacao_maximo"], 20.0)
        self.assertEqual(parsed["faixa_aceitacao_unidade"], "%")

    def test_acceptance_range_keeps_bounds(self):
        parsed = parse_medida("75 a 125 %", "faixa_aceitacao", duplicar_valor_simples=True)

        self.assertIsNone(parsed["faixa_aceitacao_operador"])
        self.assertEqual(parsed["faixa_aceitacao_minimo"], 75.0)
        self.assertEqual(parsed["faixa_aceitacao_maximo"], 125.0)
        self.assertEqual(parsed["faixa_aceitacao_unidade"], "%")

    def test_empty_measure_does_not_become_nan_text(self):
        parsed = parse_medida(float("nan"), "faixa_aceitacao", duplicar_valor_simples=True)

        self.assertIsNone(parsed["faixa_aceitacao"])
        self.assertIsNone(parsed["faixa_aceitacao_minimo"])
        self.assertIsNone(parsed["faixa_aceitacao_maximo"])

    def test_result_value_keeps_qualifier_and_unit(self):
        valor, qualificador, unidade = parse_resultado("< 0,5 mg/L")

        self.assertEqual(valor, 0.5)
        self.assertEqual(qualificador, "<")
        self.assertEqual(unidade, "mg/L")

    def test_result_value_extracts_color_unit(self):
        valor, qualificador, unidade = parse_resultado("10 Pt/Co (mgPt/L)")

        self.assertEqual(valor, 10.0)
        self.assertIsNone(qualificador)
        self.assertEqual(unidade, "Pt/Co (mgPt/L)")

    def test_result_value_extracts_ml_per_l_unit(self):
        valor, qualificador, unidade = parse_resultado("< 0,100 mL/L")

        self.assertEqual(valor, 0.1)
        self.assertEqual(qualificador, "<")
        self.assertEqual(unidade, "mL/L")

    def test_normative_value_extracts_mgpt_per_l_unit(self):
        parsed = parse_medida("Máx. 75 mgPt/L", "conama")

        self.assertEqual(parsed["conama_operador"], "max")
        self.assertEqual(parsed["conama_maximo"], 75.0)
        self.assertEqual(parsed["conama_unidade"], "mgPt/L")

    def test_result_scientific_notation(self):
        valor, qualificador, unidade = parse_resultado("1,2 x 10 3 UFC/mL")

        assert valor is not None
        self.assertTrue(math.isclose(valor, 1200.0))
        self.assertIsNone(qualificador)
        self.assertEqual(unidade, "UFC/mL")


if __name__ == "__main__":
    unittest.main()

