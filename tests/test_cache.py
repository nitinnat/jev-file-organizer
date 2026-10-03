import json
from pathlib import Path

from jev_file_organizer.discovery import DiscoveryCorpus
from jev_file_organizer.extraction import TextExtractor, limit_pages
from jev_file_organizer.folder_config import FolderGuidance
from jev_file_organizer.models import Decision, DecisionStatus, FileEvidence, FolderOption
from jev_file_organizer.organizer import create_intelligent_plan


def test_cache_reuses_unchanged_extraction_and_invalidates_changes(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("initial notes", encoding="utf-8")
    first_extractor = TextExtractor()

    first = first_extractor.extract(path)
    first_extractor.flush()
    second_extractor = TextExtractor()
    cached = second_extractor.extract(path)

    assert first.extraction == "markitdown"
    assert cached.extraction == "cache:markitdown"
    assert second_extractor.cache.hits == 1

    path.write_text("changed notes with a different size", encoding="utf-8")
    refreshed = second_extractor.extract(path)

    assert refreshed.extraction == "markitdown"
    assert second_extractor.cache.misses == 1


def test_cache_rebuilds_when_json_has_the_wrong_shape(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("release notes", encoding="utf-8")
    (tmp_path / ".jfo-cache.json").write_text("[]", encoding="utf-8")

    extractor = TextExtractor()
    evidence = extractor.extract(path)
    extractor.flush()

    assert evidence.content == "release notes"
    assert evidence.extraction == "markitdown"


def test_cache_rebuilds_malformed_file_entry(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("release notes", encoding="utf-8")
    extractor = TextExtractor()
    (tmp_path / ".jfo-cache.json").write_text(
        json.dumps(
            {
                "version": 1,
                "entries": {
                    path.name: {"fingerprint": extractor.cache.fingerprint(path)},
                },
            }
        ),
        encoding="utf-8",
    )

    evidence = extractor.extract(path)

    assert evidence.content == "release notes"
    assert evidence.extraction == "markitdown"


def test_page_limit_uses_form_feed_boundaries() -> None:
    assert limit_pages("one\ftwo\fthree", 2) == "one\n\ntwo"


class VaryingClassifier:
    cache_namespace = "test:classification-v1"

    def __init__(self) -> None:
        self.calls = 0

    def discover(
        self,
        parent: Path,
        evidence: list[FileEvidence],
        corpus: DiscoveryCorpus,
        guidance: FolderGuidance,
        threshold: float,
        min_files: int,
    ) -> list:
        return []

    def classify(
        self,
        parent: Path,
        evidence: list[FileEvidence],
        destinations: list[FolderOption],
        threshold: float,
        guidance: FolderGuidance,
    ) -> list[Decision]:
        self.calls += 1
        confidence = 0.71 if self.calls == 1 else 0.69
        return [
            Decision(
                source=item.path,
                destination=destinations[0].path / item.path.name,
                choice="folder_0",
                confidence=confidence,
                status=(
                    DecisionStatus.MOVE
                    if confidence >= threshold
                    else DecisionStatus.LOW_CONFIDENCE
                ),
                extraction=item.extraction,
                probabilities={"folder_0": confidence},
                request_id=f"request-{self.calls}",
            )
            for item in evidence
        ]


def test_classification_cache_stabilizes_unchanged_decisions(tmp_path: Path) -> None:
    (tmp_path / "Finance").mkdir()
    source = tmp_path / "invoice.txt"
    source.write_text("invoice payment", encoding="utf-8")
    classifier = VaryingClassifier()

    first = create_intelligent_plan(tmp_path, classifier, TextExtractor(), 0.7)
    second_extractor = TextExtractor()
    second = create_intelligent_plan(tmp_path, classifier, second_extractor, 0.7)

    assert classifier.calls == 1
    assert first.decisions[0].status == DecisionStatus.MOVE
    assert second.decisions[0].status == DecisionStatus.MOVE
    assert second.decisions[0].confidence == 0.71
    assert second_extractor.cache.classification_hits == 1

    source.write_text("changed invoice payment", encoding="utf-8")
    third = create_intelligent_plan(tmp_path, classifier, TextExtractor(), 0.7)

    assert classifier.calls == 2
    assert third.decisions[0].status == DecisionStatus.LOW_CONFIDENCE
