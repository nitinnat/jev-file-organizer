import json
import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .models import Decision, DecisionStatus, ProposedFolder

logger = logging.getLogger(__name__)

PLAN_DIRECTORY = Path(".jfo/plans")


class PlanError(RuntimeError):
    pass


class PlanStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.directory = self.root / PLAN_DIRECTORY

    def create(
        self,
        decisions: list[Decision],
        proposed_folders: list[ProposedFolder],
        threshold: float,
        model: str,
        collision: str,
    ) -> str:
        resolve_collisions(decisions, collision)
        plan_id = f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
        document = {
            "version": 1,
            "id": plan_id,
            "status": "preview",
            "created_at": datetime.now(UTC).isoformat(),
            "root": str(self.root),
            "threshold": threshold,
            "model": model,
            "folders": [
                {
                    "path": self._relative(folder.path),
                    "confidence": folder.confidence,
                    "supporting_files": [
                        self._relative(path) for path in folder.supporting_files
                    ],
                    "request_id": folder.request_id,
                    "rationale": folder.rationale,
                }
                for folder in proposed_folders
            ],
            "decisions": [self._serialize_decision(decision) for decision in decisions],
        }
        self._write(document)
        self._prune()
        logger.info("[PLAN] created id=%s decisions=%d", plan_id, len(decisions))
        return plan_id

    def apply(self, plan_id: str) -> dict[str, object]:
        document = self.load(plan_id)
        if document["status"] != "preview":
            raise PlanError(f"plan {plan_id} is {document['status']}, not preview")
        folders = [self._resolve(item["path"]) for item in document["folders"]]
        moves = [
            item for item in document["decisions"] if item["status"] == DecisionStatus.MOVE
        ]
        self._validate_apply(folders, moves)

        created: list[Path] = []
        completed: list[tuple[Path, Path]] = []
        try:
            for folder in sorted(folders, key=lambda path: len(path.parts)):
                folder.mkdir()
                created.append(folder)
                logger.info("[PLAN_APPLY] created_folder path=%s", folder)
            for move in moves:
                source = self._resolve(move["source"])
                destination = self._resolve(move["destination"])
                shutil.move(source, destination)
                completed.append((source, destination))
                logger.info(
                    "[PLAN_APPLY] moved source=%s destination=%s", source, destination
                )
        except Exception:
            for source, destination in reversed(completed):
                if destination.exists() and not source.exists():
                    shutil.move(destination, source)
            for folder in reversed(created):
                if folder.exists() and not any(folder.iterdir()):
                    folder.rmdir()
            raise

        document["status"] = "applied"
        document["applied_at"] = datetime.now(UTC).isoformat()
        self._write(document)
        return {"moves": len(completed), "folders": len(created), "id": plan_id}

    def undo(self, plan_id: str | None = None) -> dict[str, object]:
        document = self.load(plan_id or self.latest("applied"))
        if document["status"] != "applied":
            raise PlanError(f"plan {document['id']} is {document['status']}, not applied")
        moves = [
            item for item in document["decisions"] if item["status"] == DecisionStatus.MOVE
        ]
        for move in moves:
            source = self._resolve(move["source"])
            destination = self._resolve(move["destination"])
            if source.exists():
                raise PlanError(f"cannot undo; original path now exists: {source}")
            if not destination.is_file():
                raise PlanError(f"cannot undo; moved file is missing: {destination}")
            if fingerprint(destination) != move["fingerprint"]:
                raise PlanError(f"cannot undo; moved file changed: {destination}")

        for move in reversed(moves):
            shutil.move(
                self._resolve(move["destination"]),
                self._resolve(move["source"]),
            )

        removed = 0
        folders = [self._resolve(item["path"]) for item in document["folders"]]
        for folder in sorted(folders, key=lambda path: len(path.parts), reverse=True):
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
                removed += 1

        document["status"] = "undone"
        document["undone_at"] = datetime.now(UTC).isoformat()
        self._write(document)
        return {"moves": len(moves), "folders": removed, "id": document["id"]}

    def load(self, plan_id: str) -> dict[str, object]:
        path = self.directory / f"{plan_id}.json"
        if not path.is_file():
            raise PlanError(f"plan not found: {plan_id}")
        document = json.loads(path.read_text(encoding="utf-8"))
        if Path(document["root"]).resolve() != self.root:
            raise PlanError("plan belongs to a different root folder")
        return document

    def latest(self, status: str) -> str:
        if not self.directory.exists():
            raise PlanError(f"no {status} plans found")
        matches = []
        for path in self.directory.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            if document.get("status") == status:
                matches.append((path.stat().st_mtime_ns, str(document["id"])))
        if not matches:
            raise PlanError(f"no {status} plans found")
        return max(matches)[1]

    def _validate_apply(
        self, folders: list[Path], moves: list[dict[str, object]]
    ) -> None:
        for folder in folders:
            if folder.exists():
                raise PlanError(f"plan is stale; proposed folder now exists: {folder}")
            if not folder.parent.is_dir():
                raise PlanError(f"plan is stale; parent folder is missing: {folder.parent}")
        planned_folders = set(folders)
        for move in moves:
            source = self._resolve(move["source"])
            destination = self._resolve(move["destination"])
            if not source.is_file():
                raise PlanError(f"plan is stale; source is missing: {source}")
            if fingerprint(source) != move["fingerprint"]:
                raise PlanError(f"plan is stale; source changed: {source}")
            if destination.exists():
                raise PlanError(f"plan is stale; destination exists: {destination}")
            if not destination.parent.is_dir() and destination.parent not in planned_folders:
                raise PlanError(
                    f"plan is stale; destination folder is missing: {destination.parent}"
                )

    def _serialize_decision(self, decision: Decision) -> dict[str, object]:
        return {
            "source": self._relative(decision.source),
            "destination": (
                self._relative(decision.destination) if decision.destination else None
            ),
            "choice": decision.choice,
            "confidence": decision.confidence,
            "status": decision.status.value,
            "extraction": decision.extraction,
            "probabilities": decision.probabilities,
            "request_id": decision.request_id,
            "detail": decision.detail,
            "fingerprint": fingerprint(decision.source),
        }

    def _relative(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.root))

    def _resolve(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise PlanError(f"plan path escapes root: {relative}")
        return path

    def _write(self, document: dict[str, object]) -> None:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.directory / f"{document['id']}.json"
        temporary = path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2)
        temporary.replace(path)

    def _prune(self, keep: int = 20) -> None:
        paths = sorted(
            self.directory.glob("*.json"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for path in paths[keep:]:
            document = json.loads(path.read_text(encoding="utf-8"))
            if document.get("status") != "applied":
                path.unlink()


def fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def resolve_collisions(decisions: list[Decision], collision: str) -> None:
    reserved: set[Path] = set()
    for decision in decisions:
        if decision.status != DecisionStatus.MOVE or decision.destination is None:
            continue
        destination = decision.destination
        if destination.exists() or destination in reserved:
            if collision == "skip":
                decision.status = DecisionStatus.COLLISION
                decision.detail = "destination already exists"
                continue
            counter = 1
            while destination.exists() or destination in reserved:
                destination = decision.destination.with_name(
                    f"{decision.destination.stem} ({counter}){decision.destination.suffix}"
                )
                counter += 1
            decision.destination = destination
        reserved.add(destination)
