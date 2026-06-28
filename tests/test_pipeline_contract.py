import unittest
from pathlib import Path

from harpia_parser.config.loader import load_config
from harpia_parser.core.pipeline import run_pipeline_document


class PipelineContractTest(unittest.TestCase):
    def test_in_scope_document_returns_all_thirteen_outputs(self):
        text = (
            "Relatório Analítico 123/2025.0\n"
            "Informações da Amostra - Nº: 123-1/2025.0\n"
            "Tipo de Amostra: Água Doce ID Amostra: 123456\n"
            "Critério de Conformidade: Resolução CONAMA Nº 357\n"
            "Data Coleta: 01/01/2025 08:00\n"
            "Resultados Analíticos\n"
        )
        outputs = run_pipeline_document(
            Path("documento.pdf"),
            load_config(Path.cwd()),
            pdf_content=(text, [(text, [])]),
        )

        self.assertEqual(len(outputs), 13)


if __name__ == "__main__":
    unittest.main()
