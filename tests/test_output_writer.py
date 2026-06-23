import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from harpia_parser.constants import PACKAGING_PRESERVATIVES_COLUMNS, RESULTS_EXTRACT_COLUMNS
from harpia_parser.formatting.output_writer import salvar
from test_validation import _valid_row


class OutputWriterTest(unittest.TestCase):
    def test_resultado_tratado_is_written_as_number_with_original_decimal_format(self):
        row = _valid_row()
        row["resultado"] = "< 0,100 mg/L"
        row["resultado_tratado"] = 0.1
        row["lq"] = "0,0200 mg/L"
        row["lq_minimo"] = 0.02
        row["lq_maximo"] = 0.02
        row["incerteza"] = "0,030 %"
        row["incerteza_valor"] = 0.03
        row["faixa_aceitacao"] = "75,00 a 125,000 %"
        row["faixa_aceitacao_minimo"] = 75.0
        row["faixa_aceitacao_maximo"] = 125.0
        row["variacao_percentual"] = "4,50"
        row["quantidade_adicionada"] = "10,000"
        row["recuperacao_percentual"] = "98,5"
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "out.xlsx"
            salvar(df, output_path)

            workbook = load_workbook(output_path, data_only=False)
            worksheet = workbook["results_extract"]
            expected = {
                "resultado_tratado": (0.1, "0.000"),
                "lq_minimo": (0.02, "0.0000"),
                "lq_maximo": (0.02, "0.0000"),
                "incerteza_valor": (0.03, "0.000"),
                "faixa_aceitacao_minimo": (75, "0.00"),
                "faixa_aceitacao_maximo": (125, "0.000"),
                "variacao_percentual": (4.5, "0.00"),
                "quantidade_adicionada": (10, "0.000"),
                "recuperacao_percentual": (98.5, "0.0"),
            }
            for column_name, (value, number_format) in expected.items():
                column_index = RESULTS_EXTRACT_COLUMNS.index(column_name) + 1
                cell = worksheet.cell(row=2, column=column_index)
                self.assertEqual(cell.value, value)
                self.assertEqual(cell.number_format, number_format)

    def test_scientific_resultado_tratado_is_written_as_number(self):
        row = _valid_row()
        row["resultado"] = "7,9 x 102"
        row["resultado_tratado"] = 790
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "out.xlsx"
            salvar(df, output_path)

            workbook = load_workbook(output_path, data_only=False)
            worksheet = workbook["results_extract"]
            column_index = RESULTS_EXTRACT_COLUMNS.index("resultado_tratado") + 1
            cell = worksheet.cell(row=2, column=column_index)

            self.assertEqual(cell.value, 790)
            self.assertEqual(cell.number_format, "0.0")

    def test_table_extraction_audit_sheet_is_written_when_requested(self):
        row = _valid_row()
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)
        table_audit_df = pd.DataFrame([{
            "nome_do_arquivo": "a.pdf",
            "id_taxonomia": 1,
            "nome_taxonomia": "Agua Superficial",
            "pagina": 1,
            "tabela_indice": 1,
            "status": "ok",
        }])

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "out.xlsx"
            salvar(
                df,
                output_path,
                output_tabs=["results_extract", "table_extraction_audit", "validation_errors"],
                table_extraction_audit_df=table_audit_df,
            )

            workbook = load_workbook(output_path, data_only=False)
            self.assertIn("table_extraction_audit", workbook.sheetnames)
            worksheet = workbook["table_extraction_audit"]
            self.assertEqual(worksheet.cell(row=2, column=1).value, "a.pdf")
            self.assertEqual(worksheet.freeze_panes, "A2")
            self.assertEqual(worksheet.cell(row=1, column=1).fill.fgColor.rgb, "001F4E78")
            self.assertEqual(worksheet.cell(row=1, column=1).font.color.rgb, "00FFFFFF")

    def test_packaging_preservatives_sheet_is_written_when_requested(self):
        row = _valid_row()
        df = pd.DataFrame([row], columns=RESULTS_EXTRACT_COLUMNS)
        packaging_df = pd.DataFrame([{
            "nome_do_arquivo": "a.pdf",
            "id_taxonomia": 1,
            "nome_taxonomia": "Agua Superficial",
            "id_sample": "687944",
            "identificacao_amostra": "687944 - ECR 01R - P50",
            "embalagem": "Polietileno",
            "volume": "1000 mL",
            "preservacao": "0 a 6ºC",
            "metodos": "Sólidos Dissolvidos Totais.",
        }], columns=PACKAGING_PRESERVATIVES_COLUMNS)

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "out.xlsx"
            salvar(
                df,
                output_path,
                output_tabs=["results_extract", "packaging_preservatives", "validation_errors"],
                packaging_preservatives_df=packaging_df,
            )

            workbook = load_workbook(output_path, data_only=False)
            self.assertIn("packaging_preservatives", workbook.sheetnames)
            worksheet = workbook["packaging_preservatives"]
            self.assertEqual(worksheet.cell(row=2, column=1).value, "a.pdf")
            self.assertEqual(worksheet.cell(row=2, column=6).value, "Polietileno")
            self.assertEqual(worksheet.freeze_panes, "A2")


if __name__ == "__main__":
    unittest.main()

