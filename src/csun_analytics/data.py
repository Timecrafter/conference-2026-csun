"""Shared data loading layer for CSUN analytics.

Centralizes all data loading and provides cached access to sessions,
speakers, and exhibitors as both dicts and DataFrames.
"""

import json
import functools
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

YEARS = [2023, 2024, 2025, 2026]


@functools.lru_cache
def load_sessions_raw(year: int) -> tuple[dict, ...]:
    """Load raw session dicts for a year (tuple for hashability/caching)."""
    path = RAW_DIR / f"sessions_{year}.json"
    if not path.exists():
        return ()
    with open(path) as f:
        return tuple(json.load(f))


def load_sessions(year: int) -> list[dict]:
    return list(load_sessions_raw(year))


def load_all_sessions() -> dict[int, list[dict]]:
    return {y: load_sessions(y) for y in YEARS}


def load_all_sessions_flat() -> list[dict]:
    flat = []
    for y in YEARS:
        flat.extend(load_sessions(y))
    return flat


@functools.lru_cache
def load_speakers_raw(year: int) -> tuple[dict, ...]:
    path = RAW_DIR / f"speakers_{year}.json"
    if not path.exists():
        path = RAW_DIR / f"speakers_{year}_full.json"
    if not path.exists():
        return ()
    with open(path) as f:
        return tuple(json.load(f))


def load_speakers(year: int) -> list[dict]:
    return list(load_speakers_raw(year))


def load_taxonomy() -> dict | None:
    """Load the normalized topic taxonomy if it exists."""
    path = PROCESSED_DIR / "topic_taxonomy.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def sessions_dataframe(sessions: list[dict] | None = None) -> pd.DataFrame:
    """Convert sessions to a DataFrame with flattened presenter/topic info."""
    if sessions is None:
        sessions = load_all_sessions_flat()
    rows = []
    for s in sessions:
        presenters = s.get("presenters") or []
        presenter_names = [p.get("name", "") for p in presenters]
        orgs = list({p.get("affiliation", "") for p in presenters if p.get("affiliation")})
        rows.append({
            "session_id": str(s.get("session_id", "")),
            "title": s.get("title", ""),
            "year": s.get("year", 0),
            "primary_topic": s.get("primary_topic", ""),
            "secondary_topics": s.get("secondary_topics", []),
            "audience_level": s.get("audience_level", ""),
            "target_audiences": s.get("target_audiences", []),
            "date": s.get("date", ""),
            "time": s.get("time", ""),
            "location": s.get("location", ""),
            "description": s.get("description", "") or "",
            "abstract": s.get("abstract", "") or "",
            "presenter_names": presenter_names,
            "presenter_count": len(presenters),
            "organizations": orgs,
            "content_tags": s.get("content_tags", []),
            "learning_objectives": s.get("learning_objectives", []),
        })
    return pd.DataFrame(rows)
