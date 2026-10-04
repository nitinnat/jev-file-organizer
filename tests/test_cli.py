import subprocess
import sys
from pathlib import Path

from typer.main import get_command
from typer.testing import CliRunner

import jev_file_organizer.cli as cli
from jev_file_organizer.cli import app

runner = CliRunner()


def test_cli_import_defers_document_and_model_dependencies() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import jev_file_organizer.cli; "
                "print('markitdown' in sys.modules, 'onnxruntime' in sys.modules, "
                "'typesafe_sdk' in sys.modules)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False False False"


def test_version_is_available_without_configuration() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.2.0"


def test_doctor_reports_missing_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    result = runner.invoke(app, ["doctor", "--path", str(tmp_path)])

    assert result.exit_code == 1
    assert "missing; run jfo configure" in result.stdout


def test_help_shows_intelligent_default_opt_out() -> None:
    command = get_command(app)
    option = next(param for param in command.params if param.name == "discover_folders")

    assert "--discover-folders" in option.opts
    assert "--existing-folders-only" in option.secondary_opts


def test_folders_option_builds_a_plan_with_requested_names(monkeypatch) -> None:
    captured = {}

    def fake_run(*args) -> None:
        captured["requested_folders"] = args[-1]

    monkeypatch.setattr(cli, "run", fake_run)

    result = runner.invoke(app, ["-f", "Work Reports, Travel", "-f", "Medical"])

    assert result.exit_code == 0
    assert captured["requested_folders"] == ("Work Reports", "Travel", "Medical")


def test_help_exposes_folder_shortcut() -> None:
    command = get_command(app)
    option = next(param for param in command.params if param.name == "folders")

    assert "--folders" in option.opts
    assert "-f" in option.opts


def test_candidates_explains_file_type_source_without_api(tmp_path: Path) -> None:
    (tmp_path / "one.dmg").write_bytes(b"")
    (tmp_path / "two.dmg").write_bytes(b"")

    result = runner.invoke(app, ["candidates", str(tmp_path)])

    assert result.exit_code == 0
    assert "Software Installers" in result.stdout
    assert "2 .dmg" in result.stdout
    assert "no Jev request was made" in result.stdout


def test_evaluation_threshold_parser_includes_selected_threshold() -> None:
    assert cli.parse_thresholds("0.70, 0.90", 0.8) == (0.7, 0.8, 0.9)
