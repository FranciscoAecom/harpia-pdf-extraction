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


if __name__ == "__main__":
    unittest.main()
