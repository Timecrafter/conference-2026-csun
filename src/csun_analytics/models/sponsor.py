"""Sponsor data model."""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json
from pathlib import Path


@dataclass
class Sponsor:
    name: str
    tier: str = ""  # e.g., Platinum, Gold, Silver
    website: Optional[str] = None
    description: str = ""
    year: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Sponsor":
        return cls(**data)


def save_sponsors(sponsors: list["Sponsor"], path: Path) -> None:
    data = [s.to_dict() for s in sponsors]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_sponsors(path: Path) -> list["Sponsor"]:
    data = json.loads(path.read_text())
    return [Sponsor.from_dict(d) for d in data]
