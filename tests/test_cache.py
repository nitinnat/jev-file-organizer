import json
from pathlib import Path

from jev_file_organizer.extraction import TextExtractor, limit_pages


def test_cache_reuses_unchanged_extraction_and_invalidates_changes(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("initial notes", encoding="utf-8")
    first_extractor = TextExtractor()

    first = first_extractor.extract(path)
    first_extractor.flush()
    second_extractor = TextExtractor()
    cached = second_extractor.extract(path)

    assert first.extraction == "markitdown"
    assert cached.extraction == "cache:markitdown"
    assert second_extractor.cache.hits == 1

    path.write_text("changed notes with a different size", encoding="utf-8")
    refreshed = second_extractor.extract(path)

    assert refreshed.extraction == "markitdown"
    assert second_extractor.cache.misses == 1


def test_cache_rebuilds_when_json_has_the_wrong_shape(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("release notes", encoding="utf-8")
    (tmp_path / ".jfo-cache.json").write_text("[]", encoding="utf-8")

    extractor = TextExtractor()
    evidence = extractor.extract(path)
    extractor.flush()

    assert evidence.content == "release notes"
    assert evidence.extraction == "markitdown"


def test_cache_rebuilds_malformed_file_entry(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("release notes", encoding="utf-8")
    extractor = TextExtractor()
    (tmp_path / ".jfo-cache.json").write_text(
        json.dumps(
            {
                "version": 1,
                "entries": {
                    path.name: {"fingerprint": extractor.cache.fingerprint(path)},
                },
            }
        ),
        encoding="utf-8",
    )

    evidence = extractor.extract(path)

    assert evidence.content == "release notes"
    assert evidence.extraction == "markitdown"


def test_page_limit_uses_form_feed_boundaries() -> None:
    assert limit_pages("one\ftwo\fthree", 2) == "one\n\ntwo"
