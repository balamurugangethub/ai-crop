"""Sourced disease information (English + Tamil). Add a language by adding a key
(e.g. "hi") next to "en"/"ta" in diseases.json; missing languages fall back to English."""
import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent
SUPPORTED_LANGUAGES = ("en", "ta")


@lru_cache
def _load():
    diseases = json.loads((_DIR / "diseases.json").read_text(encoding="utf-8"))
    sources = json.loads((_DIR / "sources.json").read_text(encoding="utf-8"))
    return diseases, sources


def all_class_ids() -> list[str]:
    return list(_load()[0].keys())


def get_disease(class_id: str, lang: str = "en") -> dict | None:
    diseases, sources = _load()
    entry = diseases.get(class_id)
    if entry is None:
        return None
    text = entry.get(lang) or entry["en"]
    return {
        "class_id": class_id,
        "crop": entry["crop"],
        "healthy": entry["healthy"],
        "severity": entry["severity"],
        "limited_source": entry.get("limited_source", False),
        "language": lang if lang in entry else "en",
        **text,
        "sources": [sources[s] for s in entry["sources"]],
    }
