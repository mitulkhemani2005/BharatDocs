import json
from pathlib import Path


def load_config(path=None):
    config_path = Path(path) if path else Path(__file__).resolve().parent / "config.json"
    with config_path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    if not isinstance(config, dict):
        raise ValueError("The root of the conversion configuration must be an object.")
    return config
