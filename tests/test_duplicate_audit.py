import tempfile
import unittest
from pathlib import Path

import pandas as pd

from harpia_parser.audit.duplicate_audit import (
    build_duplicate_audit,
    build_duplicate_candidate,
)


def _sample(id_amostra: str, identificacao: str = "LAUDO-1") -> pd.DataFrame:
    return pd.DataFrame([{
        "nome_do_arquivo": "a.pdf",
        "id_taxonomia": 1,
        "nome_taxonomia": "Agua Superficial",
        "versao": "1",
        "id_amostra": id_amostra,
        "identificacao_amostra": identificacao,
        "data_publicacao": "01/01/2025",
        "data_coleta": "31/12/2024",
    }])


def _result(id_amostra: str, resultado: str = "0,1") -> pd.DataFrame:
    return pd.DataFrame([{
        "id_amostra": id_amostra,
        "categoria": "Resultados Analiticos",
        "subcategoria": "Fisico-Quimico",
        "parameter": "Fosfato",
        "resultado": resultado,
        "lq": "0,1 mg/L",
        "ld": None,
    }])


class DuplicateAuditTest(unittest.TestCase):
    def test_detects_exact_file_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.pdf"
            second = Path(tmp) / "b.pdf"
            first.write_bytes(b"same-pdf")
            second.write_bytes(b"same-pdf")

            audit = build_duplicate_audit([
                build_duplicate_candidate(first, "texto", _result("1"), _sample("1")),
                build_duplicate_candidate(second, "texto", _result("1"), _sample("1")),
            ])

            self.assertEqual(set(audit["status"]), {"duplicado_exato_arquivo"})
            self.assertTrue(audit["arquivo_referencia"].notna().all())

    def test_detects_textual_duplicates_when_binary_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.pdf"
            second = Path(tmp) / "b.pdf"
            first.write_bytes(b"pdf-a")
            second.write_bytes(b"pdf-b")

            audit = build_duplicate_audit([
                build_duplicate_candidate(first, "Mesmo texto", _result("1"), _sample("1")),
                build_duplicate_candidate(second, "Mesmo   texto", _result("1"), _sample("1")),
            ])

            self.assertEqual(set(audit["status"]), {"duplicado_textual"})

    def test_detects_same_sample_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.pdf"
            second = Path(tmp) / "b.pdf"
            first.write_bytes(b"pdf-a")
            second.write_bytes(b"pdf-b")

            audit = build_duplicate_audit([
                build_duplicate_candidate(first, "texto a", _result("1", "0,1"), _sample("1", "LAUDO-1")),
                build_duplicate_candidate(second, "texto b", _result("1", "0,2"), _sample("1", "LAUDO-2")),
            ])

            self.assertEqual(set(audit["status"]), {"conflito_mesma_amostra"})

    def test_detects_possible_replacement_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.pdf"
            second = Path(tmp) / "b.pdf"
            first.write_bytes(b"pdf-a")
            second.write_bytes(b"pdf-b")

            audit = build_duplicate_audit([
                build_duplicate_candidate(first, "texto original", _result("1"), _sample("1", "LAUDO-1")),
                build_duplicate_candidate(
                    second,
                    "Este relatorio analitico cancela e substitui o relatorio anterior.",
                    _result("1", "0,2"),
                    _sample("1", "LAUDO-1"),
                ),
            ])

            self.assertIn("possivel_versao_substituta", set(audit["status"]))


if __name__ == "__main__":
    unittest.main()
