import unittest

import pandas as pd

from harpia_parser.audit.document_reconciliation import build_document_reconciliation_audit


class DocumentReconciliationAuditTest(unittest.TestCase):
    def _build(self, *, sample_id=10, sample_date="01/01/2025", received="02/01/2025", published="03/01/2025"):
        common = {
            "nome_do_arquivo": "a.pdf",
            "id_taxonomia": 1,
            "nome_taxonomia": "Agua Superficial",
            "versao_template": 1,
            "id_amostra": 10,
        }
        results = pd.DataFrame([
            {**common, "parametro": "pH", "acm_unidade": None},
            {**common, "parametro": "Ferro", "acm_unidade": "mg/L"},
        ])
        sample = pd.DataFrame([{
            **common,
            "id_amostra": sample_id,
            "data_coleta": sample_date,
            "data_recebimento": received,
            "data_publicacao": published,
        }])
        client = pd.DataFrame([common])
        return build_document_reconciliation_audit(
            results,
            sample,
            client,
            pd.DataFrame(),
            pd.DataFrame([{"nome_do_arquivo": "a.pdf", "status": "ok"}]),
            pd.DataFrame([{"nome_do_arquivo": "a.pdf", "status": "ok"}]),
            pd.DataFrame([{"nome_do_arquivo": "a.pdf", "status": "ok"}]),
            pd.DataFrame(),
        )

    def test_consistent_document_is_ok(self):
        row = self._build().iloc[0]
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["coerencia_temporal"], "ok")

    def test_identity_divergence_is_error(self):
        row = self._build(sample_id=11).iloc[0]
        self.assertEqual(row["status"], "erro")
        self.assertIn("id_amostra", str(row["observacao"]))

    def test_invalid_date_order_is_alert(self):
        row = self._build(received="05/01/2025", published="04/01/2025").iloc[0]
        self.assertEqual(row["status"], "alerta")
        self.assertEqual(row["coerencia_temporal"], "inconsistente")

    def test_validation_errors_are_counted_and_explained(self):
        common = {
            "nome_do_arquivo": "a.pdf", "id_taxonomia": 1,
            "nome_taxonomia": "Agua Superficial", "versao_template": 1,
            "id_amostra": 10,
        }
        audit = build_document_reconciliation_audit(
            pd.DataFrame([{**common, "parametro": "Ferro", "acm_unidade": "mg/L"}]),
            pd.DataFrame([{**common, "data_coleta": "01/01/2025", "data_recebimento": "02/01/2025", "data_publicacao": "03/01/2025"}]),
            pd.DataFrame([common]), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
            pd.DataFrame([{"id_amostra": 10, "message": "valor deve ser numerico"}]),
        )
        row = audit.iloc[0]
        self.assertEqual(row["status"], "alerta")
        self.assertEqual(row["erros_validacao"], 1)
        self.assertIn("Erros de validacao", str(row["observacao"]))


if __name__ == "__main__":
    unittest.main()
