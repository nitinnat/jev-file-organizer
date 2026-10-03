import logging
import os
from pathlib import Path

from .models import FolderBatch

logger = logging.getLogger(__name__)


IGNORED_DIRECTORIES = {".git", ".jfo", ".venv", "__pycache__"}
IGNORED_FILES = {".jfo-cache.json", ".jfo.toml"}


def child_folders(parent: Path, include_hidden: bool = False) -> tuple[Path, ...]:
    if not parent.is_dir():
        return ()
    return tuple(
        path
        for path in sorted(parent.iterdir())
        if path.is_dir()
        and not path.is_symlink()
        and path.name not in IGNORED_DIRECTORIES
        and (include_hidden or not path.name.startswith("."))
    )


def scan(
    root: Path,
    include_hidden: bool = False,
    include_without_destinations: bool = False,
) -> list[FolderBatch]:
    logger.info("[SCAN] start root=%s include_hidden=%s", root, include_hidden)
    batches: list[FolderBatch] = []

    for parent, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in IGNORED_DIRECTORIES and (include_hidden or not name.startswith("."))
        )
        parent_path = Path(parent)
        destinations = child_folders(parent_path, include_hidden)
        files = tuple(
            path
            for name in sorted(file_names)
            if name not in IGNORED_FILES
            and (include_hidden or not name.startswith("."))
            and not (path := parent_path / name).is_symlink()
            and path.is_file()
        )
        if files and (destinations or include_without_destinations):
            batches.append(
                FolderBatch(parent=parent_path, files=files, destinations=destinations)
            )

    logger.info(
        "[SCAN] complete root=%s batches=%d files=%d",
        root,
        len(batches),
        sum(len(batch.files) for batch in batches),
    )
    return batches
