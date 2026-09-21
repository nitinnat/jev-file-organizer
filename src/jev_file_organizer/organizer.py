import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .discovery import DiscoveryCorpus, build_corpus
from .extraction import TextExtractor
from .folder_config import FolderGuidance, load_guidance, read_folder_config
from .models import (
    Decision,
    DecisionStatus,
    FileEvidence,
    FolderOption,
    ProposedFolder,
)
from .scanner import scan

logger = logging.getLogger(__name__)


class Classifier(Protocol):
    def classify(
        self,
        parent: Path,
        evidence: list[FileEvidence],
        destinations: list[FolderOption],
        threshold: float,
        guidance: FolderGuidance,
    ) -> list[Decision]: ...

    def discover(
        self,
        parent: Path,
        evidence: list[FileEvidence],
        corpus: DiscoveryCorpus,
        guidance: FolderGuidance,
        threshold: float,
        min_files: int,
    ) -> list[ProposedFolder]: ...


@dataclass(frozen=True)
class PlanningResult:
    decisions: list[Decision]
    proposed_folders: list[ProposedFolder]
    latency_seconds: float


def create_plan(
    root: Path,
    classifier: Classifier,
    extractor: TextExtractor,
    threshold: float,
    include_hidden: bool = False,
) -> tuple[list[Decision], float]:
    result = create_intelligent_plan(
        root,
        classifier,
        extractor,
        threshold,
        include_hidden=include_hidden,
    )
    return result.decisions, result.latency_seconds


def create_intelligent_plan(
    root: Path,
    classifier: Classifier,
    extractor: TextExtractor,
    threshold: float,
    include_hidden: bool = False,
    discover_folders: bool = False,
    max_new_folders: int = 5,
    min_folder_files: int = 2,
) -> PlanningResult:
    started = time.perf_counter()
    decisions: list[Decision] = []
    all_proposed: list[ProposedFolder] = []
    try:
        batches = scan(
            root,
            include_hidden=include_hidden,
            include_without_destinations=discover_folders,
        )
        for batch in batches:
            evidence = [extractor.extract(path) for path in batch.files]
            guidance = load_guidance(root, batch.parent)
            options = [
                FolderOption(
                    path=path,
                    description=read_folder_config(path).description,
                )
                for path in batch.destinations
            ]
            proposed = []
            if discover_folders and len(evidence) >= min_folder_files:
                corpus = build_corpus(
                    evidence,
                    batch.destinations,
                    guidance.candidate_names,
                )
                proposed = sorted(
                    classifier.discover(
                        batch.parent,
                        evidence,
                        corpus,
                        guidance,
                        threshold,
                        min_folder_files,
                    ),
                    key=lambda folder: folder.confidence,
                    reverse=True,
                )[:max_new_folders]
                options.extend(
                    FolderOption(
                        path=folder.path,
                        description=folder.rationale,
                        proposed=True,
                    )
                    for folder in proposed
                )

            if options:
                batch_decisions = classifier.classify(
                    batch.parent,
                    evidence,
                    options,
                    threshold,
                    guidance,
                )
            else:
                batch_decisions = [
                    Decision(
                        source=item.path,
                        destination=None,
                        choice="none",
                        confidence=1.0,
                        status=DecisionStatus.NO_MATCH,
                        extraction=item.extraction,
                        detail="no existing or proposed destination folders",
                    )
                    for item in evidence
                ]

            supported = support_proposed_folders(
                proposed,
                batch_decisions,
                min_folder_files,
            )
            all_proposed.extend(supported)
            decisions.extend(batch_decisions)
            extractor.flush()
    finally:
        extractor.flush()

    return PlanningResult(
        decisions=decisions,
        proposed_folders=all_proposed,
        latency_seconds=time.perf_counter() - started,
    )


def support_proposed_folders(
    proposed: list[ProposedFolder],
    decisions: list[Decision],
    min_folder_files: int,
) -> list[ProposedFolder]:
    supported = []
    for folder in proposed:
        matches = tuple(
            decision.source
            for decision in decisions
            if decision.status == DecisionStatus.MOVE
            and decision.destination
            and decision.destination.parent == folder.path
        )
        if len(matches) >= min_folder_files:
            supported.append(
                ProposedFolder(
                    path=folder.path,
                    confidence=folder.confidence,
                    supporting_files=matches,
                    request_id=folder.request_id,
                    rationale=folder.rationale,
                )
            )
            continue
        for decision in decisions:
            if decision.destination and decision.destination.parent == folder.path:
                decision.destination = None
                decision.status = DecisionStatus.NO_MATCH
                decision.detail = (
                    f"proposed folder needs at least {min_folder_files} matching files"
                )
    return supported


def apply_plan(decisions: list[Decision], collision: str = "skip") -> None:
    logger.info("[APPLY] start candidates=%d collision=%s", len(decisions), collision)
    for decision in decisions:
        if decision.status != DecisionStatus.MOVE or decision.destination is None:
            continue
        destination = decision.destination
        if destination.exists():
            if collision == "skip":
                decision.status = DecisionStatus.COLLISION
                decision.detail = "destination already exists"
                logger.warning(
                    "[APPLY] collision source=%s destination=%s", decision.source, destination
                )
                continue
            destination = available_destination(destination)
            decision.destination = destination

        logger.info("[APPLY] move source=%s destination=%s", decision.source, destination)
        shutil.move(decision.source, destination)
        decision.status = DecisionStatus.MOVED
    logger.info(
        "[APPLY] complete moved=%d collisions=%d",
        sum(decision.status == DecisionStatus.MOVED for decision in decisions),
        sum(decision.status == DecisionStatus.COLLISION for decision in decisions),
    )


def available_destination(path: Path) -> Path:
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
