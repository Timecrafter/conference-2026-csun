"""Scraper for CSUN conference sessions from csun.edu.

The session detail pages use a consistent HTML structure:
- Title: second <h1> on the page (inside .presentations div)
- Fields: <dl> with <dt> labels and <dd> values
- Presenters: <h2>Presenter</h2> followed by <ul><li>Name<br>Affiliation</li></ul>
"""

import logging
import re
from pathlib import Path

from tqdm import tqdm

from csun_analytics.models.session import Presenter, Session
from csun_analytics.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# URL patterns for CSUN session pages (2022-2024 confirmed)
BASE_URLS = {
    2024: "https://www.csun.edu/cod/conference/sessions/index.php",
    2023: "https://www.csun.edu/cod/conference/sessions/2023/index.php",
    # 2022: 404 as of March 2026
}

SESSIONS_LIST_PATH = "/public/conf_sessions/"
SESSION_DETAIL_PATH = "/public/presentations/view/{session_id}"


class SessionScraper(BaseScraper):
    """Scrapes session data from CSUN conference website."""

    def __init__(self, year: int = 2024, **kwargs):
        super().__init__(**kwargs)
        self.year = year
        if year not in BASE_URLS:
            raise ValueError(f"Year {year} not supported. Available: {list(BASE_URLS.keys())}")
        self.base_url = BASE_URLS[year]

    def get_session_ids(self) -> list[int]:
        """Get all session IDs from the session listing page."""
        url = self.base_url + SESSIONS_LIST_PATH
        soup = self.fetch(url)

        session_ids = set()
        for link in soup.find_all("a", href=True):
            href = link["href"]
            match = re.search(r"/presentations/view/(\d+)", href)
            if match:
                session_ids.add(int(match.group(1)))

        logger.info(f"Found {len(session_ids)} session IDs for {self.year}")
        return sorted(session_ids)

    def scrape_session(self, session_id: int) -> Session:
        """Scrape a single session detail page."""
        url = self.base_url + SESSION_DETAIL_PATH.format(session_id=session_id)
        soup = self.fetch(url)

        # Find the presentation content div
        content_div = soup.find("div", class_="presentations")
        if not content_div:
            content_div = soup  # fallback

        # Title: the h1 inside the presentations div (not the site-wide h1)
        title = ""
        h1_tags = content_div.find_all("h1")
        for h1 in h1_tags:
            h1_text = h1.get_text(strip=True)
            # Skip the "Conference Has Concluded" banner
            if "concluded" not in h1_text.lower() and "annual" not in h1_text.lower():
                title = h1_text
                break

        if not title:
            raise ValueError(f"No title found for session {session_id}")

        session = Session(session_id=session_id, title=title, year=self.year)

        # Parse dt/dd pairs from the definition list
        self._parse_dl_fields(content_div, session)
        self._parse_presenters(content_div, session)

        return session

    def _parse_dl_fields(self, content_div, session: Session) -> None:
        """Extract fields from <dl><dt>Label</dt><dd>Value</dd></dl> structure."""
        for dt in content_div.find_all("dt"):
            label = dt.get_text(strip=True)
            dd = dt.find_next_sibling("dd")
            if not dd:
                continue
            value = dd.get_text(strip=True)

            if label == "Date & Time":
                # Parse "Wednesday, March 20, 2024 - 2:20 PM PDT"
                date_match = re.match(r"(.+\d{4})\s*-\s*(.+)", value)
                if date_match:
                    session.date = date_match.group(1).strip()
                    session.time = date_match.group(2).strip()
                else:
                    session.date = value
            elif label == "Location":
                session.location = value
            elif label == "Description":
                session.description = value
            elif label == "Session Summary (Abstract)":
                session.abstract = value
            elif label == "Primary Topic":
                session.primary_topic = value
            elif label == "Secondary Topics":
                # Items are in <ul><li> inside the dd
                items = dd.find_all("li")
                if items:
                    session.secondary_topics = [li.get_text(strip=True) for li in items]
                else:
                    session.secondary_topics = [t.strip() for t in value.split(",") if t.strip()]
            elif label == "Audience Level":
                session.audience_level = value
            elif label == "Audience":
                items = dd.find_all("li")
                if items:
                    session.target_audiences = [li.get_text(strip=True) for li in items]
                else:
                    session.target_audiences = [t.strip() for t in value.split(",") if t.strip()]
            elif label == "Session Type":
                session.track = value

    def _parse_presenters(self, content_div, session: Session) -> None:
        """Extract presenters from <h2>Presenter</h2> <ul><li>Name<br>Affiliation</li></ul>."""
        presenter_heading = None
        for h2 in content_div.find_all("h2"):
            if "presenter" in h2.get_text(strip=True).lower():
                presenter_heading = h2
                break

        if not presenter_heading:
            return

        # The <ul> follows the heading
        ul = presenter_heading.find_next("ul")
        if not ul:
            return

        for li in ul.find_all("li"):
            # Structure: Name<br/>Affiliation
            # Use .contents to split on <br>
            parts = []
            for child in li.children:
                if hasattr(child, "name") and child.name == "br":
                    parts.append("")  # separator
                else:
                    text = child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
                    if text:
                        if parts and parts[-1] == "":
                            parts[-1] = text
                        else:
                            parts.append(text)

            name = parts[0] if parts else li.get_text(strip=True)
            affiliation = parts[1] if len(parts) > 1 else None

            if name:
                session.presenters.append(Presenter(name=name, affiliation=affiliation))

    def scrape_all_sessions(self, max_sessions: int | None = None) -> list[Session]:
        """Scrape all sessions for the configured year."""
        session_ids = self.get_session_ids()
        if max_sessions:
            session_ids = session_ids[:max_sessions]

        sessions = []
        for sid in tqdm(session_ids, desc=f"Scraping {self.year} sessions"):
            try:
                session = self.scrape_session(sid)
                sessions.append(session)
            except Exception as e:
                logger.warning(f"Failed to scrape session {sid}: {e}")

        logger.info(f"Scraped {len(sessions)} sessions for {self.year}")
        return sessions

    def find_papers(self, sessions: list[Session], download_dir: Path | None = None) -> None:
        """Check for linked papers/slides and optionally download them."""
        download_dir = download_dir or Path(f"data/raw/papers/{self.year}")

        for session in tqdm(sessions, desc="Checking for papers"):
            url = self.base_url + SESSION_DETAIL_PATH.format(session_id=session.session_id)
            soup = self.fetch(url)

            for link in soup.find_all("a", href=True):
                href = link["href"]
                if any(ext in href.lower() for ext in [".pdf", ".pptx", ".ppt", ".docx"]):
                    if not href.startswith("http"):
                        href = self.base_url.rsplit("/", 1)[0] + "/" + href.lstrip("/")
                    session.paper_url = href
                    try:
                        filename = href.split("/")[-1]
                        dest = download_dir / filename
                        self.download_file(href, dest)
                        session.paper_local_path = str(dest)
                    except Exception as e:
                        logger.warning(
                            f"Failed to download paper for session {session.session_id}: {e}"
                        )
