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


@dataclass(frozen=True)
class ConfidenceBand:
    label: str
    total: int
    correct: int
    accuracy: float
    mean_confidence: float


@dataclass(frozen=True)
class EvaluationAnalysis:
    thresholds: dict[str, Metrics]
    recommended_threshold: float | None
    target_precision: float
    by_extension: dict[str, Metrics]
    confidence_bands: list[ConfidenceBand]
    actions: dict[str, int]


def load_manifest(path: Path) -> dict[str, str | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["expected"]


def evaluate(
    root: Path,
    decisions: list[Decision],
    expected: dict[str, str | None],
    latency_seconds: float,
    threshold: float | None = None,
) -> Metrics:
    predictions = {
        str(decision.source.relative_to(root)): prediction(decision, root, threshold)
        for decision in decisions
        if str(decision.source.relative_to(root)) in expected
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


# claim: 2026-10-04-single-run-threshold-calibration
def analyze(
    root: Path,
    decisions: list[Decision],
    expected: dict[str, str | None],
    thresholds: tuple[float, ...],
    selected_threshold: float,
    target_precision: float,
) -> EvaluationAnalysis:
    validate_manifest(root, decisions, expected)
    curves = {
        f"{threshold:.2f}": evaluate(root, decisions, expected, 0.0, threshold)
        for threshold in thresholds
    }
    eligible = [
        (threshold, metrics)
        for threshold, metrics in ((float(key), value) for key, value in curves.items())
        if metrics.predicted_moves and metrics.precision >= target_precision
    ]
    recommended = (
        max(eligible, key=lambda item: (item[1].recall, item[1].coverage, -item[0]))[0]
        if eligible
        else None
    )
    extensions = sorted({Path(source).suffix.casefold() or "[no extension]" for source in expected})
    by_extension = {}
    for extension in extensions:
        subset = {
            source: destination
            for source, destination in expected.items()
            if (Path(source).suffix.casefold() or "[no extension]") == extension
        }
        by_extension[extension] = evaluate(
            root, decisions, subset, 0.0, selected_threshold
        )
    return EvaluationAnalysis(
        thresholds=curves,
        recommended_threshold=recommended,
        target_precision=target_precision,
        by_extension=by_extension,
        confidence_bands=build_confidence_bands(root, decisions, expected),
        actions=action_counts(root, decisions, expected, selected_threshold),
    )


def prediction(decision: Decision, root: Path, threshold: float | None) -> str | None:
    accepted = (
        decision.status in {DecisionStatus.MOVE, DecisionStatus.MOVED}
        if threshold is None
        else decision.destination is not None and decision.confidence >= threshold
    )
    return str(decision.destination.parent.relative_to(root)) if accepted else None


def validate_manifest(
    root: Path,
    decisions: list[Decision],
    expected: dict[str, str | None],
) -> None:
    for source, destination in expected.items():
        relative = Path(source)
        if relative.is_absolute() or ".." in relative.parts or not (root / relative).is_file():
            raise ValueError(f"manifest source is missing or unsafe: {source}")
        if destination is not None and not (root / destination).is_dir():
            raise ValueError(f"manifest destination is missing: {destination}")
    actual = {str(decision.source.relative_to(root)) for decision in decisions}
    extra = sorted(actual - expected.keys())
    missing = sorted(expected.keys() - actual)
    if extra or missing:
        details = []
        if extra:
            details.append(f"unlabeled={extra}")
        if missing:
            details.append(f"not_scanned={missing}")
        raise ValueError("manifest does not match the evaluated files: " + ", ".join(details))


def action_counts(
    root: Path,
    decisions: list[Decision],
    expected: dict[str, str | None],
    threshold: float,
) -> dict[str, int]:
    counts = {
        "correct_move": 0,
        "wrong_move": 0,
        "correct_abstention": 0,
        "wrong_abstention": 0,
    }
    for decision in decisions:
        source = str(decision.source.relative_to(root))
        predicted = prediction(decision, root, threshold)
        wanted = expected[source]
        if predicted is None:
            key = "correct_abstention" if wanted is None else "wrong_abstention"
        else:
            key = "correct_move" if predicted == wanted else "wrong_move"
        counts[key] += 1
    return counts


def build_confidence_bands(
    root: Path,
    decisions: list[Decision],
    expected: dict[str, str | None],
) -> list[ConfidenceBand]:
    bands = ((0.0, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01))
    results = []
    for lower, upper in bands:
        members = [
            decision
            for decision in decisions
            if decision.destination is not None and lower <= decision.confidence < upper
        ]
        correct = sum(
            prediction(decision, root, 0.0)
            == expected[str(decision.source.relative_to(root))]
            for decision in members
        )
        results.append(
            ConfidenceBand(
                label=f"{lower:.2f}–{min(upper, 1.0):.2f}",
                total=len(members),
                correct=correct,
                accuracy=correct / len(members) if members else 0.0,
                mean_confidence=(
                    sum(decision.confidence for decision in members) / len(members)
                    if members
                    else 0.0
                ),
            )
        )
    return results


def write_report(
    path: Path,
    root: Path,
    decisions: list[Decision],
    metrics: Metrics,
    analysis: EvaluationAnalysis | None = None,
) -> None:
    path.write_text(
        json.dumps(
            {
                "metrics": asdict(metrics),
                "analysis": asdict(analysis) if analysis else None,
                "decisions": [decision.to_dict(root) for decision in decisions],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
