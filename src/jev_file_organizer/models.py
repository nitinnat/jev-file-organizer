from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path


class DecisionStatus(StrEnum):
    MOVE = "move"
    NO_MATCH = "no_match"
    LOW_CONFIDENCE = "low_confidence"
    COLLISION = "collision"
    MOVED = "moved"


@dataclass(frozen=True)
class FileEvidence:
    path: Path
    content: str
    extraction: str


@dataclass(frozen=True)
class FolderOption:
    path: Path
    description: str = ""
    proposed: bool = False


@dataclass(frozen=True)
class ProposedFolder:
    path: Path
    confidence: float
    supporting_files: tuple[Path, ...]
    request_id: str | None = None
    rationale: str = ""


@dataclass
class Decision:
    source: Path
    destination: Path | None
    choice: str
    confidence: float
    status: DecisionStatus
    extraction: str
    probabilities: dict[str, float] = field(default_factory=dict)
    request_id: str | None = None
    detail: str | None = None

    def to_dict(self, root: Path) -> dict[str, object]:
        data = asdict(self)
        data["source"] = str(self.source.relative_to(root))
        data["destination"] = (
            str(self.destination.relative_to(root)) if self.destination else None
        )
        data["status"] = self.status.value
        return data


@dataclass(frozen=True)
class FolderBatch:
    parent: Path
    files: tuple[Path, ...]
    destinations: tuple[Path, ...]
