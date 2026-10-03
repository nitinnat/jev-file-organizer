from pathlib import Path

from jev_file_organizer.extraction import TextExtractor
from jev_file_organizer.folder_config import FolderGuidance
from jev_file_organizer.models import Decision, DecisionStatus, FileEvidence, FolderOption
from jev_file_organizer.organizer import apply_plan, create_plan


class KeywordClassifier:
    def classify(
        self,
        parent: Path,
        evidence: list[FileEvidence],
        destinations: list[FolderOption],
        threshold: float,
        guidance: FolderGuidance,
    ) -> list[Decision]:
        decisions = []
        for item in evidence:
            destination = next(
                (
                    option.path
                    for option in destinations
                    if option.path.name.lower() in item.content.lower()
                ),
                None,
            )
            confidence = 0.9 if destination else 0.8
            decisions.append(
                Decision(
                    source=item.path,
                    destination=destination / item.path.name if destination else None,
                    choice=destination.name if destination else "none",
                    confidence=confidence,
                    status=DecisionStatus.MOVE if destination else DecisionStatus.NO_MATCH,
                    extraction=item.extraction,
                )
            )
        return decisions


def test_recursive_plan_and_apply_uses_immediate_child_folders(tmp_path: Path) -> None:
    (tmp_path / "Work" / "Reports").mkdir(parents=True)
    (tmp_path / "Personal").mkdir()
    (tmp_path / "work-item.txt").write_text("Work planning", encoding="utf-8")
    (tmp_path / "Work" / "report.txt").write_text("Reports metrics", encoding="utf-8")
    (tmp_path / "unmatched.txt").write_text("No useful category", encoding="utf-8")

    decisions, _ = create_plan(tmp_path, KeywordClassifier(), TextExtractor(), 0.7)

    assert len(decisions) == 3
    assert sum(decision.status == DecisionStatus.MOVE for decision in decisions) == 2
    apply_plan(decisions)
    assert (tmp_path / "Work" / "work-item.txt").exists()
    assert (tmp_path / "Work" / "Reports" / "report.txt").exists()
    assert (tmp_path / "unmatched.txt").exists()


def test_plan_routes_file_through_complete_existing_hierarchy(tmp_path: Path) -> None:
    (tmp_path / "Finance" / "Taxes" / "2026").mkdir(parents=True)
    source = tmp_path / "invoice.txt"
    source.write_text("Finance Taxes 2026", encoding="utf-8")

    decisions, _ = create_plan(tmp_path, KeywordClassifier(), TextExtractor(), 0.7)

    assert len(decisions) == 1
    assert decisions[0].destination == tmp_path / "Finance" / "Taxes" / "2026" / source.name
    assert decisions[0].detail == (
        "Finance (0.90) → Finance/Taxes (0.90) → Finance/Taxes/2026 (0.90)"
    )

    apply_plan(decisions)
    assert (tmp_path / "Finance" / "Taxes" / "2026" / source.name).is_file()


def test_hierarchical_route_stops_at_last_approved_parent(tmp_path: Path) -> None:
    (tmp_path / "Finance" / "Taxes").mkdir(parents=True)
    source = tmp_path / "invoice.txt"
    source.write_text("Finance invoice", encoding="utf-8")

    decisions, _ = create_plan(tmp_path, KeywordClassifier(), TextExtractor(), 0.7)

    assert decisions[0].destination == tmp_path / "Finance" / source.name
    assert decisions[0].status == DecisionStatus.MOVE


def test_apply_skips_existing_destination(tmp_path: Path) -> None:
    destination_folder = tmp_path / "Receipts"
    destination_folder.mkdir()
    source = tmp_path / "invoice.txt"
    destination = destination_folder / source.name
    source.write_text("new", encoding="utf-8")
    destination.write_text("existing", encoding="utf-8")
    decision = Decision(
        source=source,
        destination=destination,
        choice="Receipts",
        confidence=0.95,
        status=DecisionStatus.MOVE,
        extraction="markitdown",
    )

    apply_plan([decision])

    assert decision.status == DecisionStatus.COLLISION
    assert source.exists()
    assert destination.read_text(encoding="utf-8") == "existing"
