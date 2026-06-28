import tempfile
import unittest
from pathlib import Path

from harpia_parser.batch.cache import BatchCache, exact_duplicate_plan


class RunBatchTest(unittest.TestCase):
    def test_hash_cache_reuses_unchanged_files_and_invalidates_changed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "a.pdf"
            cache = root / "cache" / "hashes.json"
            pdf.write_bytes(b"first")

            batch_cache = BatchCache(cache.parent, root, root)
            first, first_hits = batch_cache.file_hashes([pdf], 1)
            second, second_hits = batch_cache.file_hashes([pdf], 1)
            pdf.write_bytes(b"changed-content")
            third, third_hits = batch_cache.file_hashes([pdf], 1)

            self.assertEqual(first_hits, 0)
            self.assertEqual(second_hits, 1)
            self.assertEqual(third_hits, 0)
            self.assertEqual(first, second)
            self.assertNotEqual(first[str(pdf)], third[str(pdf)])

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

            hashes, _ = BatchCache(root / "cache", root, root).file_hashes(pdfs, workers=2)
            canonical, duplicates = exact_duplicate_plan(pdfs, hashes)

            self.assertEqual(canonical, [first, different])
            self.assertEqual(duplicates, {str(duplicate): first})


if __name__ == "__main__":
    unittest.main()
