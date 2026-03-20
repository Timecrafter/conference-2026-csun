"""Speaker data analysis for Cvent-sourced data."""

import json
from collections import Counter
from pathlib import Path

import pandas as pd


class SpeakerAnalyzer:
    """Analyze speaker data from Cvent API."""

    def __init__(self, speakers_path: Path):
        self.speakers = json.loads(speakers_path.read_text())
        self.df = pd.DataFrame(self.speakers)

    def summary(self) -> dict:
        return {
            "total_speakers": len(self.speakers),
            "unique_companies": self.df["company"].nunique(),
            "with_title": int((self.df["title"] != "").sum()),
            "with_biography": int((self.df["biography"] != "").sum()),
            "with_linkedin": int((self.df["linkedin_url"] != "").sum()),
        }

    def top_companies(self, n: int = 30) -> list[tuple[str, int]]:
        companies = [sp["company"] for sp in self.speakers if sp.get("company")]
        return Counter(companies).most_common(n)

    def company_sectors(self) -> dict[str, list[str]]:
        """Group companies into rough sectors based on known names."""
        tech_giants = {"Google", "Microsoft", "Amazon", "Apple, Inc", "Meta", "Apple"}
        enterprise = {"Salesforce", "Oracle", "SAP", "IBM", "Cisco"}
        at_vendors = {"Vispero", "Be My Eyes", "NewHaptics", "Aira"}
        a11y_firms = {"Deque", "Level Access", "AudioEye", "TPGi", "Accessibility Partners"}

        sectors = {"Tech Giants": [], "Enterprise": [], "AT Vendors": [], "A11y Firms": [],
                   "Education": [], "Other": []}

        for sp in self.speakers:
            company = sp.get("company", "")
            if not company:
                continue
            if company in tech_giants:
                sectors["Tech Giants"].append(sp["name"])
            elif company in enterprise:
                sectors["Enterprise"].append(sp["name"])
            elif company in at_vendors:
                sectors["AT Vendors"].append(sp["name"])
            elif company in a11y_firms:
                sectors["A11y Firms"].append(sp["name"])
            elif any(kw in company.lower() for kw in ["university", "college", "school"]):
                sectors["Education"].append(sp["name"])
            else:
                sectors["Other"].append(sp["name"])

        return {k: v for k, v in sectors.items() if v}

    def title_keywords(self, n: int = 30) -> list[tuple[str, int]]:
        """Most common words in speaker titles (job titles)."""
        import re
        stop = {"and", "the", "of", "for", "in", "at", "a", "an", "to", "-", "&", "/"}
        words = []
        for sp in self.speakers:
            title = sp.get("title", "")
            if title:
                tokens = re.findall(r"\b\w+\b", title.lower())
                words.extend(t for t in tokens if t not in stop and len(t) > 2)
        return Counter(words).most_common(n)

    def save_report(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(output_dir / "speakers.csv", index=False)

        summary = self.summary()
        summary["top_companies"] = self.top_companies()
        summary["title_keywords"] = self.title_keywords()

        (output_dir / "speaker_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False)
        )
