import unittest
from pathlib import Path

import pandas as pd

from harpia_parser.config.loader import filter_config_for_template, load_config
from harpia_parser.core.context import ClassificationResult, DocumentContext
from harpia_parser.extraction.field_audit import build_field_extraction_audit
from harpia_parser.extraction.metadata_extractor import extract_client, extract_metadata, extract_sample


def _context() -> DocumentContext:
    return DocumentContext(
        pdf_path=Path("documento.pdf"),
        nome_do_arquivo="documento.pdf",
        template_id="template_laudo_agua_v1",
        tipo_laudo="laudo_agua",
        id_taxonomia=1,
        nome_taxonomia="Água Superficial",
        versao_template=1,
        classification=ClassificationResult(None, None, None, None, None, []),
    )


class FieldExtractionAuditTest(unittest.TestCase):
    def setUp(self):
        self.config = filter_config_for_template(load_config(Path.cwd()), "template_laudo_agua_v1")

    def _audit(self, text: str) -> pd.DataFrame:
        metadata = extract_metadata(text, self.config)
        sample = extract_sample(text, metadata, self.config)
        client = extract_client(text, metadata, self.config)
        return build_field_extraction_audit(
            [(text, [])], _context(), self.config, metadata, sample, client
        )

    def test_reports_separate_real_coordinates_and_climate_fields(self):
        text = (
            "ID Amostra: 636341\nData Coleta: 12/09/2025 08:00\n"
            "Latitude: -19,2324 Longitude: -42,3271\n"
            "Condições climáticas nas últimas 24 horas: Sol\n"
            "Condições climáticas no momento da coleta: Nublado Local da Coleta: RSA 01\n"
            "Latitude (coordenada real): -19,23234 Longitude (coordenada real): -42,32715\n"
        )
        audit = self._audit(text).set_index("campo")

        for field in (
            "latitude_real",
            "longitude_real",
            "condicoes_climaticas_nas_ultimas_24_horas",
            "condicoes_climaticas_no_momento_da_coleta",
        ):
            self.assertEqual(audit.loc[field, "status"], "ok")

    def test_detects_value_contaminated_by_another_field(self):
        text = "Observações: NA Condições climáticas nas últimas 24 horas: Sol\n"
        sample = pd.DataFrame([{"observacoes": text.removeprefix("Observações: ")}])
        audit = build_field_extraction_audit(
            [(text, [])], _context(), self.config, {}, sample, pd.DataFrame()
        )
        row = audit[(audit["schema_origem"] == "sample") & (audit["campo"] == "observacoes")].iloc[0]

        self.assertEqual(row["status"], "possivel_contaminacao")
        self.assertIn("condicoes_climaticas_nas_ultimas_24_horas", row["campos_detectados_no_valor"])


if __name__ == "__main__":
    unittest.main()
