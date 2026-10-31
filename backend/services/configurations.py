"""Persist user layouts separately from bundled application resources."""

import json
import math
import sqlite3
import uuid
from contextlib import contextmanager

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.core.errors import APIError
from backend.core.paths import user_documents_root


class Region(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    rect: tuple[float, float, float, float]
    text_rect: tuple[float, float, float, float] | None = None


class Layout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    page_width: float = Field(gt=0, le=14400)
    page_height: float = Field(gt=0, le=14400)
    font_size: float = Field(default=14, ge=8, le=18)
    regions: list[Region] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_regions(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Enter a configuration name.")
        names = set()
        for region in self.regions:
            region.name = region.name.strip()
            if not region.name or region.name in names:
                raise ValueError("Each area needs a unique name.")
            names.add(region.name)
            for rect in (region.rect, region.text_rect or region.rect):
                x0, y0, x1, y1 = rect
                if not all(math.isfinite(v) for v in rect) or not (0 <= x0 < x1 <= self.page_width and 0 <= y0 < y1 <= self.page_height):
                    raise ValueError("Keep every area inside the reference page.")
                if x1 - x0 < 2 or y1 - y0 < 2:
                    raise ValueError("An area is too small. Draw a larger rectangle.")
        for index, first in enumerate(self.regions):
            for second in self.regions[index + 1:]:
                for a, b in ((first.rect, second.rect), (first.text_rect or first.rect, second.text_rect or second.rect)):
                    if max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3]):
                        raise ValueError("Translation areas must not overlap other areas of the same type.")
        return self


def owner_key(owner):
    try:
        return str(uuid.UUID(owner))
    except (ValueError, TypeError, AttributeError) as error:
        raise APIError("The configuration storage key is missing or invalid. Reload the app.", 400) from error


@contextmanager
def database():
    folder = user_documents_root() / "Configurations"
    folder.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(folder / "layouts.sqlite3", timeout=15)
    try:
        with connection:
            connection.execute("CREATE TABLE IF NOT EXISTS layouts (id TEXT PRIMARY KEY, owner TEXT NOT NULL, data TEXT NOT NULL)")
            yield connection
    finally:
        connection.close()


def list_layouts(owner):
    owner = owner_key(owner)
    with database() as connection:
        rows = connection.execute("SELECT id, data FROM layouts WHERE owner = ? ORDER BY rowid DESC", (owner,)).fetchall()
    return [{"id": key, **json.loads(data)} for key, data in rows]


def get_layout(owner, key):
    owner = owner_key(owner)
    with database() as connection:
        row = connection.execute("SELECT data FROM layouts WHERE owner = ? AND id = ?", (owner, key)).fetchone()
    if row is None:
        raise APIError("This configuration was deleted or is unavailable. Choose another configuration.", 404)
    return {"id": key, **json.loads(row[0])}


def save_layout(owner, layout, key=None):
    owner = owner_key(owner)
    updating = key is not None
    if key:
        get_layout(owner, key)
    key = key or str(uuid.uuid4())
    with database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        exists = connection.execute("SELECT 1 FROM layouts WHERE id = ? AND owner = ?", (key, owner)).fetchone()
        if updating and not exists:
            raise APIError("This configuration was deleted. Save it as a new configuration instead.", 404)
        if not exists and connection.execute("SELECT COUNT(*) FROM layouts WHERE owner = ?", (owner,)).fetchone()[0] >= 100:
            raise APIError("You can save up to 100 configurations. Delete an unused configuration first.", 400)
        connection.execute("INSERT INTO layouts (id, owner, data) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET data = excluded.data WHERE layouts.owner = excluded.owner", (key, owner, layout.model_dump_json()))
    return {"id": key, **layout.model_dump(mode="json")}


def delete_layout(owner, key):
    owner = owner_key(owner)
    with database() as connection:
        result = connection.execute("DELETE FROM layouts WHERE owner = ? AND id = ?", (owner, key))
        if not result.rowcount:
            raise APIError("This configuration is already deleted or unavailable.", 404)


def conversion_settings(owner, key):
    layout = get_layout(owner, key)
    return {
        "all_pages": [{**region, "page_size": [layout["page_width"], layout["page_height"]]} for region in layout["regions"]],
        "pdf_text": {"font_size": layout["font_size"], "vertical_padding": 0},
    }
