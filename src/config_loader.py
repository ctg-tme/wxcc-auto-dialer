import json
import os
from pathlib import Path
from typing import Any, Optional


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.json"


def _stringify_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return ""
    if isinstance(value, list):
        if value and any(isinstance(item, (list, dict)) for item in value):
            return json.dumps(value)
        return "\n".join(_stringify_value(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value)
    return str(value)


def load_env_from_json(config_path: Optional[Path] = None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open() as fp:
        data = json.load(fp)
    for key, value in data.items():
        os.environ[key] = _stringify_value(value)
    return data
