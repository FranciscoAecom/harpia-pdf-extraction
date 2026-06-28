from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import pickle

from ..audit.duplicate_audit import file_sha256
from ..core.outputs import PipelineOutputs


class BatchCache:
    def __init__(self, cache_dir: Path, project_root: Path, source_root: Path):
        self.cache_dir = cache_dir
        self.project_root = project_root
        self.source_root = source_root

    def file_hashes(self, pdfs: list[Path], workers: int) -> tuple[dict[str, str], int]:
        cache_path = self.cache_dir / "file_hashes.json"
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            cache = {}
        hashes: dict[str, str] = {}
        pending: list[Path] = []
        refreshed: dict[str, dict] = {}
        for path in pdfs:
            key = str(path)
            stat = path.stat()
            cached = cache.get(key, {})
            if cached.get("size") == stat.st_size and cached.get("mtime_ns") == stat.st_mtime_ns and cached.get("sha256"):
                hashes[key] = str(cached["sha256"])
            else:
                pending.append(path)
            refreshed[key] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
        if pending:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                pending_hashes = list(executor.map(file_sha256, pending))
            hashes.update({str(path): pending_hashes[index] for index, path in enumerate(pending)})
        for key, metadata in refreshed.items():
            metadata["sha256"] = hashes[key]
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(refreshed, ensure_ascii=False), encoding="utf-8")
        temporary.replace(cache_path)
        return hashes, len(pdfs) - len(pending)

    def runtime_signature(self, taxonomy_path: Path, runner_path: Path) -> str:
        digest = hashlib.sha256()
        paths = [taxonomy_path, *sorted(self.source_root.rglob("*.py")), runner_path]
        for path in paths:
            relative = path.relative_to(self.project_root) if path.is_relative_to(self.project_root) else path
            digest.update(str(relative).encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()

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

