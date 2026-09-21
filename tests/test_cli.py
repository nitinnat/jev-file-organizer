from pathlib import Path

from typer.main import get_command
from typer.testing import CliRunner

from jev_file_organizer.cli import app

runner = CliRunner()


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


def test_candidates_explains_file_type_source_without_api(tmp_path: Path) -> None:
    (tmp_path / "one.dmg").write_bytes(b"")
    (tmp_path / "two.dmg").write_bytes(b"")

    result = runner.invoke(app, ["candidates", str(tmp_path)])

    assert result.exit_code == 0
    assert "Software Installers" in result.stdout
    assert "2 .dmg" in result.stdout
    assert "no Jev request was made" in result.stdout
