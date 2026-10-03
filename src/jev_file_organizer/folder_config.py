import tomllib
from dataclasses import dataclass
from pathlib import Path

# claim: 2026-09-20-lightweight-local-metadata
CONFIG_NAME = ".jfo.toml"
TEMPLATE = """description = ""
context = ""
rules = []

[discovery]
candidate_names = []

[privacy]
exclude = []
redact = []
"""


@dataclass(frozen=True)
class FolderConfig:
    description: str = ""
    context: str = ""
    rules: tuple[str, ...] = ()
    candidate_names: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()
    redact_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class FolderGuidance:
    context: tuple[str, ...] = ()
    rules: tuple[str, ...] = ()
    candidate_names: tuple[str, ...] = ()


def read_folder_config(folder: Path) -> FolderConfig:
    path = folder / CONFIG_NAME
    if not path.exists():
        return FolderConfig()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    discovery = data.get("discovery", {})
    privacy = data.get("privacy", {})
    return FolderConfig(
        description=str(data.get("description", "")).strip(),
        context=str(data.get("context", "")).strip(),
        rules=tuple(str(rule).strip() for rule in data.get("rules", []) if str(rule).strip()),
        candidate_names=tuple(
            str(name).strip() for name in discovery.get("candidate_names", []) if str(name).strip()
        ),
        exclude_patterns=tuple(str(value) for value in privacy.get("exclude", [])),
        redact_patterns=tuple(str(value) for value in privacy.get("redact", [])),
    )


def load_privacy_policy(root: Path):
    from .privacy import DEFAULT_EXCLUDES, PrivacyPolicy

    config = read_folder_config(root)
    return PrivacyPolicy(
        exclude_patterns=DEFAULT_EXCLUDES + config.exclude_patterns,
        redact_patterns=config.redact_patterns,
    )


def load_guidance(root: Path, folder: Path) -> FolderGuidance:
    relative = folder.relative_to(root)
    lineage = [root]
    current = root
    for part in relative.parts:
        current /= part
        lineage.append(current)

    configs = [read_folder_config(path) for path in lineage]
    return FolderGuidance(
        context=tuple(config.context for config in configs if config.context),
        rules=tuple(rule for config in configs for rule in config.rules),
        # claim: 2026-10-03-local-folder-candidates
        candidate_names=configs[-1].candidate_names,
    )


def initialize_configs(root: Path, recursive: bool) -> list[Path]:
    folders = [root]
    if recursive:
        folders.extend(
            path
            for path in sorted(root.rglob("*"))
            if path.is_dir() and not path.is_symlink() and not path.name.startswith(".")
        )
    created = []
    for folder in folders:
        path = folder / CONFIG_NAME
        if path.exists():
            continue
        path.write_text(TEMPLATE, encoding="utf-8")
        created.append(path)
    return created
