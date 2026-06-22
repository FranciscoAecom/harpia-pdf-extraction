import unittest
from pathlib import Path

import pandas as pd

from harpia_parser.config.loader import filter_config_for_template, load_config
from harpia_parser.constants import CLIENT_COLUMNS, RESULTS_EXTRACT_COLUMNS, SAMPLE_COLUMNS


class ConfigLoaderTest(unittest.TestCase):
    def test_output_model_matches_code_columns(self):
        config = load_config(Path.cwd())

        self.assertEqual(config.df_results_extract_model["campo"].tolist(), RESULTS_EXTRACT_COLUMNS)
        self.assertEqual(config.df_sample_output_model["campo"].tolist(), SAMPLE_COLUMNS)
        self.assertEqual(config.df_client_output_model["campo"].tolist(), CLIENT_COLUMNS)

    def test_template_filter_keeps_only_explicit_template_rules(self):
        config = load_config(Path.cwd())

        water_config = filter_config_for_template(config, "template_laudo_agua_v1")
        fito_config = filter_config_for_template(config, "template_laudo_fito_v1")

        self.assertGreater(len(water_config.category_type_rules), 0)
        self.assertEqual(len(fito_config.category_type_rules), 0)
        self.assertEqual(len(fito_config.metadata_rules), 0)

    def test_relational_config_sheets_do_not_use_template_wildcard(self):
        config = load_config(Path.cwd())

        for sheet_name, df in {
            "metadata": config.df_metadata_text_rules,
            "client": config.df_client_text_rules,
            "sample": config.df_sample_text_rules,
        }.items():
            template_values = df["template_id"].fillna("").astype(str).str.strip()
            with self.subTest(sheet_name=sheet_name):
                self.assertFalse(template_values.isin(["", "*"]).any())

    def test_detection_rules_use_only_pdf_text_as_source(self):
        config = load_config(Path.cwd())

        for sheet_name, df in {
            "template_rules": config.df_template_rules,
        }.items():
            sources = df["source"].fillna("text").astype(str).str.strip().str.lower()
            with self.subTest(sheet_name=sheet_name):
                self.assertEqual(set(sources), {"text"})

    def test_templates_define_theme_id(self):
        config = load_config(Path.cwd())

        self.assertIn("theme_id", config.df_templates.columns)

    def test_boolean_columns_are_real_booleans(self):
        config = load_config(Path.cwd())
        boolean_columns = {"ativo", "obrigatorio", "extrair_subcategoria"}

        for sheet_name, df in {
            "templates": config.df_templates,
            "template_rules": config.df_template_rules,
            "metadata": config.df_metadata_text_rules,
            "client": config.df_client_text_rules,
            "sample": config.df_sample_text_rules,
            "category_type": config.df_category_type_rules,
            "category_alias": config.df_category_alias_rules,
            "subcategory_alias": config.df_subcategory_alias_rules,
            "table_layouts": config.df_table_extraction_rules,
            "header_alias": config.df_header_alias_rules,
            "continuation": config.df_continuation_rules,
            "results_extract_model": config.df_results_extract_model,
            "sample_output_model": config.df_sample_output_model,
            "client_output_model": config.df_client_output_model,
        }.items():
            for column in boolean_columns & set(df.columns):
                with self.subTest(sheet_name=sheet_name, column=column):
                    self.assertTrue(pd.api.types.is_bool_dtype(df[column]))

    def test_table_layouts_use_relational_format(self):
        config = load_config(Path.cwd())

        self.assertEqual(
            config.df_table_extraction_rules.columns.tolist(),
            ["template_id", "tipo_registro", "campo", "coluna_origem", "ativo"],
        )
        self.assertEqual(config.table_layouts["AMOSTRA"]["unidade_col"], 1)
        self.assertEqual(config.table_layouts["AMOSTRA"]["ld_col"], 2)
        self.assertEqual(config.table_layouts["AMOSTRA"]["lq_col"], 3)
        self.assertEqual(config.table_layouts["AMOSTRA"]["resultado_col"], 4)
        self.assertEqual(config.table_layouts["DUPLICATA"]["faixa_aceitacao_col"], 5)

    def test_header_alias_rules_include_normative_fields(self):
        config = filter_config_for_template(load_config(Path.cwd()), "template_laudo_agua_v1")

        self.assertTrue(
            any(
                rule["field"] == "copam_cerh_col"
                and "copam" in rule["regex"].pattern.lower()
                for rule in config.header_alias_rules
            )
        )

        self.assertTrue(
            any(
                rule["field"] == "conama_col"
                and "conama" in rule["regex"].pattern.lower()
                for rule in config.header_alias_rules
            )
        )

    def test_header_rules_are_limited_to_curated_laudo_templates(self):
        config = load_config(Path.cwd())
        expected_templates = {"template_laudo_agua_v1"}

        for sheet_name, df in {
            "metadata": config.df_metadata_text_rules,
            "client": config.df_client_text_rules,
            "sample": config.df_sample_text_rules,
        }.items():
            with self.subTest(sheet_name=sheet_name):
                self.assertEqual(set(df["template_id"]), expected_templates)

    def test_output_tabs_are_loaded_by_template(self):
        config = load_config(Path.cwd())

        self.assertEqual(
            config.output_tabs["template_laudo_agua_v1"],
            [
                "results_extract",
                "sample",
                "client",
                "table_extraction_audit",
                "classification_audit",
                "validation_errors",
            ],
        )

    def test_subcategory_alias_rules_are_loaded_by_template(self):
        config = load_config(Path.cwd())

        water_config = filter_config_for_template(config, "template_laudo_agua_v1")
        self.assertGreater(len(water_config.subcategory_alias_rules), 0)
        self.assertTrue(
            any(
                rule["categoria"] == "Controle de Qualidade"
                and rule["tipo_registro"] == "RECUPERACAO"
                for rule in water_config.subcategory_alias_rules
            )
        )


if __name__ == "__main__":
    unittest.main()

