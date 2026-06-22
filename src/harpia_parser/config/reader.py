from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REQUIRED_TAXONOMY_SHEETS = {
    "item_taxonomia",
    "template",
    "item_template",
    "schema",
    "item_schema",
}


@dataclass(frozen=True)
class TaxonomyWorkbook:
    path: Path
    item_taxonomia: pd.DataFrame
    template: pd.DataFrame
    item_template: pd.DataFrame
    schema: pd.DataFrame
    item_schema: pd.DataFrame


def read_taxonomy_workbook(taxonomy_path: Path) -> TaxonomyWorkbook:
    excel = pd.ExcelFile(taxonomy_path)
    try:
        sheet_names = {str(sheet_name) for sheet_name in excel.sheet_names}
        missing = sorted(REQUIRED_TAXONOMY_SHEETS - sheet_names)
        if missing:
            raise ValueError(f"Taxonomia invalida. Abas obrigatorias ausentes: {missing}")

        return TaxonomyWorkbook(
            path=taxonomy_path,
            item_taxonomia=pd.read_excel(excel, "item_taxonomia"),
            template=pd.read_excel(excel, "template"),
            item_template=pd.read_excel(excel, "item_template"),
            schema=pd.read_excel(excel, "schema"),
            item_schema=pd.read_excel(excel, "item_schema"),
        )
    finally:
        excel.close()
