from dataclasses import dataclass

import pandas as pd


@dataclass
class PipelineOutputs:
    results: pd.DataFrame
    sample: pd.DataFrame
    client: pd.DataFrame
    packaging_preservatives: pd.DataFrame
    notes: pd.DataFrame
    general_considerations: pd.DataFrame
    conformity_statement: pd.DataFrame
    validation_key: pd.DataFrame
    classification_audit: pd.DataFrame
    table_extraction_audit: pd.DataFrame
    section_extraction_audit: pd.DataFrame
    field_extraction_audit: pd.DataFrame
    revision_reason: pd.DataFrame

