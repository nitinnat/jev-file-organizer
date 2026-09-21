from pathlib import Path

from jev_file_organizer.folder_config import initialize_configs, load_guidance


def test_guidance_inherits_context_rules_and_candidate_names(tmp_path: Path) -> None:
    child = tmp_path / "Inbox"
    child.mkdir()
    (tmp_path / ".jfo.toml").write_text(
        'context = "Household records"\nrules = ["Keep tax files separate"]\n'
        '[discovery]\ncandidate_names = ["Finance"]\n',
        encoding="utf-8",
    )
    (child / ".jfo.toml").write_text(
        'context = "Incoming documents"\nrules = ["Travel bookings stay together"]\n'
        '[discovery]\ncandidate_names = ["Travel"]\n',
        encoding="utf-8",
    )

    guidance = load_guidance(tmp_path, child)

    assert guidance.context == ("Household records", "Incoming documents")
    assert guidance.rules == (
        "Keep tax files separate",
        "Travel bookings stay together",
    )
    assert guidance.candidate_names == ("Finance", "Travel")


def test_recursive_initializer_preserves_existing_configs(tmp_path: Path) -> None:
    child = tmp_path / "Child"
    child.mkdir()
    existing = tmp_path / ".jfo.toml"
    existing.write_text('description = "Existing"\n', encoding="utf-8")

    created = initialize_configs(tmp_path, recursive=True)

    assert created == [child / ".jfo.toml"]
    assert "Existing" in existing.read_text(encoding="utf-8")
