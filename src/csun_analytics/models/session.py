"""Session and Presenter data models."""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json
from pathlib import Path


@dataclass
class Presenter:
    name: str
    affiliation: Optional[str] = None
    role: Optional[str] = None


@dataclass
class Session:
    session_id: str | int = ""
    title: str = ""
    presenters: list[Presenter] = field(default_factory=list)
    abstract: str = ""
    description: str = ""
    track: str = ""  # General, Journal, Exhibitor, Pre-Conference
    primary_topic: str = ""
    secondary_topics: list[str] = field(default_factory=list)
    audience_level: str = ""
    target_audiences: list[str] = field(default_factory=list)
    date: str = ""
    time: str = ""
    location: str = ""
    year: int = 0
    paper_url: Optional[str] = None
    paper_local_path: Optional[str] = None
    content_tags: list[str] = field(default_factory=list)
    learning_objectives: list[str] = field(default_factory=list)
    start_datetime_utc: str = ""
    end_datetime_utc: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        presenters = [Presenter(**p) for p in data.pop("presenters", [])]
        return cls(presenters=presenters, **data)


def save_sessions(sessions: list[Session], path: Path) -> None:
    data = [s.to_dict() for s in sessions]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_sessions(path: Path) -> list[Session]:
    data = json.loads(path.read_text())
    return [Session.from_dict(d) for d in data]
