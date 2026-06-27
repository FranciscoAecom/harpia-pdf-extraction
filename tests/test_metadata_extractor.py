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

    def test_real_coordinates_are_separate_and_do_not_contaminate_sample(self):
        config = filter_config_for_template(load_config(Path.cwd()), "template_laudo_agua_v1")
        texto = (
            "ID Amostra: 636341\n"
            "Data Coleta: 12/09/2025 08:00\n"
            "Latitude: -19,2324 Longitude: -42,3271\n"
            "Observações: NA Condições climáticas nas últimas 24 horas: Sol\n"
            "Condições climáticas no momento da coleta: Nublado Local da Coleta: RSA 01\n"
            "Descrição da não-conformidade: Texto preservado antes da coordenada.\n"
            "Planejamento de Amostragem: CA5602/2025\n"
            "Texto preservado depois da coordenada.\n"
            "Latitude (coordenada real): -19,23234\n"
            "Resultados Analíticos\n"
        )

        metadata = extract_metadata(texto, config)
        sample = extract_sample(texto, metadata, config)

        self.assertEqual(sample.loc[0, "latitude"], -19.2324)
        self.assertEqual(sample.loc[0, "longitude"], -42.3271)
        self.assertEqual(sample.loc[0, "latitude_real"], -19.23234)
        self.assertIsNone(sample.loc[0, "longitude_real"])
        self.assertEqual(sample.loc[0, "observacoes"], "NA")
        self.assertEqual(sample.loc[0, "condicoes_climaticas_nas_ultimas_24_horas"], "Sol")
        self.assertEqual(sample.loc[0, "condicoes_climaticas_no_momento_da_coleta"], "Nublado")
        descricao = str(sample.loc[0, "descricao_nao_conformidade"])
        self.assertIn("Texto preservado antes", descricao)
        self.assertIn("Texto preservado depois", descricao)
        self.assertNotIn("coordenada real", descricao)

    def test_both_real_coordinates_are_kept_separate_from_standard_coordinates(self):
        config = filter_config_for_template(load_config(Path.cwd()), "template_laudo_agua_v1")
        texto = (
            "ID Amostra: 739911\n"
            "Data Coleta: 21/10/2025 08:00\n"
            "Latitude: -19,3500 Longitude: -40,0800\n"
            "Latitude (coordenada real): -19,35302336 "
            "Longitude (coordenada real): -40,08751597\n"
        )

        metadata = extract_metadata(texto, config)
        sample = extract_sample(texto, metadata, config)

        self.assertEqual(sample.loc[0, "latitude"], -19.35)
        self.assertEqual(sample.loc[0, "longitude"], -40.08)
        self.assertEqual(sample.loc[0, "latitude_real"], -19.35302336)
        self.assertEqual(sample.loc[0, "longitude_real"], -40.08751597)

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
