from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import pickle

import pandas as pd

from ..audit.duplicate_audit import file_sha256
from ..core.outputs import PipelineOutputs


class BatchCache:
    def __init__(self, cache_dir: Path, project_root: Path, source_root: Path):
        self.cache_dir = cache_dir
        self.project_root = project_root
        self.source_root = source_root

    def file_hashes(self, pdfs: list[Path], workers: int) -> tuple[dict[str, str], int, dict[str, str]]:
        cache_path = self.cache_dir / "file_hashes.json"
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            cache = {}
        hashes: dict[str, str] = {}
        pending: list[Path] = []
        refreshed: dict[str, dict] = {}
        failures: dict[str, str] = {}
        cache_hits = 0
        for path in pdfs:
            key = str(path)
            try:
                stat = path.stat()
            except OSError as exc:
                failures[key] = f"{type(exc).__name__}: {exc}"
                continue
            cached = cache.get(key, {})
            if cached.get("size") == stat.st_size and cached.get("mtime_ns") == stat.st_mtime_ns and cached.get("sha256"):
                hashes[key] = str(cached["sha256"])
                cache_hits += 1
            else:
                pending.append(path)
            refreshed[key] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        if pending:
            def safe_hash(path: Path) -> tuple[Path, str | None, str | None]:
                try:
                    return path, file_sha256(path), None
                except OSError as exc:
                    return path, None, f"{type(exc).__name__}: {exc}"

            with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                hash_results = list(executor.map(safe_hash, pending))
            for path, digest, error in hash_results:
                key = str(path)
                if digest is not None:
                    hashes[key] = digest
                else:
                    failures[key] = error or "Falha desconhecida ao calcular hash."
                    refreshed.pop(key, None)
        for key, metadata in refreshed.items():
            metadata["sha256"] = hashes[key]
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(refreshed, ensure_ascii=False), encoding="utf-8")
        temporary.replace(cache_path)
        return hashes, cache_hits, failures

    def runtime_signature(self, taxonomy_path: Path, runner_path: Path) -> str:
        digest = hashlib.sha256()
        digest.update(b"extraction-cache-v2")
        for path in self._extraction_source_paths():
            relative = path.relative_to(self.project_root) if path.is_relative_to(self.project_root) else path
            digest.update(str(relative).encode("utf-8"))
            digest.update(path.read_bytes())
        digest.update(self._taxonomy_extraction_payload(taxonomy_path))
        return digest.hexdigest()

    def _extraction_source_paths(self) -> list[Path]:
        package = self.source_root / "harpia_parser"
        paths: set[Path] = set()
        for directory in ["config", "core", "extraction", "normalization", "parsing"]:
            paths.update((package / directory).rglob("*.py"))
        paths.update([
            package / "constants.py",
            package / "utils.py",
            package / "batch" / "discovery.py",
            package / "formatting" / "common.py",
            package / "formatting" / "laudo_agua.py",
            package / "formatting" / "laudo_fito.py",
            package / "formatting" / "laudo_sedimento.py",
        ])
        return sorted(path for path in paths if path.exists())

    @staticmethod
    def _taxonomy_extraction_payload(taxonomy_path: Path) -> bytes:
        frames = pd.read_excel(
            taxonomy_path,
            sheet_name=["item_taxonomia", "template", "item_template"],
            dtype=object,
        )
        digest = hashlib.sha256()
        for sheet_name in ["item_taxonomia", "template", "item_template"]:
            frame = frames[sheet_name].copy()
            frame.columns = frame.columns.map(str)
            frame = frame.reindex(sorted(frame.columns), axis=1)
            if "id" in frame.columns:
                frame = frame.sort_values("id", key=lambda values: values.astype(str), kind="stable")
            payload = frame.fillna("").astype(str).to_json(
                orient="split",
                force_ascii=False,
                index=False,
            )
            digest.update(sheet_name.encode("utf-8"))
            digest.update(payload.encode("utf-8"))
        return digest.digest()

    def load_extraction(self, signature: str, file_hash: str) -> tuple[str, PipelineOutputs] | None:
        path = self._extraction_path(signature, file_hash)
        if not path.exists():
            return None
        with gzip.open(path, "rb") as handle:
            return pickle.load(handle)

    def save_extraction(self, signature: str, file_hash: str, text: str, outputs: PipelineOutputs) -> None:
        path = self._extraction_path(signature, file_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        with gzip.open(temporary, "wb", compresslevel=3) as handle:
            pickle.dump((text, outputs), handle, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(path)

    def _extraction_path(self, signature: str, file_hash: str) -> Path:
        return self.cache_dir / "extractions" / signature / f"{file_hash}.pkl.gz"


def exact_duplicate_plan(pdfs: list[Path], file_hashes: dict[str, str]) -> tuple[list[Path], dict[str, Path]]:
    groups: dict[str, list[Path]] = {}
    for pdf in pdfs:
        groups.setdefault(file_hashes[str(pdf)], []).append(pdf)
    canonical_paths: list[Path] = []
    duplicate_to_canonical: dict[str, Path] = {}
    for group in groups.values():
        ordered = sorted(group, key=lambda path: str(path).lower())
        canonical_paths.append(ordered[0])
        for duplicate in ordered[1:]:
            duplicate_to_canonical[str(duplicate)] = ordered[0]
    return sorted(canonical_paths, key=lambda path: str(path).lower()), duplicate_to_canonical
