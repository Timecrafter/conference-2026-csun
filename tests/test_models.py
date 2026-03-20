"""Tests for data models."""

import json
import tempfile
from pathlib import Path

from csun_analytics.models.session import Presenter, Session, save_sessions, load_sessions
from csun_analytics.models.exhibitor import Exhibitor, save_exhibitors, load_exhibitors


def test_session_roundtrip():
    sessions = [
        Session(
            session_id=1,
            title="Test Session",
            presenters=[Presenter(name="Jane Doe", affiliation="MIT")],
            abstract="A test abstract.",
            track="General Track",
            primary_topic="Blind/Low Vision",
            year=2024,
        )
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "sessions.json"
        save_sessions(sessions, path)
        loaded = load_sessions(path)

    assert len(loaded) == 1
    assert loaded[0].title == "Test Session"
    assert loaded[0].presenters[0].name == "Jane Doe"
    assert loaded[0].presenters[0].affiliation == "MIT"


def test_exhibitor_roundtrip():
    exhibitors = [
        Exhibitor(
            exhibitor_id=1,
            name="TestCo",
            booth_numbers=["101", "102"],
            description="A test exhibitor.",
            website="https://example.com",
            year=2024,
        )
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "exhibitors.json"
        save_exhibitors(exhibitors, path)
        loaded = load_exhibitors(path)

    assert len(loaded) == 1
    assert loaded[0].name == "TestCo"
    assert loaded[0].booth_numbers == ["101", "102"]
