import unittest
import re
from types import SimpleNamespace

from harpia_parser.extraction.table_audit import build_table_audit_row


def _context():
    return SimpleNamespace(
        nome_do_arquivo="a.pdf",
        template_id="template_laudo_agua_v1",
        tipo_laudo="laudo_agua",
        id_taxonomia=1,
        nome_taxonomia="Agua Superficial",
    )


def _config():
    return SimpleNamespace(
        table_layouts={
            "AMOSTRA": {
                "resultado_col": 4,
                "unidade_col": 1,
                "ld_col": 2,
                "lq_col": 3,
                "incerteza_col": 5,
                "conama_col": 6,
                "referencia_col": 7,
                "data_inicio_col": 8,
            }
        },
        header_alias_rules=[],
    )


class TableAuditTest(unittest.TestCase):
    def test_complete_header_is_ok(self):
        row = build_table_audit_row(
            context=_context(),
            page_number=1,
            table_index=1,
            rows=[[
                "Parametros",
                "Unidade",
                "LD",
                "LQ",
                "Resultado",
                "Incerteza",
                "CONAMA",
                "Referencia",
                "Data de Inicio",
            ]],
            estado={"categoria": "Resultados", "subcategoria": "Amostragem", "tipo_registro": "AMOSTRA"},
            config=_config(),
            is_qaqc_continuacao=False,
        )

        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["campos_opcionais_ausentes"], "")

    def test_missing_expected_fields_are_optional_until_taxonomy_marks_required(self):
        row = build_table_audit_row(
            context=_context(),
            page_number=1,
            table_index=1,
            rows=[[
                "Analise",
                "Resultado",
                "Data de Inicio",
                "CONAMA",
                "LQ",
                "Referencia",
                "Incerteza",
            ]],
            estado={"categoria": "Resultados", "subcategoria": "Amostragem", "tipo_registro": "AMOSTRA"},
            config=_config(),
            is_qaqc_continuacao=False,
        )

        self.assertEqual(row["status"], "ok_com_opcional_ausente")
        campos_opcionais_ausentes = str(row["campos_opcionais_ausentes"])
        self.assertIn("ld", campos_opcionais_ausentes)
        self.assertIn("unidade", campos_opcionais_ausentes)

    def test_header_alias_from_taxonomy_maps_copam_criterion(self):
        config = _config()
        config.header_alias_rules = [
            {
                "field": "copam_cerh_col",
                "regex": re.compile(r"copam|cerh|deliberacao normativa", re.IGNORECASE),
            }
        ]
        row = build_table_audit_row(
            context=_context(),
            page_number=1,
            table_index=1,
            rows=[[
                "Analise",
                "Resultado",
                "Data de Inicio",
                "Deliberação Normativa COPAM/CERH MG Nº01, de 05/05/2008 - Art.14 - Lótico",
                "LQ",
                "Referencia",
                "Incerteza",
            ]],
            estado={"categoria": "Resultados", "subcategoria": "Amostragem", "tipo_registro": "AMOSTRA"},
            config=config,
            is_qaqc_continuacao=False,
        )

        status = str(row["status"])
        colunas_mapeadas = str(row["colunas_mapeadas"])
        self.assertNotIn("alerta_descoberta", status)
        self.assertEqual(row["colunas_sem_mapeamento"], "")
        self.assertIn("copam_cerh", colunas_mapeadas)

    def test_fallback_uses_page_text_header_and_marks_confident_layout(self):
        row = build_table_audit_row(
            context=_context(),
            page_number=1,
            table_index=1,
            rows=[
                ["Fosfato", "mg/L", "0,01", "0,02", "0,100", "5%", "NA", "SMWW", "01/01/2025"],
                ["Nitrato", "mg/L", "0,01", "0,02", "1,500", "5%", "NA", "SMWW", "01/01/2025"],
            ],
            estado={"categoria": "Resultados", "subcategoria": "Amostragem", "tipo_registro": "AMOSTRA"},
            config=_config(),
            is_qaqc_continuacao=False,
            page_text="Análise Unidade LD LQ Resultado Incerteza CONAMA Referência Data de Início",
        )

        self.assertEqual(row["status"], "fallback_cabecalho_texto_layout_confiavel")
        self.assertTrue(row["usou_fallback"])
        observacao = str(row["observacao"])
        self.assertIn("Cabecalho contextual encontrado", observacao)
        self.assertIn("resultado", observacao)

    def test_fallback_uses_page_text_header_and_marks_confident_compact_layout(self):
        row = build_table_audit_row(
            context=_context(),
            page_number=1,
            table_index=1,
            rows=[
                ["Carbono Orgânico Dissolvido", "1,76 mg/L", "16/11/2024", "NA", "0,500 mg/L", "SMWW", "9,39%"],
                ["Carbono Orgânico Total", "1,82 mg/L", "16/11/2024", "Máx. 3 mg/L", "0,500 mg/L", "SMWW", "9,39%"],
            ],
            estado={"categoria": "Resultados", "subcategoria": "Amostragem", "tipo_registro": "AMOSTRA"},
            config=_config(),
            is_qaqc_continuacao=False,
            page_text="Análise Resultado Data de Início CONAMA LQ Referência Incerteza",
        )

        self.assertEqual(row["status"], "fallback_cabecalho_texto_layout_confiavel")
        self.assertTrue(row["usou_fallback"])
        self.assertIn("colunas suficientes", str(row["observacao"]))
        self.assertEqual(
            row["campos_esperados"],
            "parameter; resultado; data_inicio; conama; lq; referencia; incerteza",
        )

    def test_fallback_uses_previous_header_layout_override(self):
        config = _config()
        row = build_table_audit_row(
            context=_context(),
            page_number=2,
            table_index=1,
            rows=[
                ["Antimônio Dissolvido", "< 0,00005 mg/L", "13/11/2024", "NA", "NA", "0,00005 mg/L", "EPA", "15,28%"],
                ["Antimônio Total", "< 0,0000500 mg/L", "13/11/2024", "Máx 0,005 mg/L", "Máx. 0,005 mg/L", "0,0000500 mg/L", "EPA", "15,28%"],
            ],
            estado={
                "categoria": "Resultados",
                "subcategoria": "Metais",
                "tipo_registro": "AMOSTRA",
                "layout_override_tipo": "AMOSTRA",
                "layout_override": {
                    "resultado_col": 1,
                    "data_inicio_col": 2,
                    "copam_cerh_col": 3,
                    "conama_col": 4,
                    "lq_col": 5,
                    "referencia_col": 6,
                    "incerteza_col": 7,
                },
            },
            config=config,
            is_qaqc_continuacao=False,
        )

        self.assertEqual(row["status"], "fallback_layout_confiavel")
        self.assertEqual(
            row["campos_esperados"],
            "parameter; resultado; data_inicio; copam_cerh; conama; lq; referencia; incerteza",
        )


if __name__ == "__main__":
    unittest.main()
