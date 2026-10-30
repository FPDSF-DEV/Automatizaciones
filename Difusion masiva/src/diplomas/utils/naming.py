from __future__ import annotations

import re
import unicodedata
from typing import Iterable

_slug_invalid = re.compile(r"[^a-zA-Z0-9_-]+")


def slugify(value: str, preserve_accents: bool = True) -> str:
    original = value
    if not preserve_accents:
        value = unicodedata.normalize("NFKD", value)
        value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.strip().replace(" ", "-")
    value = _slug_invalid.sub("-", value)
    value = re.sub(r"-+", "-", value)
    value = value.strip("-_").lower()
    return value or "sin-nombre"


def ensure_unique_slug(slug: str, existing: set[str]) -> str:
    if slug not in existing:
        existing.add(slug)
        return slug
    i = 2
    base = slug
    while True:
        candidate = f"{base}-{i}"
        if candidate not in existing:
            existing.add(candidate)
            return candidate
        i += 1


__all__ = ["slugify", "ensure_unique_slug"]
