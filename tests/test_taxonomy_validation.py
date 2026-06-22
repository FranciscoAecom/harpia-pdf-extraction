import unittest
from pathlib import Path

import pandas as pd

from harpia_parser.config.loader import load_config
from harpia_parser.config.mapper import map_taxonomy_to_runtime_frames
from harpia_parser.config.reader import TaxonomyWorkbook
from harpia_parser.config.validators import validate_raw_taxonomy


def _minimal_workbook() -> TaxonomyWorkbook:
    return TaxonomyWorkbook(
        path=Path("taxonomy.xlsx"),
        item_taxonomia=pd.DataFrame([{
            "id": 1,
            "id_taxonomia": 1,
            "nome": "Agua Superficial",
        }]),
        template=pd.DataFrame([{
            "id": 1,
            "id_item_taxonomia": 1,
            "regex": r"Relat.rio Anal.tico",
            "ativo": "Verdadeiro",
        }]),
        item_template=pd.DataFrame([
            {
                "id": 1,
                "id_template": 1,
                "schema": "template_required",
                "campo": "documento",
                "regex": r"Relat.rio Anal.tico",
                "coluna_origem": "peso=0",
                "tipo_registro": "Nao se aplica",
            },
            {
                "id": 2,
                "id_template": 1,
                "schema": "layout",
                "campo": "resultado",
                "regex": "Nao se aplica",
                "coluna_origem": 4,
                "tipo_registro": "Amostra",
            },
        ]),
        schema=pd.DataFrame([
            {"id": 1, "id_item_taxonomia": 1, "nome": "metadata", "is_serial": "Falso"},
            {"id": 2, "id_item_taxonomia": 1, "nome": "results_extract", "is_serial": "Verdadeiro"},
        ]),
        item_schema=pd.DataFrame([
            {"id": 1, "id_schema": 2, "schema": "results_extract", "campo": "resultado", "tipo": "texto", "nulo": "sim"},
        ]),
    )


class TaxonomyValidationTest(unittest.TestCase):
    def test_current_taxonomy_passes_raw_validation(self):
        config = load_config(Path.cwd())

        self.assertEqual(config.taxonomy_path.name, "taxonomy.xlsx")
        self.assertEqual(set(config.templates), {"template_laudo_agua_v1"})

    def test_rejects_unknown_template_reference(self):
        workbook = _minimal_workbook()
        workbook.item_template.loc[0, "id_template"] = 999

        with self.assertRaisesRegex(ValueError, "item_template.id_template"):
            validate_raw_taxonomy(workbook)

    def test_rejects_invalid_regex(self):
        workbook = _minimal_workbook()
        workbook.item_template.loc[0, "regex"] = "("

        with self.assertRaisesRegex(ValueError, "regex invalida"):
            validate_raw_taxonomy(workbook)

    def test_mapper_uses_explicit_template_identity_when_available(self):
        workbook = _minimal_workbook()
        workbook.template["template_id"] = "template_custom_v1"
        workbook.template["theme_id"] = "laudo_custom"
        workbook.template["nome"] = "Laudo custom"

        validate_raw_taxonomy(workbook)
        frames = map_taxonomy_to_runtime_frames(workbook)

        self.assertEqual(frames["templates"]["template_id"].tolist(), ["template_custom_v1"])
        self.assertEqual(frames["templates"]["theme_id"].tolist(), ["laudo_custom"])
        self.assertEqual(frames["templates"]["nome"].tolist(), ["Laudo custom"])


if __name__ == "__main__":
    unittest.main()
