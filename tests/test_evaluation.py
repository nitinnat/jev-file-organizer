import json
from pathlib import Path

import pytest

from jev_file_organizer.evaluation import analyze, evaluate, write_report
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


def test_analysis_calibrates_thresholds_and_confidence_bands(tmp_path: Path) -> None:
    reports = tmp_path / "Reports"
    reports.mkdir()
    strong = tmp_path / "strong.csv"
    marginal = tmp_path / "marginal.txt"
    strong.write_text("report", encoding="utf-8")
    marginal.write_text("report", encoding="utf-8")
    decisions = [
        Decision(
            strong,
            reports / strong.name,
            "folder_0",
            0.93,
            DecisionStatus.MOVE,
            "markitdown",
        ),
        Decision(
            marginal,
            reports / marginal.name,
            "folder_0",
            0.74,
            DecisionStatus.MOVE,
            "markitdown",
        ),
    ]
    expected = {"strong.csv": "Reports", "marginal.txt": None}

    analysis = analyze(
        tmp_path,
        decisions,
        expected,
        (0.7, 0.8, 0.95),
        selected_threshold=0.8,
        target_precision=1.0,
    )

    assert analysis.thresholds["0.70"].precision == 0.5
    assert analysis.thresholds["0.80"].precision == 1.0
    assert analysis.recommended_threshold == 0.8
    assert analysis.actions == {
        "correct_move": 1,
        "wrong_move": 0,
        "correct_abstention": 1,
        "wrong_abstention": 0,
    }
    assert analysis.by_extension[".csv"].accuracy == 1.0
    marginal_band = next(
        band for band in analysis.confidence_bands if band.label == "0.70–0.80"
    )
    assert marginal_band.accuracy == 0

    report = tmp_path / "report.json"
    metrics = evaluate(tmp_path, decisions, expected, 1.25, 0.8)
    write_report(report, tmp_path, decisions, metrics, analysis)
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["analysis"]["recommended_threshold"] == 0.8
    assert payload["analysis"]["actions"]["correct_abstention"] == 1


def test_analysis_rejects_incomplete_manifest(tmp_path: Path) -> None:
    reports = tmp_path / "Reports"
    reports.mkdir()
    source = tmp_path / "unlabeled.txt"
    source.write_text("report", encoding="utf-8")
    decisions = [
        Decision(
            source,
            reports / source.name,
            "folder_0",
            0.9,
            DecisionStatus.MOVE,
            "markitdown",
        )
    ]

    with pytest.raises(ValueError, match="unlabeled"):
        analyze(tmp_path, decisions, {}, (0.7,), 0.7, 0.95)
