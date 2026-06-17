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

    def test_template_filter_keeps_common_rules_and_excludes_other_templates(self):
        config = load_config(Path.cwd())

        water_config = filter_config_for_template(config, "template_laudo_agua_v1")
        fito_config = filter_config_for_template(config, "template_laudo_fito_v1")

        self.assertGreater(len(water_config.section_config_rules), 0)
        self.assertEqual(len(fito_config.section_config_rules), 0)
        self.assertGreater(len(fito_config.metadata_rules), 0)

    def test_output_sheets_are_loaded_by_template(self):
        config = load_config(Path.cwd())

        self.assertEqual(
            config.output_sheets["template_laudo_agua_v1"],
            ["results_extract", "sample", "client", "classification_audit", "validation_errors"],
        )


if __name__ == "__main__":
    unittest.main()

