"""Scraper for CSUN conference sponsor data from brochure PDFs and web pages."""

import logging
import re
from pathlib import Path

from csun_analytics.models.sponsor import Sponsor
from csun_analytics.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Known sponsor brochure PDFs
BROCHURE_URLS = {
    2026: "https://custom.cvent.com/fd39d9c54ee64289b55890d53a01ea94/files/e767f5b75a3b4f1cbb275c82f9cbb752.pdf",
}

EXHIBITOR_BROCHURE_URLS = {
    2026: "https://custom.cvent.com/fd39d9c54ee64289b55890d53a01ea94/files/3edaaf678705405aad970e6da4730cd8.pdf",
}


class SponsorScraper(BaseScraper):
    """Scrapes sponsor information from CSUN conference."""

    def __init__(self, year: int = 2026, **kwargs):
        super().__init__(**kwargs)
        self.year = year

    def download_brochures(self, output_dir: Path | None = None) -> list[Path]:
        """Download available sponsor/exhibitor brochures."""
        output_dir = output_dir or Path(f"data/raw/brochures/{self.year}")
        downloaded = []

        if self.year in BROCHURE_URLS:
            path = self.download_file(
                BROCHURE_URLS[self.year],
                output_dir / f"sponsorship_brochure_{self.year}.pdf",
            )
            downloaded.append(path)

        if self.year in EXHIBITOR_BROCHURE_URLS:
            path = self.download_file(
                EXHIBITOR_BROCHURE_URLS[self.year],
                output_dir / f"exhibitor_brochure_{self.year}.pdf",
            )
            downloaded.append(path)

        return downloaded

    def scrape_sponsors_from_page(self, url: str) -> list[Sponsor]:
        """Extract sponsor names from a conference page (e.g., Cvent summary)."""
        soup = self.fetch(url)
        sponsors = []

        # Look for sponsor sections
        text = soup.get_text()
        tier_patterns = [
            (r"(?i)platinum\s*sponsors?", "Platinum"),
            (r"(?i)gold\s*sponsors?", "Gold"),
            (r"(?i)silver\s*sponsors?", "Silver"),
            (r"(?i)bronze\s*sponsors?", "Bronze"),
            (r"(?i)sponsors?", "Sponsor"),
        ]

        for pattern, tier in tier_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                # Try to extract names near the tier heading
                after_text = text[match.end():match.end() + 500]
                lines = [l.strip() for l in after_text.split("\n") if l.strip()]
                for line in lines[:10]:
                    if len(line) > 3 and len(line) < 100:
                        if not re.match(r"(?i)(sponsor|exhibitor|partner|more|learn|view)", line):
                            sponsors.append(Sponsor(name=line, tier=tier, year=self.year))

        return sponsors
