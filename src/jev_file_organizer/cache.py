import json
import os
from pathlib import Path
from typing import TypedDict

from .models import FileEvidence

# claim: 2026-09-20-lightweight-local-metadata
CACHE_NAME = ".jfo-cache.json"
CACHE_VERSION = 1


class CacheDocument(TypedDict):
    version: int
    entries: dict[str, object]


class ExtractionCache:
    def __init__(
        self,
        enabled: bool = True,
        refresh: bool = False,
        max_pages: int = 5,
        max_chars: int = 12_000,
    ) -> None:
        self.enabled = enabled
        self.refresh = refresh
        self.max_pages = max_pages
        self.max_chars = max_chars
        self.hits = 0
        self.misses = 0
        self._documents: dict[Path, CacheDocument] = {}
        self._changed: set[Path] = set()

    def get(self, path: Path) -> FileEvidence | None:
        if not self.enabled or self.refresh:
            self.misses += 1
            return None
        entry = self._entries(path.parent).get(path.name)
        if (
            not isinstance(entry, dict)
            or entry.get("fingerprint") != self.fingerprint(path)
            or not isinstance(entry.get("content"), str)
            or not isinstance(entry.get("extraction"), str)
        ):
            self.misses += 1
            return None
        self.hits += 1
        return FileEvidence(
            path=path,
            content=entry["content"],
            extraction=f"cache:{entry['extraction']}",
        )

    def put(self, evidence: FileEvidence) -> None:
        if not self.enabled:
            return
        self._entries(evidence.path.parent)[evidence.path.name] = {
            "fingerprint": self.fingerprint(evidence.path),
            "content": evidence.content,
            "extraction": evidence.extraction.removeprefix("cache:"),
        }
        self._changed.add(evidence.path.parent)

    def flush(self) -> None:
        for folder in self._changed:
            document = self._documents[folder]
            entries = document["entries"]
            document["entries"] = {
                name: entry for name, entry in entries.items() if (folder / name).is_file()
            }
            path = folder / CACHE_NAME
            temporary = folder / f"{CACHE_NAME}.tmp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(document, stream, ensure_ascii=False, separators=(",", ":"))
            temporary.replace(path)
        self._changed.clear()

    def fingerprint(self, path: Path) -> str:
        stat = path.stat()
        return (
            f"v{CACHE_VERSION}:{stat.st_size}:{stat.st_mtime_ns}:"
            f"{self.max_pages}:{self.max_chars}"
        )

    def _entries(self, folder: Path) -> dict[str, object]:
        if folder not in self._documents:
            path = folder / CACHE_NAME
            if path.exists():
                try:
                    document = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    document = None
            else:
                document = None
            if (
                not isinstance(document, dict)
                or document.get("version") != CACHE_VERSION
                or not isinstance(document.get("entries"), dict)
            ):
                self._documents[folder] = {"version": CACHE_VERSION, "entries": {}}
            else:
                self._documents[folder] = {
                    "version": CACHE_VERSION,
                    "entries": document["entries"],
                }
        return self._documents[folder]["entries"]
