import os
import sys
from pathlib import Path


def resource_root():
    """Return the project resources directory in source and packaged builds."""
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        for candidate in (executable_dir, *executable_dir.parents):
            if (candidate / "hindi_terms.json").is_file():
                return candidate
        return executable_dir
    return Path(__file__).resolve().parents[2]


def user_documents_root():
    configured = os.environ.get("BHARATDOCS_DOCUMENTS")
    if configured:
        return Path(configured).expanduser().resolve()
    documents = Path.home() / "Documents"
    return documents / "BharatDocs"
