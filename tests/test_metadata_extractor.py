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
        self.assertEqual(metadata["codigo_laudo"], "Relatório Analítico 68659/2024.0.A")

    def test_extracts_partial_report_code_when_number_is_on_next_line(self):
        config = filter_config_for_template(load_config(Path.cwd()), "template_laudo_agua_v1")
        texto = (
            "Relat\u00f3rio Anal\u00edtico Parcial\n"
            "73406/2025.1.A\n"
            "InformaÃ§Ãµes da Amostra - NÂº: 73406-1/2025.1 - ZCN 05 - P50\n"
            "Tipo de Amostra: Ãgua Salina Classe 1 ID Amostra: 871654\n"
            "Data Coleta: 17/10/2025 07:50\n"
            "Latitude: -18,72408\n"
            "Longitude: -39,74225\n"
        )

        metadata = extract_metadata(texto, config)

        self.assertEqual(metadata["codigo_laudo"], "Relat\u00f3rio Anal\u00edtico Parcial 73406/2025.1.A")

    def test_extracts_full_non_conformity_description_across_planning_line(self):
        config = filter_config_for_template(load_config(Path.cwd()), "template_laudo_agua_v1")
        texto = (
            "Relatório Analítico 18951/2025.0.A\n"
            "Informações da Amostra - Nº: 18951-1/2025.0 - LJP 01 - P1\n"
            "Tipo de Amostra: Água Doce Classe 2 ID Amostra: 123456\n"
            "Data Coleta: 25/03/2025 08:00\n"
            "Latitude: -19,35330\n"
            "Longitude: -40,08720\n"
            "Descrição da não-conformidade: A análise de ferro II foi executada fora do prazo estabelecido\n"
            "em INT-ANL-035. Entretanto, a análise está em\n"
            "Planejamento de Amostragem: CA1682/2025\n"
            "conformidade com os aspectos técnicos descritos e justificados na Nota Técnica n.°116 do GTA-\n"
            "PMQQS\n"
            "Resultados Analíticos\n"
        )

        metadata = extract_metadata(texto, config)
        sample = extract_sample(texto, metadata, config)

        self.assertEqual(sample.loc[0, "planejamento_amostragem"], "CA1682/2025")
        descricao = str(sample.loc[0, "descricao_nao_conformidade"])
        self.assertIn("Entretanto", descricao)
        self.assertIn("conformidade", descricao)
        self.assertNotIn("Planejamento de Amostragem", descricao)

    def test_sample_planning_keeps_only_planning_code(self):
        config = filter_config_for_template(load_config(Path.cwd()), "template_laudo_agua_v1")
        texto = (
            "ID Amostra: 123456\n"
            "Data Coleta: 01/01/2025\n"
            "Planejamento de Amostragem: CA5056/2025 Salinidade: 2,26 ‰\n"
            "Descrição da não-conformidade: -\n"
            "Resultados Analíticos\n"
        )

        metadata = extract_metadata(texto, config)
        sample = extract_sample(texto, metadata, config)

        self.assertEqual(sample.loc[0, "planejamento_amostragem"], "CA5056/2025")
        self.assertEqual(sample.loc[0, "descricao_nao_conformidade"], "-")

    def test_extracts_replaced_report_notice(self):
        config = filter_config_for_template(load_config(Path.cwd()), "template_laudo_agua_v1")
        texto = (
            "ID Amostra: 123456\n"
            "Data Coleta: 01/01/2025\n"
            "Este relatório analítico cancela e substitui o relatório 72768/2024.0\n"
            "Resultados Analíticos\n"
        )

        metadata = extract_metadata(texto, config)
        sample = extract_sample(texto, metadata, config)

        self.assertEqual(
            sample.loc[0, "codigo_laudo_substituido"],
            "Este relatório analítico cancela e substitui o relatório 72768/2024.0",
        )


if __name__ == "__main__":
    unittest.main()
