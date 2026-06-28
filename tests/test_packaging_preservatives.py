import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from harpia_parser.core.context import ClassificationResult, DocumentContext
from harpia_parser.extraction.packaging_preservatives import extract_packaging_preservatives


class PackagingPreservativesTest(unittest.TestCase):
    def test_section_title_can_continue_to_table_on_next_page(self):
        classification = ClassificationResult(
            template_id="template_laudo_agua_v1",
            tipo_laudo="laudo_agua",
            id_taxonomia=1,
            nome_taxonomia="Agua Superficial",
            versao_template="1",
            scores=[],
        )
        context = DocumentContext(
            pdf_path=Path("a.pdf"),
            nome_do_arquivo="a.pdf",
            template_id="template_laudo_agua_v1",
            tipo_laudo="laudo_agua",
            id_taxonomia=1,
            nome_taxonomia="Agua Superficial",
            versao_template="1",
            classification=classification,
        )
        config = SimpleNamespace(df_packaging_preservatives_rules=pd.DataFrame([
            {"campo": "section_start", "regex": r"Embalagens\s+e\s+Preservantes"},
            {"campo": "table_header", "regex": r"Embalagem\s+Volume\s+Preserva..o\s+M.todos"},
            {"campo": "sample_identification", "regex": r"^\s*\d+\s*-\s*.+$"},
            {"campo": "container_value", "regex": r"^(?:Polietileno|Frasco\s+Est.ril|Vidro\s+.mbar|Vial)$"},
            {"campo": "volume_value", "regex": r"^\d+(?:[,.]\d+)?\s*mL$"},
        ]))
        pages = [
            ("Embalagens e Preservantes\n123456 - Ponto A", [
                [["123456 - Ponto A", "", "", ""]],
            ]),
            ("Embalagem Volume Preservacao Metodos", [[
                ["Polietileno", "1000 mL", "0 a 6 C", "Metais"],
            ]]),
        ]

        result = extract_packaging_preservatives(pages, context, config)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "id_amostra"], "123456")
        self.assertEqual(result.loc[0, "embalagem"], "Polietileno")

    def test_other_tables_on_section_page_are_not_extracted_as_packaging(self):
        classification = ClassificationResult(
            "template_laudo_agua_v1", "laudo_agua", 1, "Agua Superficial", "1", []
        )
        context = DocumentContext(
            Path("a.pdf"), "a.pdf", "template_laudo_agua_v1", "laudo_agua",
            1, "Agua Superficial", "1", classification,
        )
        config = SimpleNamespace(df_packaging_preservatives_rules=pd.DataFrame([
            {"campo": "section_start", "regex": r"Embalagens\s+e\s+Preservantes"},
            {"campo": "table_header", "regex": r"Embalagem\s+Volume\s+Preserva..o\s+M.todos"},
            {"campo": "sample_identification", "regex": r"^\s*\d+\s*-\s*.+$"},
            {"campo": "container_value", "regex": r"^(?:Polietileno|Frasco\s+Est.ril|Vidro\s+.mbar|Vial)$"},
            {"campo": "volume_value", "regex": r"^\d+(?:[,.]\d+)?\s*mL$"},
        ]))
        pages = [("Embalagens e Preservantes\nEmbalagem Volume Preservacao Metodos", [
            [["Polietileno", "100 mL", "0 a 6 C", "Metais"]],
            [["Zinco Total", "CQ123", "0,25", "mg/L"]],
            [["Notas", None, None, None]],
        ])]

        result = extract_packaging_preservatives(pages, context, config)

        self.assertEqual(result["embalagem"].tolist(), ["Polietileno"])


if __name__ == "__main__":
    unittest.main()
