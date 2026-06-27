import tempfile
import unittest
from pathlib import Path

from run_batch import _exact_duplicate_plan, _file_hashes


class RunBatchTest(unittest.TestCase):
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

            hashes = _file_hashes(pdfs, workers=2)
            canonical, duplicates = _exact_duplicate_plan(pdfs, hashes)

            self.assertEqual(canonical, [first, different])
            self.assertEqual(duplicates, {str(duplicate): first})


if __name__ == "__main__":
    unittest.main()
