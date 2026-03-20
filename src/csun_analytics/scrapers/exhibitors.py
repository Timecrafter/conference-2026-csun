"""Scraper for CSUN conference exhibitors."""

import logging
import re
from pathlib import Path

from tqdm import tqdm

from csun_analytics.models.exhibitor import Exhibitor
from csun_analytics.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

EXHIBITOR_BASE_URLS = {
    2024: "https://www.csun.edu/cod/conference/ebb/rbk/2024/index.php",
}

EXHIBITORS_LIST_PATH = "/public/exhibitors/"
EXHIBITOR_DETAIL_PATH = "/public/exhibitors/view/{exhibitor_id}"


class ExhibitorScraper(BaseScraper):
    """Scrapes exhibitor data from CSUN conference website."""

    def __init__(self, year: int = 2024, **kwargs):
        super().__init__(**kwargs)
        self.year = year
        if year not in EXHIBITOR_BASE_URLS:
            raise ValueError(f"Year {year} not supported. Available: {list(EXHIBITOR_BASE_URLS.keys())}")
        self.base_url = EXHIBITOR_BASE_URLS[year]

    def get_exhibitor_list(self) -> list[dict]:
        """Get all exhibitors from paginated listing."""
        exhibitors = []
        page = 1

        while True:
            url = self.base_url + EXHIBITORS_LIST_PATH
            if page > 1:
                url += f"?page={page}"

            soup = self.fetch(url, use_cache=(page == 1))

            # Find exhibitor links and booth numbers
            found_any = False
            for link in soup.find_all("a", href=True):
                href = link["href"]
                match = re.search(r"/exhibitors/view/(\d+)", href)
                if match:
                    found_any = True
                    exhibitors.append({
                        "id": int(match.group(1)),
                        "name": link.get_text(strip=True),
                    })

            if not found_any:
                break

            # Check for next page
            next_link = soup.find("a", string=re.compile(r"Next|›|>>"))
            if not next_link:
                # Also check by page number
                page_links = soup.find_all("a", href=re.compile(r"page=\d+"))
                has_next = any(f"page={page + 1}" in a["href"] for a in page_links)
                if not has_next:
                    break

            page += 1
            if page > 20:  # Safety limit
                break

        logger.info(f"Found {len(exhibitors)} exhibitors for {self.year}")
        return exhibitors

    def scrape_exhibitor(self, exhibitor_id: int, name: str = "") -> Exhibitor:
        """Scrape a single exhibitor detail page."""
        url = self.base_url + EXHIBITOR_DETAIL_PATH.format(exhibitor_id=exhibitor_id)
        soup = self.fetch(url)

        exhibitor = Exhibitor(exhibitor_id=exhibitor_id, name=name, year=self.year)

        # Title: second <h1> on page (first is site-wide "California State University, Northridge")
        h1_tags = soup.find_all("h1")
        for h1 in h1_tags:
            h1_text = h1.get_text(strip=True)
            if "california state" not in h1_text.lower() and h1_text:
                exhibitor.name = h1_text
                break

        # The exhibitor detail page has labeled sections in flat text:
        # "Description...", "Website...", "Categories...", "Booth..."
        text = soup.get_text()

        # Parse booth numbers
        booth_match = re.findall(r"Booth[:\s#]*(\d+(?:\s*[,&]\s*\d+)*)", text, re.IGNORECASE)
        if booth_match:
            for bm in booth_match:
                exhibitor.booth_numbers.extend(
                    [b.strip() for b in re.split(r"[,&]", bm)]
                )

        # Description: text between "Description" label and "Categories" or "Back to"
        desc_match = re.search(
            r"Description\s*(.+?)(?:Categories|Back to Exhibitor)",
            text, re.DOTALL,
        )
        if desc_match:
            exhibitor.description = desc_match.group(1).strip()

        # Categories: newline-separated in the HTML
        cat_match = re.search(
            r"Categories\s*(.+?)(?:Back to Exhibitor|$)",
            text, re.DOTALL,
        )
        if cat_match:
            cat_text = cat_match.group(1).strip()
            # Split on newlines since categories are one per line, not comma-separated
            exhibitor.categories = [
                c.strip() for c in re.split(r"[\n,]", cat_text) if c.strip()
            ]

        # Website: link labeled with http that isn't csun.edu
        for link in soup.find_all("a", href=True):
            href = link["href"]
            link_text = link.get_text(strip=True)
            if href.startswith("http") and "csun.edu" not in href:
                exhibitor.website = href
                break

        return exhibitor

    def scrape_all_exhibitors(self) -> list[Exhibitor]:
        """Scrape all exhibitor details."""
        listing = self.get_exhibitor_list()

        exhibitors = []
        for item in tqdm(listing, desc=f"Scraping {self.year} exhibitors"):
            try:
                exhibitor = self.scrape_exhibitor(item["id"], item.get("name", ""))
                exhibitors.append(exhibitor)
            except Exception as e:
                logger.warning(f"Failed to scrape exhibitor {item['id']}: {e}")

        logger.info(f"Scraped {len(exhibitors)} exhibitors for {self.year}")
        return exhibitors
