import unittest
from types import SimpleNamespace

from harpia_parser.extraction.table_audit import build_table_audit_row


def _context():
    return SimpleNamespace(
        nome_do_arquivo="a.pdf",
        template_id="template_laudo_agua_v1",
        tipo_laudo="laudo_agua",
    )


def _config():
    return SimpleNamespace(
        result_layouts={
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
        }
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
                "Criterio",
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
                "Criterio",
                "LQ",
                "Referencia",
                "Incerteza",
            ]],
            estado={"categoria": "Resultados", "subcategoria": "Amostragem", "tipo_registro": "AMOSTRA"},
            config=_config(),
            is_qaqc_continuacao=False,
        )

        self.assertEqual(row["status"], "ok_com_opcional_ausente")
        self.assertIn("ld_original", row["campos_opcionais_ausentes"])
        self.assertIn("unidade", row["campos_opcionais_ausentes"])


if __name__ == "__main__":
    unittest.main()
