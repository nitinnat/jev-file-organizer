from pathlib import Path
from types import SimpleNamespace

from jev_file_organizer.classifier import JevClassifier
from jev_file_organizer.discovery import DiscoveryCorpus, WordStat
from jev_file_organizer.folder_config import FolderGuidance
from jev_file_organizer.models import DecisionStatus, FileEvidence, FolderOption


class FakeDiscoveryClient:
    def __init__(self) -> None:
        self.state = None

    def system_one(self, state, questions):
        self.state = state
        probabilities = (0.91, 0.42)
        return SimpleNamespace(
            nouls={
                key: SimpleNamespace(noul=probabilities[index])
                for index, key in enumerate(questions)
            },
            request_id="request-123",
        )


def test_jev_discovery_receives_word_and_document_counts(tmp_path: Path) -> None:
    client = FakeDiscoveryClient()
    classifier = JevClassifier.__new__(JevClassifier)
    classifier._client = client
    evidence = [
        FileEvidence(tmp_path / "invoice.txt", "invoice payment", "markitdown")
    ]
    corpus = DiscoveryCorpus(
        words=(WordStat("invoice", 7, 3), WordStat("payment", 4, 2)),
        candidate_names=("Finance", "Travel"),
    )

    proposed = classifier.discover(
        tmp_path,
        evidence,
        corpus,
        FolderGuidance(context=("Business records",), rules=("Group invoices",)),
        threshold=0.7,
        min_files=2,
    )

    assert client.state["word_counts"] == [
        {"word": "invoice", "count": 7, "documents": 3},
        {"word": "payment", "count": 4, "documents": 2},
    ]
    assert client.state["candidate_folders"] == ["Finance", "Travel"]
    assert client.state["candidate_sources"] == []
    assert client.state["organization_rules"] == ["Group invoices"]
    assert [folder.path.name for folder in proposed] == ["Finance"]
    assert proposed[0].confidence == 0.91


class FakeClassificationClient:
    def system_one(self, state, questions):
        values = (
            {"folder_0": 0.18, "folder_1": 0.92}
            if state["file"]["filename"] == "invoice.pdf"
            else {"folder_0": 0.41, "folder_1": 0.24}
        )
        return SimpleNamespace(
            nouls={key: SimpleNamespace(noul=values[key]) for key in questions},
            request_id="classification-123",
        )


def test_jev_classification_uses_independent_folder_fit_probabilities(
    tmp_path: Path,
) -> None:
    classifier = JevClassifier.__new__(JevClassifier)
    classifier._client = FakeClassificationClient()
    evidence = [
        FileEvidence(tmp_path / "invoice.pdf", "invoice total", "markitdown"),
        FileEvidence(tmp_path / "notes.txt", "miscellaneous", "markitdown"),
    ]
    destinations = [
        FolderOption(tmp_path / "Travel"),
        FolderOption(tmp_path / "Finance"),
    ]

    decisions = classifier.classify(
        tmp_path,
        evidence,
        destinations,
        0.7,
        FolderGuidance(),
    )

    assert decisions[0].destination == tmp_path / "Finance" / "invoice.pdf"
    assert decisions[0].confidence == 0.92
    assert decisions[0].status == DecisionStatus.MOVE
    assert decisions[1].confidence == 0.41
    assert decisions[1].status == DecisionStatus.LOW_CONFIDENCE
