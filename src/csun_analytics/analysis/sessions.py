"""Session data analysis."""

from collections import Counter
from pathlib import Path

import pandas as pd

from csun_analytics.models.session import Session


class SessionAnalyzer:
    """Analyze scraped session data."""

    def __init__(self, sessions: list[Session]):
        self.sessions = sessions
        self.df = self._to_dataframe()

    def _to_dataframe(self) -> pd.DataFrame:
        records = []
        for s in self.sessions:
            record = {
                "session_id": s.session_id,
                "title": s.title,
                "track": s.track,
                "primary_topic": s.primary_topic,
                "audience_level": s.audience_level,
                "date": s.date,
                "time": s.time,
                "location": s.location,
                "year": s.year,
                "abstract": s.abstract,
                "num_presenters": len(s.presenters),
                "num_secondary_topics": len(s.secondary_topics),
                "secondary_topics": "; ".join(s.secondary_topics),
                "target_audiences": "; ".join(s.target_audiences),
                "has_paper": s.paper_url is not None,
                "presenter_names": "; ".join(p.name for p in s.presenters),
                "presenter_affiliations": "; ".join(
                    p.affiliation for p in s.presenters if p.affiliation
                ),
            }
            records.append(record)
        return pd.DataFrame(records)

    def summary(self) -> dict:
        """High-level summary statistics."""
        return {
            "total_sessions": len(self.sessions),
            "years": sorted(self.df["year"].unique().tolist()),
            "tracks": self.df["track"].value_counts().to_dict(),
            "topics": self.df["primary_topic"].value_counts().to_dict(),
            "audience_levels": self.df["audience_level"].value_counts().to_dict(),
            "sessions_with_papers": int(self.df["has_paper"].sum()),
            "avg_presenters_per_session": round(self.df["num_presenters"].mean(), 2),
        }

    def topic_trends(self) -> pd.DataFrame:
        """Topic distribution, optionally across years."""
        return self.df.groupby(["year", "primary_topic"]).size().reset_index(name="count")

    def top_presenters(self, n: int = 20) -> list[tuple[str, int]]:
        """Most frequent presenters across sessions."""
        all_presenters = []
        for s in self.sessions:
            for p in s.presenters:
                all_presenters.append(p.name)
        return Counter(all_presenters).most_common(n)

    def top_affiliations(self, n: int = 20) -> list[tuple[str, int]]:
        """Most represented organizations."""
        all_affiliations = []
        for s in self.sessions:
            for p in s.presenters:
                if p.affiliation:
                    all_affiliations.append(p.affiliation)
        return Counter(all_affiliations).most_common(n)

    def secondary_topic_network(self) -> pd.DataFrame:
        """Co-occurrence of secondary topics."""
        pairs = []
        for s in self.sessions:
            topics = sorted(s.secondary_topics)
            for i, t1 in enumerate(topics):
                for t2 in topics[i + 1 :]:
                    pairs.append({"topic_1": t1, "topic_2": t2})
        if not pairs:
            return pd.DataFrame(columns=["topic_1", "topic_2", "count"])
        return (
            pd.DataFrame(pairs)
            .groupby(["topic_1", "topic_2"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )

    def save_report(self, output_dir: Path) -> None:
        """Save analysis outputs to files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(output_dir / "sessions.csv", index=False)
        self.topic_trends().to_csv(output_dir / "topic_trends.csv", index=False)
        self.secondary_topic_network().to_csv(output_dir / "topic_cooccurrence.csv", index=False)

        # Summary as JSON
        import json

        (output_dir / "summary.json").write_text(
            json.dumps(self.summary(), indent=2, ensure_ascii=False)
        )
