import json
from pathlib import Path

from backend.core.paths import resource_root


def load_config(path=None):
    config_path = Path(path) if path else resource_root() / "config.json"
    with config_path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    if not isinstance(config, dict):
        raise ValueError("The root of the conversion configuration must be an object.")
    return config
