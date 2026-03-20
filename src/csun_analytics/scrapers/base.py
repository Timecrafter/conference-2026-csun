"""Base scraper with shared HTTP session and rate limiting."""

import time
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Be polite: seconds between requests
RATE_LIMIT = 1.0


class BaseScraper:
    """Base scraper with session management and rate limiting."""

    def __init__(self, cache_dir: Path | None = None, rate_limit: float = RATE_LIMIT):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.rate_limit = rate_limit
        self._last_request_time = 0.0
        self.cache_dir = cache_dir or Path("data/raw/html_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _wait(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

    def fetch(self, url: str, use_cache: bool = True) -> BeautifulSoup:
        cache_key = url.replace("https://", "").replace("http://", "").replace("/", "_")
        cache_path = self.cache_dir / f"{cache_key}.html"

        if use_cache and cache_path.exists():
            logger.debug(f"Cache hit: {url}")
            html = cache_path.read_text(encoding="utf-8")
            return BeautifulSoup(html, "lxml")

        self._wait()
        logger.info(f"Fetching: {url}")
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        self._last_request_time = time.time()

        cache_path.write_text(resp.text, encoding="utf-8")
        return BeautifulSoup(resp.text, "lxml")

    def download_file(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            logger.debug(f"Already downloaded: {dest}")
            return dest

        self._wait()
        logger.info(f"Downloading: {url} -> {dest}")
        resp = self.session.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        self._last_request_time = time.time()

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return dest
