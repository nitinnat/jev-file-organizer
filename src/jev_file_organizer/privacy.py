import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_EXCLUDES = (
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_ed25519",
)


@dataclass(frozen=True)
class PrivacyPolicy:
    exclude_patterns: tuple[str, ...] = DEFAULT_EXCLUDES
    redact_patterns: tuple[str, ...] = ()
    _redactions: tuple[re.Pattern[str], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            compiled = tuple(re.compile(pattern) for pattern in self.redact_patterns)
        except re.error as error:
            raise ValueError(f"invalid privacy redaction pattern: {error}") from error
        object.__setattr__(self, "_redactions", compiled)

    def excludes(self, root: Path, path: Path) -> bool:
        relative = path.relative_to(root)
        return any(
            relative.match(pattern) or path.name == pattern for pattern in self.exclude_patterns
        )

    # claim: 2026-10-03-redact-before-cache-and-boundary
    def redact(self, value: str) -> str:
        for pattern in self._redactions:
            value = pattern.sub("[REDACTED]", value)
        return value

    def sanitize(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.sanitize(item) for item in value)
        if isinstance(value, dict):
            return {key: self.sanitize(item) for key, item in value.items()}
        return value

    @property
    def cache_key(self) -> str:
        payload = json.dumps(
            {"exclude": self.exclude_patterns, "redact": self.redact_patterns},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
