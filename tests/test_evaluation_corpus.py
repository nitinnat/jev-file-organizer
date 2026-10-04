import json
import subprocess
import sys
from pathlib import Path


def test_evaluation_corpus_generator_is_reproducible(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    manifest = tmp_path / "manifest.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/generate_evaluation_corpus.py",
            "--output",
            str(root),
            "--manifest",
            str(manifest),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    expected = json.loads(manifest.read_text(encoding="utf-8"))["expected"]
    assert len(expected) == 22
    assert all((root / source).is_file() for source in expected)
    assert {Path(source).suffix for source in expected} >= {
        ".csv",
        ".docx",
        ".eml",
        ".json",
        ".pdf",
        ".pptx",
        ".wav",
        ".xlsx",
        ".zip",
    }
