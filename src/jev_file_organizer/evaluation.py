import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import Decision, DecisionStatus


@dataclass(frozen=True)
class Metrics:
    total: int
    correct: int
    accuracy: float
    expected_moves: int
    predicted_moves: int
    correct_moves: int
    precision: float
    recall: float
    coverage: float
    abstention_rate: float
    latency_seconds: float


def load_manifest(path: Path) -> dict[str, str | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["expected"]


def evaluate(
    root: Path,
    decisions: list[Decision],
    expected: dict[str, str | None],
    latency_seconds: float,
) -> Metrics:
    predictions = {
        str(decision.source.relative_to(root)): (
            str(decision.destination.parent.relative_to(root))
            if decision.destination and decision.status == DecisionStatus.MOVE
            else None
        )
        for decision in decisions
    }
    correct = sum(
        predictions.get(source) == destination for source, destination in expected.items()
    )
    predicted_moves = sum(destination is not None for destination in predictions.values())
    expected_moves = sum(destination is not None for destination in expected.values())
    correct_moves = sum(
        predictions.get(source) == destination
        for source, destination in expected.items()
        if destination is not None
    )
    total = len(expected)
    return Metrics(
        total=total,
        correct=correct,
        accuracy=correct / total if total else 0.0,
        expected_moves=expected_moves,
        predicted_moves=predicted_moves,
        correct_moves=correct_moves,
        precision=correct_moves / predicted_moves if predicted_moves else 0.0,
        recall=correct_moves / expected_moves if expected_moves else 0.0,
        coverage=predicted_moves / total if total else 0.0,
        abstention_rate=(total - predicted_moves) / total if total else 0.0,
        latency_seconds=latency_seconds,
    )


def write_report(
    path: Path,
    root: Path,
    decisions: list[Decision],
    metrics: Metrics,
) -> None:
    path.write_text(
        json.dumps(
            {
                "metrics": asdict(metrics),
                "decisions": [decision.to_dict(root) for decision in decisions],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
