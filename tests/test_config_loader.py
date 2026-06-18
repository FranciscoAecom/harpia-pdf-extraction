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
        self.assertEqual(len(fito_config.metadata_rules), 0)

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

    def test_water_header_rules_are_not_replicated_to_uncurated_templates(self):
        config = load_config(Path.cwd())

        for sheet_name, df in {
            "metadata_schema": config.df_metadata,
            "client_schema": config.df_client_schema,
            "sample_schema": config.df_sample_schema,
        }.items():
            with self.subTest(sheet_name=sheet_name):
                self.assertEqual(set(df["template_id"]), {"template_laudo_agua_v1"})

    def test_output_sheets_are_loaded_by_template(self):
        config = load_config(Path.cwd())

        self.assertEqual(
            config.output_sheets["template_laudo_agua_v1"],
            ["results_extract", "sample", "client", "classification_audit", "validation_errors"],
        )


if __name__ == "__main__":
    unittest.main()

