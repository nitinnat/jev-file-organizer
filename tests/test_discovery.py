from pathlib import Path

from jev_file_organizer.discovery import DiscoveryCorpus, build_corpus
from jev_file_organizer.extraction import TextExtractor
from jev_file_organizer.folder_config import FolderGuidance
from jev_file_organizer.models import (
    Decision,
    DecisionStatus,
    FileEvidence,
    FolderOption,
    ProposedFolder,
)
from jev_file_organizer.organizer import create_intelligent_plan


def test_corpus_sends_counts_and_builds_candidate_names(tmp_path: Path) -> None:
    evidence = [
        FileEvidence(
            tmp_path / "vendor-invoice.txt",
            "invoice payment vendor invoice total",
            "markitdown",
        ),
        FileEvidence(
            tmp_path / "software-invoice.txt",
            "software invoice payment total",
            "markitdown",
        ),
    ]

    corpus = build_corpus(
        evidence,
        existing_folders=(),
        configured_names=("Vendor Bills",),
    )

    invoice = next(stat for stat in corpus.words if stat.word == "invoice")
    assert invoice.count == 3
    assert invoice.documents == 2
    assert corpus.candidate_names[0] == "Vendor Bills"
    assert "Invoices" in corpus.candidate_names
    assert "Finance" in corpus.candidate_names
    assert "Receipts" in corpus.candidate_names


def test_candidate_names_prefer_repeated_groups_and_supported_file_types(
    tmp_path: Path,
) -> None:
    evidence = [
        FileEvidence(tmp_path / "Screenshot 1.png", "Screenshot 1.png", "markitdown"),
        FileEvidence(tmp_path / "Screenshot 2.png", "Screenshot 2.png", "markitdown"),
        FileEvidence(tmp_path / "tool-one.dmg", "tool-one.dmg", "filename_unsupported"),
        FileEvidence(tmp_path / "tool-two.dmg", "tool-two.dmg", "filename_unsupported"),
    ]

    corpus = build_corpus(evidence, existing_folders=())

    assert "Screenshots" in corpus.candidate_names
    assert "Software Installers" in corpus.candidate_names
    assert "Screenshot" not in corpus.candidate_names
    index = corpus.candidate_names.index("Software Installers")
    assert corpus.candidate_reasons[index] == "2 .dmg"


def test_existing_folder_names_are_not_proposed(tmp_path: Path) -> None:
    corpus = build_corpus(
        [FileEvidence(tmp_path / "invoice.txt", "invoice payment", "markitdown")],
        existing_folders=(tmp_path / "Finance",),
    )

    assert "Finance" not in corpus.candidate_names


class DiscoveryClassifier:
    def discover(
        self,
        parent: Path,
        evidence: list[FileEvidence],
        corpus: DiscoveryCorpus,
        guidance: FolderGuidance,
        threshold: float,
        min_files: int,
    ) -> list[ProposedFolder]:
        return [ProposedFolder(parent / "Finance", 0.91, (), "discovery-request")]

    def classify(
        self,
        parent: Path,
        evidence: list[FileEvidence],
        destinations: list[FolderOption],
        threshold: float,
        guidance: FolderGuidance,
    ) -> list[Decision]:
        finance = next(option.path for option in destinations if option.path.name == "Finance")
        return [
            Decision(
                source=item.path,
                destination=finance / item.path.name,
                choice="folder_0",
                confidence=0.9,
                status=DecisionStatus.MOVE,
                extraction=item.extraction,
            )
            for item in evidence
        ]


def test_discovery_requires_validation_and_file_support(tmp_path: Path) -> None:
    (tmp_path / "invoice-one.txt").write_text("invoice payment", encoding="utf-8")
    (tmp_path / "invoice-two.txt").write_text("invoice total", encoding="utf-8")

    result = create_intelligent_plan(
        tmp_path,
        DiscoveryClassifier(),
        TextExtractor(cache_enabled=False),
        threshold=0.7,
        discover_folders=True,
        min_folder_files=2,
    )

    assert len(result.proposed_folders) == 1
    assert result.proposed_folders[0].path == tmp_path / "Finance"
    assert len(result.proposed_folders[0].supporting_files) == 2
    assert all(decision.status == DecisionStatus.MOVE for decision in result.decisions)
