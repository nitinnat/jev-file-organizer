import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from jev_file_organizer.classifier import JevClassifier
from jev_file_organizer.cli import app
from jev_file_organizer.extraction import TextExtractor
from jev_file_organizer.folder_config import FolderGuidance, load_privacy_policy
from jev_file_organizer.models import FileEvidence, FolderOption
from jev_file_organizer.privacy import PrivacyPolicy

runner = CliRunner()


def test_policy_excludes_credentials_and_configured_paths(tmp_path: Path) -> None:
    (tmp_path / ".jfo.toml").write_text('[privacy]\nexclude = ["private/**"]\n', encoding="utf-8")
    policy = load_privacy_policy(tmp_path)

    assert policy.excludes(tmp_path, tmp_path / ".env")
    assert policy.excludes(tmp_path, tmp_path / "private" / "notes.txt")
    assert not policy.excludes(tmp_path, tmp_path / "notes.txt")


def test_redaction_happens_before_cache_write(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("token=secret-123", encoding="utf-8")
    extractor = TextExtractor(privacy=PrivacyPolicy(redact_patterns=(r"secret-\d+",)))

    assert extractor.extract(source).content == "token=[REDACTED]"
    extractor.flush()

    raw_cache = (tmp_path / ".jfo-cache.json").read_text(encoding="utf-8")
    assert "secret-123" not in raw_cache
    assert "[REDACTED]" in raw_cache


class CaptureClient:
    def __init__(self) -> None:
        self.state = None

    def system_one(self, state, questions):
        self.state = state
        return SimpleNamespace(
            nouls={key: SimpleNamespace(noul=0.8) for key in questions},
            request_id="privacy-test",
        )


def test_classifier_redacts_every_outbound_string(tmp_path: Path) -> None:
    client = CaptureClient()
    classifier = JevClassifier.__new__(JevClassifier)
    classifier._client = client
    classifier._privacy = PrivacyPolicy(redact_patterns=(r"secret-\d+",))

    classifier.classify(
        tmp_path,
        [FileEvidence(tmp_path / "secret-123.txt", "token secret-123", "markitdown")],
        [FolderOption(tmp_path / "secret-123")],
        0.7,
        FolderGuidance(context=("secret-123",), rules=("hide secret-123",)),
    )

    assert "secret-123" not in json.dumps(client.state)
    assert "[REDACTED]" in json.dumps(client.state)


def test_payload_preview_and_cache_commands(tmp_path: Path) -> None:
    (tmp_path / "Finance").mkdir()
    (tmp_path / "notes.txt").write_text("account secret-123", encoding="utf-8")
    (tmp_path / ".env").write_text("TYPESAFE_API_KEY=", encoding="utf-8")
    (tmp_path / ".jfo.toml").write_text('[privacy]\nredact = ["secret-[0-9]+"]\n', encoding="utf-8")

    preview = runner.invoke(app, ["payloads", str(tmp_path), "--include-hidden"])

    assert preview.exit_code == 0
    assert "secret-123" not in preview.stdout
    assert "[REDACTED]" in preview.stdout
    assert '".env"' in preview.stdout
    assert "No Jev request was made" in preview.stdout

    inspection = runner.invoke(app, ["cache", "inspect", str(tmp_path)])
    assert inspection.exit_code == 0
    assert "1 cache file(s)" in inspection.stdout

    cleared = runner.invoke(app, ["cache", "clear", str(tmp_path)])
    assert cleared.exit_code == 0
    assert not (tmp_path / ".jfo-cache.json").exists()
