import os
import sys
from pathlib import Path


def resource_root():
    """Return the project resources directory in source and packaged builds."""
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        for candidate in (executable_dir, *executable_dir.parents):
            if (candidate / "config.json").is_file():
                return candidate
        return executable_dir
    return Path(__file__).resolve().parents[2]


def user_data_root():
    configured = os.environ.get("BHARATDOCS_USER_DATA")
    if configured:
        return Path(configured).expanduser().resolve()
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "BharatDocs"
    return resource_root()
