import unittest
from pathlib import Path

from harpia_parser.config.loader import filter_config_for_template, load_config
from harpia_parser.constants import CLIENT_COLUMNS, RESULTS_EXTRACT_COLUMNS, SAMPLE_COLUMNS


class ConfigLoaderTest(unittest.TestCase):
    def test_taxonomy_output_schemas_match_code_columns(self):
        config = load_config(Path.cwd())

        self.assertEqual(config.df_results_extract_schema["campo"].tolist(), RESULTS_EXTRACT_COLUMNS)
        self.assertEqual(config.df_sample_output_schema["campo"].tolist(), SAMPLE_COLUMNS)
        self.assertEqual(config.df_client_output_schema["campo"].tolist(), CLIENT_COLUMNS)

    def test_template_filter_keeps_only_explicit_template_rules(self):
        config = load_config(Path.cwd())

        water_config = filter_config_for_template(config, "template_laudo_agua_v1")
        fito_config = filter_config_for_template(config, "template_laudo_fito_v1")

        self.assertGreater(len(water_config.section_config_rules), 0)
        self.assertEqual(len(fito_config.section_config_rules), 0)
        self.assertGreater(len(fito_config.metadata_rules), 0)

    def test_relational_config_sheets_do_not_use_template_wildcard(self):
        config = load_config(Path.cwd())

        for sheet_name, df in {
            "metadata_schema": config.df_metadata,
            "client_schema": config.df_client_schema,
            "sample_schema": config.df_sample_schema,
        }.items():
            template_values = df["template_id"].fillna("").astype(str).str.strip()
            with self.subTest(sheet_name=sheet_name):
                self.assertFalse(template_values.isin(["", "*"]).any())

    def test_detection_rules_use_only_pdf_text_as_source(self):
        config = load_config(Path.cwd())

        for sheet_name, df in {
            "template_detection_rules": config.df_template_detection_rules,
        }.items():
            sources = df["source"].fillna("text").astype(str).str.strip().str.lower()
            with self.subTest(sheet_name=sheet_name):
                self.assertEqual(set(sources), {"text"})

    def test_templates_do_not_depend_on_document_type(self):
        config = load_config(Path.cwd())

        self.assertNotIn("document_type_id", config.df_templates.columns)

    def test_result_layouts_use_relational_format(self):
        config = load_config(Path.cwd())

        self.assertEqual(
            config.df_result_layouts.columns.tolist(),
            ["template_id", "tipo_registro", "campo", "coluna_origem", "ativo"],
        )
        self.assertEqual(config.result_layouts["AMOSTRA"]["resultado_col"], 1)
        self.assertEqual(config.result_layouts["AMOSTRA"]["lq_col"], 4)
        self.assertEqual(config.result_layouts["DUPLICATA"]["faixa_aceitacao_col"], 5)

    def test_header_rules_are_limited_to_curated_laudo_templates(self):
        config = load_config(Path.cwd())
        expected_templates = {
            "template_laudo_agua_v1",
            "template_laudo_fito_v1",
            "template_laudo_sedimento_v1",
        }

        for sheet_name, df in {
            "metadata_schema": config.df_metadata,
            "client_schema": config.df_client_schema,
            "sample_schema": config.df_sample_schema,
        }.items():
            with self.subTest(sheet_name=sheet_name):
                self.assertEqual(set(df["template_id"]), expected_templates)

    def test_output_sheets_are_loaded_by_template(self):
        config = load_config(Path.cwd())

        self.assertEqual(
            config.output_sheets["template_laudo_agua_v1"],
            ["results_extract", "sample", "client", "classification_audit", "validation_errors"],
        )


if __name__ == "__main__":
    unittest.main()

