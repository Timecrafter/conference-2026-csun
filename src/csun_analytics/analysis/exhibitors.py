"""Exhibitor data analysis."""

from collections import Counter
from pathlib import Path

import pandas as pd

from csun_analytics.models.exhibitor import Exhibitor


class ExhibitorAnalyzer:
    """Analyze scraped exhibitor data."""

    def __init__(self, exhibitors: list[Exhibitor]):
        self.exhibitors = exhibitors
        self.df = self._to_dataframe()

    def _to_dataframe(self) -> pd.DataFrame:
        records = []
        for e in self.exhibitors:
            records.append({
                "exhibitor_id": e.exhibitor_id,
                "name": e.name,
                "booth_numbers": "; ".join(e.booth_numbers),
                "num_booths": len(e.booth_numbers),
                "description": e.description,
                "website": e.website,
                "categories": "; ".join(e.categories),
                "products": "; ".join(e.products),
                "year": e.year,
                "has_website": e.website is not None,
                "has_description": len(e.description) > 0,
            })
        return pd.DataFrame(records)

    def summary(self) -> dict:
        return {
            "total_exhibitors": len(self.exhibitors),
            "with_website": int(self.df["has_website"].sum()),
            "with_description": int(self.df["has_description"].sum()),
            "avg_booths": round(self.df["num_booths"].mean(), 2),
        }

    def top_categories(self, n: int = 20) -> list[tuple[str, int]]:
        all_cats = []
        for e in self.exhibitors:
            all_cats.extend(e.categories)
        return Counter(all_cats).most_common(n)

    def save_report(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(output_dir / "exhibitors.csv", index=False)

        import json
        (output_dir / "exhibitor_summary.json").write_text(
            json.dumps(self.summary(), indent=2, ensure_ascii=False)
        )
