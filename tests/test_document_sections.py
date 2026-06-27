import unittest
from pathlib import Path

import pandas as pd

from harpia_parser.constants import VALIDATION_KEY_COLUMNS
from harpia_parser.core.context import ClassificationResult, DocumentContext
from harpia_parser.extraction.document_sections import extract_document_section


class DocumentSectionsTest(unittest.TestCase):
    def test_notes_capture_multiline_normative_text_until_document_footer(self):
        context = DocumentContext(
            pdf_path=Path("a.pdf"),
            nome_do_arquivo="a.pdf",
            template_id="template_laudo_agua_v1",
            tipo_laudo="laudo_agua",
            id_taxonomia=1,
            nome_taxonomia="Agua Superficial",
            versao_template="1",
            classification=ClassificationResult(
                template_id="template_laudo_agua_v1",
                tipo_laudo="laudo_agua",
                id_taxonomia=1,
                nome_taxonomia="Agua Superficial",
                versao_template="1",
                scores=[],
            ),
        )
        rules = pd.DataFrame([{
            "campo": "texto",
            "regex": (
                r"(?:^|\n)[ \t]*Notas?[ \t]*:?[ \t]*(?:\n|$)(.*?)"
                r"(?=\n[ \t]*(?:Registro\s+da\s+Coleta|FO-ANL-\d+)|\Z)"
            ),
        }])
        pages = [(
            "Notas\nLegendas\nResolucao CONAMA 357: Nota 2 = texto completo.\n"
            "Resolucao CONAMA 357: Nota 3 = 3,7 mg/L N, para pH <= 7,5.\n"
            "Registro da Coleta\nFO-ANL-162",
            [],
        )]

        df = extract_document_section(
            pages,
            context,
            {"id_amostra": "123456"},
            rules,
            columns=[
                "nome_do_arquivo",
                "id_taxonomia",
                "nome_taxonomia",
                "versao_template",
                "id_amostra",
                "pagina",
                "texto",
            ],
        )

        self.assertEqual(len(df), 1)
        notes_text = str(df.loc[0, "texto"])
        self.assertIn("Nota 2 = texto completo", notes_text)
        self.assertIn("Nota 3 = 3,7 mg/L N", notes_text)
        self.assertNotIn("Registro da Coleta", notes_text)

    def test_validation_key_ignores_nonexistent_form_code(self):
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
        rules = pd.DataFrame([{
            "campo": "chave_validacao",
            "regex": r"(?:^|\n)\s*Chave\s+de\s+Valida..o\s*:?\s*([A-Za-z0-9][A-Za-z0-9\-_.]+)",
        }])
        paginas = [
            ("Chave de Validacao: FO-ANL-162", []),
            ("Chave de Validacao: ABCD-1234-EFGH", []),
        ]

        df = extract_document_section(
            paginas,
            context,
            {"id_amostra": "123456"},
            rules,
            columns=VALIDATION_KEY_COLUMNS,
        )

        self.assertEqual(df["chave_validacao"].tolist(), ["ABCD-1234-EFGH"])


if __name__ == "__main__":
    unittest.main()
