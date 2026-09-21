from pathlib import Path

from jev_file_organizer.extraction import TextExtractor


def test_extracts_supported_text_and_falls_back_for_unsupported(tmp_path: Path) -> None:
    text_file = tmp_path / "invoice.txt"
    text_file.write_text("Quarterly software invoice", encoding="utf-8")
    binary_file = tmp_path / "holiday-photo.proprietary"
    binary_file.write_bytes(bytes(range(256)) * 4)
    extractor = TextExtractor()

    text = extractor.extract(text_file)
    binary = extractor.extract(binary_file)

    assert "Quarterly software invoice" in text.content
    assert text.extraction == "markitdown"
    assert binary.content == "holiday-photo.proprietary"
    assert binary.extraction == "filename_unsupported"


def test_falls_back_when_markitdown_converter_crashes(tmp_path: Path) -> None:
    path = tmp_path / "unicode.json"
    path.write_text('{"label": "Pokémon"}', encoding="utf-8")
    extractor = TextExtractor()

    def fail_conversion(path: Path) -> None:
        raise UnicodeDecodeError("ascii", b"\xff", 0, 1, "not ascii")

    extractor._converter.convert_local = fail_conversion

    evidence = extractor.extract(path)

    assert evidence.content == "unicode.json"
    assert evidence.extraction == "filename_conversion_error"
