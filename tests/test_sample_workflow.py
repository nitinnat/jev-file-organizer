import json
import runpy
from pathlib import Path

from jev_file_organizer.evaluation import evaluate
from jev_file_organizer.extraction import TextExtractor
from jev_file_organizer.folder_config import FolderGuidance
from jev_file_organizer.models import Decision, DecisionStatus, FileEvidence, FolderOption
from jev_file_organizer.organizer import create_plan

EXPECTED_FOLDERS = {
    "quarterly-business-review.txt": "Work",
    "vaccination-record.txt": "Personal",
    "vendor-agreement.md": "Contracts",
    "q3-metrics.csv": "Reports",
    "flight-itinerary.html": "Travel",
    "lab-results.json": "Medical",
}


class LabeledSampleClassifier:
    def classify(
        self,
        parent: Path,
        evidence: list[FileEvidence],
        destinations: list[FolderOption],
        threshold: float,
        guidance: FolderGuidance,
    ) -> list[Decision]:
        destination_by_name = {option.path.name: option.path for option in destinations}
        decisions = []
        for item in evidence:
            destination = destination_by_name.get(EXPECTED_FOLDERS.get(item.path.name, ""))
            decisions.append(
                Decision(
                    source=item.path,
                    destination=destination / item.path.name if destination else None,
                    choice=destination.name if destination else "none",
                    confidence=0.95,
                    status=DecisionStatus.MOVE if destination else DecisionStatus.NO_MATCH,
                    extraction=item.extraction,
                )
            )
        return decisions


def test_generated_sample_extraction_traversal_and_evaluation(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runpy.run_path(
        Path(__file__).parents[1] / "scripts" / "generate_sample.py",
        run_name="__main__",
    )
    root = tmp_path / "sample-folder"
    expected = json.loads(
        (tmp_path / "sample-manifest.json").read_text(encoding="utf-8")
    )["expected"]

    decisions, latency = create_plan(root, LabeledSampleClassifier(), TextExtractor(), 0.7)
    metrics = evaluate(root, decisions, expected, latency)

    assert len(decisions) == 7
    assert {decision.extraction for decision in decisions} >= {
        "markitdown",
        "filename_unsupported",
    }
    assert metrics.accuracy == 1
    assert metrics.precision == 1
    assert metrics.recall == 1
