from pathlib import Path

from jev_file_organizer.evaluation import evaluate
from jev_file_organizer.models import Decision, DecisionStatus


def test_evaluation_counts_abstentions_and_moves(tmp_path: Path) -> None:
    reports = tmp_path / "Reports"
    reports.mkdir()
    moved = tmp_path / "metrics.csv"
    skipped = tmp_path / "mystery.bin"
    decisions = [
        Decision(
            moved,
            reports / moved.name,
            "folder_0",
            0.9,
            DecisionStatus.MOVE,
            "markitdown",
        ),
        Decision(
            skipped,
            None,
            "none",
            0.8,
            DecisionStatus.NO_MATCH,
            "filename_unsupported",
        ),
    ]

    metrics = evaluate(
        tmp_path,
        decisions,
        {"metrics.csv": "Reports", "mystery.bin": None},
        1.25,
    )

    assert metrics.accuracy == 1
    assert metrics.precision == 1
    assert metrics.recall == 1
    assert metrics.coverage == 0.5
    assert metrics.abstention_rate == 0.5
