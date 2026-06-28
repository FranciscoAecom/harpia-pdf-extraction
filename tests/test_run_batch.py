import tempfile
import unittest
from pathlib import Path

import pandas as pd

from harpia_parser.batch.cache import BatchCache, exact_duplicate_plan


class RunBatchTest(unittest.TestCase):
    @staticmethod
    def _taxonomy(path: Path, *, rule: str = "agua", audit_field: str = "status") -> None:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame([{"id": 1, "nome": "Agua"}]).to_excel(writer, sheet_name="item_taxonomia", index=False)
            pd.DataFrame([{"id": 1, "id_item_taxonomia": 1, "template_id": "agua"}]).to_excel(writer, sheet_name="template", index=False)
            pd.DataFrame([{"id": 1, "id_template": 1, "schema": "metadata", "campo": "tipo", "regex": rule}]).to_excel(writer, sheet_name="item_template", index=False)
            pd.DataFrame([{"id": 1, "nome": "field_extraction_audit"}]).to_excel(writer, sheet_name="schema", index=False)
            pd.DataFrame([{"id": 1, "id_schema": 1, "schema": "field_extraction_audit", "campo": audit_field}]).to_excel(writer, sheet_name="item_schema", index=False)

    def test_hash_cache_reuses_unchanged_files_and_invalidates_changed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "a.pdf"
            cache = root / "cache" / "hashes.json"
            pdf.write_bytes(b"first")

            batch_cache = BatchCache(cache.parent, root, root)
            first, first_hits, first_failures = batch_cache.file_hashes([pdf], 1)
            second, second_hits, second_failures = batch_cache.file_hashes([pdf], 1)
            pdf.write_bytes(b"changed-content")
            third, third_hits, third_failures = batch_cache.file_hashes([pdf], 1)

            self.assertEqual(first_hits, 0)
            self.assertEqual(second_hits, 1)
            self.assertEqual(third_hits, 0)
            self.assertEqual(first, second)
            self.assertNotEqual(first[str(pdf)], third[str(pdf)])
            self.assertFalse(first_failures or second_failures or third_failures)

    def test_missing_file_during_hash_is_reported_without_stopping_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            available = root / "available.pdf"
            missing = root / "missing.pdf"
            available.write_bytes(b"pdf")

            hashes, _, failures = BatchCache(root / "cache", root, root).file_hashes(
                [available, missing], workers=2
            )

            self.assertIn(str(available), hashes)
            self.assertNotIn(str(missing), hashes)
            self.assertIn(str(missing), failures)

    def test_exact_duplicates_are_removed_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.pdf"
            duplicate = root / "b.pdf"
            different = root / "c.pdf"
            first.write_bytes(b"same-pdf")
            duplicate.write_bytes(b"same-pdf")
            different.write_bytes(b"different-pdf")
            pdfs = [first, duplicate, different]

            hashes, _, failures = BatchCache(root / "cache", root, root).file_hashes(pdfs, workers=2)
            self.assertFalse(failures)
            canonical, duplicates = exact_duplicate_plan(pdfs, hashes)

            self.assertEqual(canonical, [first, different])
            self.assertEqual(duplicates, {str(duplicate): first})

    def test_runtime_signature_ignores_output_code_and_audit_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            extraction = source / "harpia_parser" / "extraction" / "parser.py"
            output_writer = source / "harpia_parser" / "formatting" / "output_writer.py"
            extraction.parent.mkdir(parents=True)
            output_writer.parent.mkdir(parents=True)
            extraction.write_text("VERSION = 1", encoding="utf-8")
            output_writer.write_text("STYLE = 1", encoding="utf-8")
            taxonomy = root / "taxonomy.xlsx"
            self._taxonomy(taxonomy)
            cache = BatchCache(root / "cache", root, source)

            initial = cache.runtime_signature(taxonomy, root / "run_batch.py")
            output_writer.write_text("STYLE = 2", encoding="utf-8")
            after_output_change = cache.runtime_signature(taxonomy, root / "run_batch.py")
            self._taxonomy(taxonomy, audit_field="observacao")
            after_audit_schema_change = cache.runtime_signature(taxonomy, root / "run_batch.py")

            self.assertEqual(initial, after_output_change)
            self.assertEqual(initial, after_audit_schema_change)

    def test_runtime_signature_changes_with_parser_or_taxonomy_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            parser = source / "harpia_parser" / "extraction" / "parser.py"
            parser.parent.mkdir(parents=True)
            parser.write_text("VERSION = 1", encoding="utf-8")
            taxonomy = root / "taxonomy.xlsx"
            self._taxonomy(taxonomy)
            cache = BatchCache(root / "cache", root, source)

            initial = cache.runtime_signature(taxonomy, root / "run_batch.py")
            parser.write_text("VERSION = 2", encoding="utf-8")
            after_parser_change = cache.runtime_signature(taxonomy, root / "run_batch.py")
            self._taxonomy(taxonomy, rule="sedimento")
            after_rule_change = cache.runtime_signature(taxonomy, root / "run_batch.py")

            self.assertNotEqual(initial, after_parser_change)
            self.assertNotEqual(after_parser_change, after_rule_change)


if __name__ == "__main__":
    unittest.main()
