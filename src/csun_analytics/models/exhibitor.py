"""Exhibitor data model."""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json
from pathlib import Path


@dataclass
class Exhibitor:
    exhibitor_id: int
    name: str
    booth_numbers: list[str] = field(default_factory=list)
    description: str = ""
    website: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    products: list[str] = field(default_factory=list)
    year: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Exhibitor":
        return cls(**data)


def save_exhibitors(exhibitors: list["Exhibitor"], path: Path) -> None:
    data = [e.to_dict() for e in exhibitors]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_exhibitors(path: Path) -> list["Exhibitor"]:
    data = json.loads(path.read_text())
    return [Exhibitor.from_dict(d) for d in data]
