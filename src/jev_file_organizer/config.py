import json
import os
from pathlib import Path

from dotenv import dotenv_values
from platformdirs import user_config_path

APP_NAME = "jfo"


def config_path() -> Path:
    return user_config_path(APP_NAME) / "config.json"


def save_api_key(api_key: str) -> Path:
    path = config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps({"typesafe_api_key": api_key.strip()}), encoding="utf-8")
    path.chmod(0o600)
    return path


def resolve_api_key(directory: Path) -> str | None:
    if value := os.getenv("TYPESAFE_API_KEY"):
        return value

    if value := dotenv_values(directory / ".env").get("TYPESAFE_API_KEY"):
        return value

    path = config_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("typesafe_api_key")
