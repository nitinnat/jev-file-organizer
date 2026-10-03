import hashlib
import json
import logging
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
from .scanner import child_folders, scan

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
    requested_folders: tuple[str, ...] = (),
) -> PlanningResult:
    started = time.perf_counter()
    all_proposed: list[ProposedFolder] = []
    outcomes: dict[Path, Decision] = {}
    source_order: list[Path] = []
    routes: dict[Path, list[str]] = {}
    try:
        batches = scan(
            root,
            include_hidden=include_hidden,
            include_without_destinations=discover_folders or bool(requested_folders),
        )
        pending: dict[Path, list[FileEvidence]] = {}
        destinations = {batch.parent: batch.destinations for batch in batches}
        for batch in batches:
            pending[batch.parent] = [extractor.extract(path) for path in batch.files]
            source_order.extend(batch.files)

        # claim: 2026-10-03-complete-hierarchical-routing
        while pending:
            parent = min(
                pending,
                key=lambda path: (len(path.relative_to(root).parts), str(path)),
            )
            evidence = pending.pop(parent)
            guidance = load_guidance(root, parent)
            # claim: 2026-09-23-explicit-folder-option
            requested = requested_folders if parent == root else ()
            child_paths = (
                destinations[parent]
                if parent in destinations
                else child_folders(parent, include_hidden)
            )
            existing = {path.name.casefold(): path for path in child_paths}
            destination_paths = (
                [existing[name.casefold()] for name in requested if name.casefold() in existing]
                if requested
                else list(child_paths)
            )
            options = [
                FolderOption(path=path, description=read_folder_config(path).description)
                for path in destination_paths
            ]
            proposed = []
            if requested and discover_folders and len(evidence) >= min_folder_files:
                proposed = [
                    ProposedFolder(
                        path=parent / name,
                        confidence=1.0,
                        supporting_files=(),
                        rationale="specified on command line",
                    )
                    for name in requested
                    if name.casefold() not in existing
                ]
                options.extend(
                    FolderOption(
                        path=folder.path,
                        description=folder.rationale,
                        proposed=True,
                    )
                    for folder in proposed
                )
            elif discover_folders and len(evidence) >= min_folder_files:
                corpus = build_corpus(evidence, child_paths, guidance.candidate_names)
                proposed = sorted(
                    classifier.discover(
                        parent,
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
                batch_decisions = classify_with_cache(
                    classifier,
                    extractor,
                    parent,
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
            evidence_by_source = {item.path: item for item in evidence}
            for decision in batch_decisions:
                previous = outcomes.get(decision.source)
                if decision.status != DecisionStatus.MOVE or decision.destination is None:
                    if previous is None:
                        outcomes[decision.source] = decision
                    continue

                hop_confidence = decision.confidence
                if previous is not None and previous.status == DecisionStatus.MOVE:
                    decision.confidence = min(previous.confidence, decision.confidence)
                outcomes[decision.source] = decision
                routes.setdefault(decision.source, []).append(
                    f"{decision.destination.parent.relative_to(root)} ({hop_confidence:.2f})"
                )

                next_parent = decision.destination.parent
                if next_parent.is_dir():
                    pending.setdefault(next_parent, []).append(
                        evidence_by_source[decision.source]
                    )

            extractor.flush()
    finally:
        extractor.flush()

    decisions = [outcomes[source] for source in source_order]
    for decision in decisions:
        if route := routes.get(decision.source):
            decision.detail = " → ".join(route)

    return PlanningResult(
        decisions=decisions,
        proposed_folders=all_proposed,
        latency_seconds=time.perf_counter() - started,
    )


# claim: 2026-10-03-stable-classification-cache
def classify_with_cache(
    classifier: Classifier,
    extractor: TextExtractor,
    parent: Path,
    evidence: list[FileEvidence],
    options: list[FolderOption],
    threshold: float,
    guidance: FolderGuidance,
) -> list[Decision]:
    namespace = getattr(classifier, "cache_namespace", None)
    if not namespace:
        return classifier.classify(parent, evidence, options, threshold, guidance)

    payload = {
        "classifier": namespace,
        "destinations": [
            {
                "name": option.path.name,
                "description": option.description,
                "proposed": option.proposed,
            }
            for option in options
        ],
        "context": guidance.context,
        "rules": guidance.rules,
        "threshold": threshold,
    }
    policy_key = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    decisions: dict[Path, Decision] = {}
    misses: list[FileEvidence] = []
    folder_ids = {f"folder_{index}": option for index, option in enumerate(options)}

    for item in evidence:
        record = extractor.cache.get_classification(item.path, policy_key)
        if record is None or record["choice"] not in folder_ids:
            misses.append(item)
            continue
        selected = folder_ids[record["choice"]]
        decisions[item.path] = Decision(
            source=item.path,
            destination=selected.path / item.path.name,
            choice=record["choice"],
            confidence=record["confidence"],
            status=(
                DecisionStatus.MOVE
                if record["confidence"] >= threshold
                else DecisionStatus.LOW_CONFIDENCE
            ),
            extraction=item.extraction,
            probabilities=record["probabilities"],
            request_id=record.get("request_id"),
        )

    fresh = classifier.classify(parent, misses, options, threshold, guidance) if misses else []
    for decision in fresh:
        extractor.cache.put_classification(
            decision.source,
            policy_key,
            {
                "choice": decision.choice,
                "confidence": decision.confidence,
                "probabilities": decision.probabilities,
                "request_id": decision.request_id,
            },
        )
        decisions[decision.source] = decision
    return [decisions[item.path] for item in evidence]


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
