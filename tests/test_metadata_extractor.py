import unittest
from pathlib import Path

from harpia_parser.config.loader import filter_config_for_template, load_config
from harpia_parser.extraction.metadata_extractor import extract_metadata, extract_sample


class MetadataExtractorTest(unittest.TestCase):
    def test_extracts_sample_identification_number(self):
        config = filter_config_for_template(load_config(Path.cwd()), "template_laudo_agua_v1")
        texto = (
            "Relatório Analítico 68659/2024.0.A\n"
            "Informações da Amostra - Nº: 68659-1/2024.0 - ECR 01R - P50\n"
            "Tipo de Amostra: Água Salobra Classe 1 ID Amostra: 687944\n"
            "Data Coleta: 13/11/2024 07:53\n"
            "Latitude: -18,60000\n"
            "Longitude: -39,73100\n"
        )

        metadata = extract_metadata(texto, config)
        sample = extract_sample(texto, metadata, config)

        self.assertEqual(sample.loc[0, "id_amostra"], "687944")
        self.assertEqual(sample.loc[0, "identificacao_amostra"], "68659-1/2024.0 - ECR 01R - P50")


if __name__ == "__main__":
    unittest.main()
