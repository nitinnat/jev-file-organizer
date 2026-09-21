from pathlib import Path

import pytest

from jev_file_organizer.models import Decision, DecisionStatus, ProposedFolder
from jev_file_organizer.plans import PlanError, PlanStore


def decision_for(source: Path, destination: Path) -> Decision:
    return Decision(
        source=source,
        destination=destination,
        choice="folder_0",
        confidence=0.92,
        status=DecisionStatus.MOVE,
        extraction="markitdown",
    )


def test_plan_creates_moves_and_undoes_folder(tmp_path: Path) -> None:
    source = tmp_path / "invoice.txt"
    source.write_text("invoice", encoding="utf-8")
    folder = tmp_path / "Finance"
    decision = decision_for(source, folder / source.name)
    store = PlanStore(tmp_path)
    plan_id = store.create(
        [decision],
        [ProposedFolder(folder, 0.88, (source,))],
        threshold=0.7,
        model="jev-test",
        collision="skip",
    )

    applied = store.apply(plan_id)

    assert applied == {"moves": 1, "folders": 1, "id": plan_id}
    assert (folder / source.name).is_file()
    assert not source.exists()

    undone = store.undo(plan_id)

    assert undone == {"moves": 1, "folders": 1, "id": plan_id}
    assert source.is_file()
    assert not folder.exists()


def test_stale_plan_refuses_all_changes(tmp_path: Path) -> None:
    source = tmp_path / "report.txt"
    source.write_text("original", encoding="utf-8")
    folder = tmp_path / "Reports"
    store = PlanStore(tmp_path)
    plan_id = store.create(
        [decision_for(source, folder / source.name)],
        [ProposedFolder(folder, 0.9, (source,))],
        threshold=0.7,
        model="jev-test",
        collision="skip",
    )
    source.write_text("changed and longer", encoding="utf-8")

    with pytest.raises(PlanError, match="source changed"):
        store.apply(plan_id)

    assert source.is_file()
    assert not folder.exists()
