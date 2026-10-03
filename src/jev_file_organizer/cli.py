import logging
import os
import shutil
import sys
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .config import resolve_api_key, save_api_key
from .folder_config import initialize_configs, load_guidance
from .models import Decision, DecisionStatus, ProposedFolder
from .plans import PlanError, PlanStore
from .scanner import scan

if TYPE_CHECKING:
    from typesafe_sdk import TypeSafeAPIError

    from .evaluation import Metrics

MIN_THRESHOLD = 0.70
PACKAGE_NAME = "jev-file-organizer"
console = Console()
app = typer.Typer(
    name="jfo",
    help="Plan, apply, and undo recursive file organization with Jev.",
    invoke_without_command=True,
    no_args_is_help=False,
    pretty_exceptions_show_locals=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    show_version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the installed JFO version and exit.",
            is_eager=True,
        ),
    ] = False,
    path: Annotated[
        Path, typer.Option("--path", "-p", help="Folder to organize.")
    ] = Path("."),
    apply: Annotated[
        bool, typer.Option("--apply", help="Move approved files after showing the plan.")
    ] = False,
    threshold: Annotated[
        float,
        typer.Option("--threshold", "-t", help="Minimum Jev confidence (cannot be below 0.70)."),
    ] = MIN_THRESHOLD,
    model: Annotated[
        str, typer.Option("--model", help="Jev model alias or pinned version.")
    ] = "jev-latest",
    max_chars: Annotated[
        int, typer.Option("--max-chars", min=100, help="Maximum extracted characters per file.")
    ] = 12_000,
    max_pages: Annotated[
        int,
        typer.Option("--max-pages", min=1, help="Maximum page-marked sections retained per file."),
    ] = 5,
    discover_folders: Annotated[
        bool,
        typer.Option(
            "--discover-folders/--existing-folders-only",
            help="Propose missing child folders or use only folders already present.",
        ),
    ] = True,
    max_new_folders: Annotated[
        int, typer.Option("--max-new-folders", min=1, max=20)
    ] = 5,
    min_folder_files: Annotated[
        int, typer.Option("--min-folder-files", min=2)
    ] = 2,
    cache: Annotated[
        bool, typer.Option("--cache/--no-cache", help="Use the per-folder extraction cache.")
    ] = True,
    refresh_cache: Annotated[
        bool, typer.Option("--refresh-cache", help="Re-extract files and replace cache entries.")
    ] = False,
    include_hidden: Annotated[
        bool, typer.Option("--include-hidden", help="Include hidden files and folders.")
    ] = False,
    collision: Annotated[
        str, typer.Option(help="Existing destination policy: skip or rename.")
    ] = "skip",
    # claim: 2026-09-23-explicit-folder-option
    folders: Annotated[
        list[str] | None,
        typer.Option(
            "--folders",
            "-f",
            help="Root destination names, comma-separated or supplied more than once.",
        ),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show diagnostic logs.")
    ] = False,
) -> None:
    if show_version:
        console.print(version(PACKAGE_NAME))
        raise typer.Exit()
    if ctx.invoked_subcommand is not None:
        return
    configure_logging(verbose)
    run(
        path,
        apply,
        threshold,
        model,
        max_chars,
        max_pages,
        discover_folders,
        max_new_folders,
        min_folder_files,
        cache,
        refresh_cache,
        include_hidden,
        collision,
        parse_folder_names(folders or []),
    )


@app.command()
def configure(
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            help="Key value. Omit this option for a hidden prompt (recommended).",
            hide_input=True,
            prompt=False,
        ),
    ] = None,
) -> None:
    """Save a TypeSafe API key in the user's private config directory."""
    value = api_key or typer.prompt("TypeSafe API key", hide_input=True)
    if not value.strip():
        raise typer.BadParameter("API key cannot be empty")
    path = save_api_key(value)
    console.print(f"[green]Saved TypeSafe credentials to {path}[/green]")


@app.command()
def doctor(
    path: Annotated[Path, typer.Option("--path", "-p", help="Folder to inspect.")] = Path("."),
) -> None:
    """Check the installation, credentials, and current folder without changing files."""
    root = validated_root(path)
    api_configured = resolve_api_key(root) is not None
    checks = [
        ("JFO", version(PACKAGE_NAME), True),
        ("Python", sys.version.split()[0], (3, 12) <= sys.version_info[:2] < (3, 14)),
        (
            "TypeSafe API key",
            "configured" if api_configured else "missing; run jfo configure",
            api_configured,
        ),
        ("FFmpeg", shutil.which("ffmpeg") or "not found (audio extraction unavailable)", True),
        ("Folder", str(root), os.access(root, os.R_OK | os.W_OK)),
    ]
    table = Table(title="JFO doctor", header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Result")
    table.add_column("Status")
    for name, result, healthy in checks:
        table.add_row(name, result, "[green]ok[/green]" if healthy else "[red]fix needed[/red]")
    console.print(table)
    if not all(healthy for _, _, healthy in checks):
        raise typer.Exit(1)


@app.command("init")
def initialize(
    path: Annotated[Path, typer.Argument(help="Folder to configure.")] = Path("."),
    recursive: Annotated[
        bool, typer.Option("--recursive", "-r", help="Add templates to existing subfolders.")
    ] = False,
) -> None:
    """Create optional .jfo.toml configuration templates."""
    root = validated_root(path)
    created = initialize_configs(root, recursive)
    if created:
        console.print(f"[green]Created {len(created)} configuration file(s).[/green]")
        for config_path in created:
            console.print(f"  {config_path.relative_to(root)}")
    else:
        console.print("[dim]All selected folders already have .jfo.toml files.[/dim]")


@app.command()
def candidates(
    path: Annotated[Path, typer.Argument(help="Folder to inspect.")] = Path("."),
    max_chars: Annotated[int, typer.Option("--max-chars", min=100)] = 12_000,
    max_pages: Annotated[int, typer.Option("--max-pages", min=1)] = 5,
    refresh_cache: Annotated[bool, typer.Option("--refresh-cache")] = False,
) -> None:
    """Show every locally generated folder candidate before Jev filtering."""
    from .discovery import build_corpus
    from .extraction import TextExtractor

    root = validated_root(path)
    extractor = TextExtractor(max_chars, max_pages, refresh_cache=refresh_cache)
    rows = []
    try:
        for batch in scan(root, include_without_destinations=True):
            evidence = [extractor.extract(file) for file in batch.files]
            guidance = load_guidance(root, batch.parent)
            corpus = build_corpus(evidence, batch.destinations, guidance.candidate_names)
            rows.extend(
                (batch.parent.relative_to(root), name, reason)
                for name, reason in zip(
                    corpus.candidate_names,
                    corpus.candidate_reasons,
                    strict=True,
                )
            )
            extractor.flush()
    finally:
        extractor.flush()

    table = Table(title="Folder candidates sent to Jev", header_style="bold magenta")
    table.add_column("Parent")
    table.add_column("Candidate")
    table.add_column("Source")
    for parent, name, reason in rows:
        table.add_row(str(parent) if str(parent) != "." else "root", name, reason)
    console.print(table)
    console.print(f"[dim]{len(rows)} candidates; no Jev request was made.[/dim]")


@app.command("apply")
def apply_saved(
    plan_id: Annotated[str, typer.Argument(help="Plan identifier from a preview.")],
    path: Annotated[Path, typer.Option("--path", "-p")] = Path("."),
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Apply a previously previewed plan after validating every source."""
    configure_logging(verbose)
    try:
        result = PlanStore(validated_root(path)).apply(plan_id)
    except PlanError as error:
        plan_error(error)
    console.print(
        f"[green]Applied plan {result['id']}:[/green] {result['moves']} moves, "
        f"{result['folders']} folders created."
    )


@app.command("undo")
def undo_saved(
    plan_id: Annotated[
        str | None, typer.Argument(help="Applied plan ID; defaults to the latest applied plan.")
    ] = None,
    path: Annotated[Path, typer.Option("--path", "-p")] = Path("."),
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Reverse an applied plan if none of its moved files changed."""
    configure_logging(verbose)
    try:
        result = PlanStore(validated_root(path)).undo(plan_id)
    except PlanError as error:
        plan_error(error)
    console.print(
        f"[green]Undid plan {result['id']}:[/green] {result['moves']} moves, "
        f"{result['folders']} empty folders removed."
    )


@app.command("evaluate")
def evaluate_command(
    path: Annotated[Path, typer.Argument(help="Labeled sample folder.")],
    manifest: Annotated[
        Path, typer.Option("--manifest", "-m", help="JSON file containing expected destinations.")
    ],
    report: Annotated[
        Path | None, typer.Option("--report", help="Write detailed JSON results here.")
    ] = None,
    threshold: Annotated[float, typer.Option("--threshold", "-t")] = MIN_THRESHOLD,
    model: Annotated[str, typer.Option("--model")] = "jev-latest",
    max_chars: Annotated[int, typer.Option("--max-chars", min=100)] = 12_000,
    max_pages: Annotated[int, typer.Option("--max-pages", min=1)] = 5,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Measure Jev decisions against a labeled manifest without moving files."""
    from typesafe_sdk import TypeSafeAPIError

    from .classifier import JevClassifier
    from .evaluation import evaluate, load_manifest, write_report
    from .extraction import TextExtractor
    from .organizer import create_plan

    configure_logging(verbose)
    root = validated_root(path)
    validate_threshold(threshold)
    api_key = require_api_key(root)
    classifier = JevClassifier(api_key, model)
    try:
        extractor = TextExtractor(max_chars, max_pages)
        decisions, latency = create_plan(
            root, classifier, extractor, threshold
        )
    except TypeSafeAPIError as error:
        api_error(error)
    finally:
        classifier.close()

    metrics = evaluate(root, decisions, load_manifest(manifest), latency)
    render_plan(root, decisions, apply=False)
    render_metrics(metrics)
    if report:
        write_report(report, root, decisions, metrics)
        console.print(f"[green]Report written to {report}[/green]")


def run(
    path: Path,
    should_apply: bool,
    threshold: float,
    model: str,
    max_chars: int,
    max_pages: int,
    discover_folders: bool,
    max_new_folders: int,
    min_folder_files: int,
    cache: bool,
    refresh_cache: bool,
    include_hidden: bool,
    collision: str,
    requested_folders: tuple[str, ...] = (),
) -> None:
    from typesafe_sdk import TypeSafeAPIError

    from .classifier import JevClassifier
    from .extraction import TextExtractor
    from .organizer import create_intelligent_plan

    root = validated_root(path)
    validate_threshold(threshold)
    if collision not in {"skip", "rename"}:
        raise typer.BadParameter("collision must be 'skip' or 'rename'")
    api_key = require_api_key(root)
    classifier = JevClassifier(api_key, model)
    try:
        extractor = TextExtractor(
            max_chars,
            max_pages,
            cache_enabled=cache,
            refresh_cache=refresh_cache,
        )
        result = create_intelligent_plan(
            root,
            classifier,
            extractor,
            threshold,
            include_hidden=include_hidden,
            discover_folders=discover_folders,
            max_new_folders=max_new_folders,
            min_folder_files=min_folder_files,
            requested_folders=requested_folders,
        )
    except TypeSafeAPIError as error:
        api_error(error)
    finally:
        classifier.close()

    render_proposed_folders(root, result.proposed_folders)
    store = PlanStore(root)
    plan_id = store.create(
        result.decisions,
        result.proposed_folders,
        threshold,
        model,
        collision,
    )
    render_plan(root, result.decisions, apply=False)
    console.print(f"[cyan]Plan ID:[/cyan] {plan_id}")
    if should_apply:
        try:
            applied = store.apply(plan_id)
        except PlanError as error:
            plan_error(error)
        for decision in result.decisions:
            if decision.status == DecisionStatus.MOVE:
                decision.status = DecisionStatus.MOVED
        render_plan(root, result.decisions, apply=True)
        console.print(
            f"[green]Applied {applied['moves']} moves and created "
            f"{applied['folders']} folders.[/green]"
        )
    moved = sum(
        decision.status in {DecisionStatus.MOVE, DecisionStatus.MOVED}
        for decision in result.decisions
    )
    mode = "applied" if should_apply else "previewed"
    console.print(
        f"\n[bold]{mode.capitalize()} {len(result.decisions)} files in "
        f"{result.latency_seconds:.2f}s; "
        f"{moved} approved at confidence >= {threshold:.2f}.[/bold]"
    )
    if cache:
        console.print(
            f"[dim]Extraction cache: {extractor.cache.hits} hits, "
            f"{extractor.cache.misses} misses.[/dim]"
        )
        console.print(
            f"[dim]Jev classification cache: {extractor.cache.classification_hits} hits, "
            f"{extractor.cache.classification_misses} misses.[/dim]"
        )
    if not should_apply and moved:
        console.print(f"Run [cyan]jfo apply {plan_id}[/cyan] to perform this exact plan.")


def validated_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if not root.is_dir():
        raise typer.BadParameter(f"not a directory: {root}")
    return root


def parse_folder_names(values: list[str]) -> tuple[str, ...]:
    validated = []
    seen = set()
    for name in (part for value in values for part in value.split(",")):
        cleaned = " ".join(name.split())
        if (
            not cleaned
            or cleaned in {".", ".."}
            or Path(cleaned).name != cleaned
            or "\\" in cleaned
        ):
            raise typer.BadParameter(f"invalid folder name: {name!r}")
        if cleaned.casefold() not in seen:
            validated.append(cleaned)
            seen.add(cleaned.casefold())
    return tuple(validated)


def validate_threshold(threshold: float) -> None:
    if not MIN_THRESHOLD <= threshold <= 1:
        raise typer.BadParameter("threshold must be between 0.70 and 1.00")


def require_api_key(root: Path) -> str:
    if api_key := resolve_api_key(root):
        return api_key
    console.print(
        "[red]No TypeSafe API key found.[/red] Run [cyan]jfo configure[/cyan], set "
        "[cyan]TYPESAFE_API_KEY[/cyan], or add it to [cyan].env[/cyan]."
    )
    raise typer.Exit(2)


def api_error(error: "TypeSafeAPIError") -> None:
    logging.getLogger(__name__).exception(
        "[JEV] request_failed status=%s request_id=%s", error.status, error.request_id
    )
    console.print(
        f"[red]Jev request failed[/red] (status={error.status}, request_id={error.request_id})."
    )
    raise typer.Exit(1)


def plan_error(error: PlanError) -> None:
    console.print(f"[red]Plan operation refused:[/red] {error}")
    raise typer.Exit(1)


def render_proposed_folders(root: Path, folders: list[ProposedFolder]) -> None:
    if not folders:
        return
    table = Table(title="Proposed folders", header_style="bold magenta")
    table.add_column("Folder")
    table.add_column("Discovery confidence", justify="right")
    table.add_column("Supporting files", justify="right")
    table.add_column("Candidate source")
    for folder in folders:
        table.add_row(
            str(folder.path.relative_to(root)),
            f"{folder.confidence:.2f}",
            str(len(folder.supporting_files)),
            folder.rationale,
        )
    console.print(table)


def render_plan(root: Path, decisions: list[Decision], apply: bool) -> None:
    title = "Applied changes" if apply else "Organization preview"
    table = Table(title=title, header_style="bold cyan")
    table.add_column("Status")
    table.add_column("File")
    table.add_column("Destination")
    table.add_column("Confidence", justify="right")
    table.add_column("Evidence")
    styles = {
        DecisionStatus.MOVE: "green",
        DecisionStatus.MOVED: "green bold",
        DecisionStatus.NO_MATCH: "dim",
        DecisionStatus.LOW_CONFIDENCE: "yellow",
        DecisionStatus.COLLISION: "red",
        DecisionStatus.ERROR: "red",
    }
    for decision in decisions:
        destination = (
            str(decision.destination.parent.relative_to(root))
            if decision.destination
            else "—"
        )
        table.add_row(
            f"[{styles[decision.status]}]{decision.status.value}[/{styles[decision.status]}]",
            str(decision.source.relative_to(root)),
            destination,
            f"{decision.confidence:.2f}",
            decision.extraction,
        )
    console.print(table)


def render_metrics(metrics: "Metrics") -> None:
    table = Table(title="Evaluation", header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    values = {
        "Accuracy": f"{metrics.accuracy:.1%}",
        "Move precision": f"{metrics.precision:.1%}",
        "Move recall": f"{metrics.recall:.1%}",
        "Coverage": f"{metrics.coverage:.1%}",
        "Abstention rate": f"{metrics.abstention_rate:.1%}",
        "Correct": f"{metrics.correct}/{metrics.total}",
        "Latency": f"{metrics.latency_seconds:.2f}s",
    }
    for name, value in values.items():
        table.add_row(name, value)
    console.print(table)


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(message)s",
        handlers=[RichHandler(show_path=False, rich_tracebacks=True)],
        force=True,
    )
    os.environ.setdefault("TYPESAFE_LOG_LEVEL", "INFO" if verbose else "WARNING")
