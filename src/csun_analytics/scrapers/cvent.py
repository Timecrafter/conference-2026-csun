"""Scraper for CSUN conferences hosted on Cvent (2025, 2026).

The Cvent public API provides:
- Sessions (359 for 2026): titles, descriptions, speakers, topics, audience levels
  via GraphQL endpoint at /event/graphql (Sessions query)
- Speakers (514 for 2026): names, companies, titles, bios, categories
  via event snapshot API
- Event metadata: dates, location, registration types

Session data is available through the public GraphQL API used by the Session Schedule
page widget. The GraphQL Sessions query supports pagination (limit/token).
"""

import json
import logging
import time
from pathlib import Path

import requests

from csun_analytics.models.session import Presenter, Session
from csun_analytics.models.exhibitor import Exhibitor

logger = logging.getLogger(__name__)

CVENT_EVENTS = {
    2026: {
        "event_id": "19ed8807-7bb5-4840-861a-8fc9b048e17c",
        "base_url": "https://conference.csun.at",
        "snapshot_version": "llagirPbQfpGEpAL1wzTclwy8capXC9w",
        "account_snapshot_version": "WY3d95lazYHG0OV7xqJMs1Zqic9nT502",
    },
    2025: {
        "event_id": "2c5d8c51-6441-44c0-b361-131ff9544dd5",
        "base_url": "https://conference.csun.at",
        "snapshot_version": "Z_32mj.y3PNp3jiXuKB2pZym2Tt3nVDU",
        "account_snapshot_version": "WY3d95lazYHG0OV7xqJMs1Zqic9nT502",
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Session category IDs mapped to names (from 2026 account snapshot)
SESSION_CATEGORIES = {
    "e87d4a06-706c-4c6b-854c-0d204bf228ed": "General",
    "94e1481d-a063-43a6-b34c-903c6d518178": "Journal",
    "fbf525b1-f4cb-40cd-8140-8b706e3ecac1": "Exhibitor",
    "c0ef067e-8d3a-486f-ac73-093289c0924a": "Half-Day Workshops",
    "d7e0f95b-6f16-42a0-b657-f7d31e953cae": "Tuesday Pre-Conference Workshops",
    "8c3540a3-f003-40c4-95b2-5a3da40e2417": "Birds of a Feather",
    "4c53f2aa-05e7-4b3c-9e34-fa77cc5977b8": "Job Fair",
    "11a7c5c4-8efd-456c-aca4-72398086f047": "Social Event",
    "267f04d2-6b37-4865-a5b2-64ccd5467af7": "Wednesday Box Lunch",
    "d1047e7b-ad05-4d41-a60d-9609c97c228a": "Friday Box Lunch",
    "2766dd51-d843-445d-9d82-d11b923fafef": "Other",
}

# Speaker category IDs
SPEAKER_CATEGORIES = {
    "23350de5-c2c1-46ba-9af3-a12d9c351708": "Presenter",
    "420b4dc7-586e-48c2-ab7c-6ece7cb4f208": "Speaker",
    "54bfc835-ce15-4d9a-bc3f-58356a7bebdd": "Keynote Speaker",
    "fea5eda4-1e83-4a38-96e6-50b2b2aad65d": "Panelist",
    "214602c9-7097-43fc-bf21-bf1e416fcb6b": "Host",
    "5e21d1c2-3297-4c11-8e94-c9b84bb46ef0": "Moderator",
}


SESSIONS_GRAPHQL_QUERY = """\
fragment CoreSessionFields on Session {
  id
  locale
  __typename
}

query Sessions($eventId: ID!, $environment: String!, $eventSnapshotVersion: String!, $accountSnapshotVersion: String, $regTypeId: String, $token: String, $limit: Int, $sort: String, $filter: FilterDsl, $timezone: String, $sessionCustomFieldsFilter: [SessionCustomFieldsFilter], $limitByEmptyRegistration: Boolean, $locale: String, $resolveAccountTranslations: Boolean) {
  event(
    input: {eventId: $eventId, environment: $environment, eventSnapshotVersion: $eventSnapshotVersion, accountSnapshotVersion: $accountSnapshotVersion, timezone: $timezone, cultureCode: $locale}
  ) {
    id
    sessions(
      token: $token
      limit: $limit
      regTypeId: $regTypeId
      sort: $sort
      filter: $filter
      sessionCustomFieldsFilter: $sessionCustomFieldsFilter
      limitByEmptyRegistration: $limitByEmptyRegistration
      locale: $locale
    ) {
      data {
        ...CoreSessionFields
        name
        startDateTime
        endDateTime
        startTimeOnly
        startDateOnly
        showOnAgenda
        code
        presentationType
        categoryId
        category { id name description __typename }
        sessionLocation { id locationName locationCode __typename }
        description
        speakerIds { id sessionSpeakerOrder __typename }
        speakers {
          id prefix firstName lastName company title
          linkedInUrl twitterUrl biography
          contentTags { id contentTagText __typename }
          __typename
        }
        contentTags { id contentTagText __typename }
        isWaitlistEnabled
        sessionCustomFieldIds
        sessionCustomFieldQuestions(resolveAccountTranslations: $resolveAccountTranslations) {
          question { code id text translatedText(resolveAccountTranslations: $resolveAccountTranslations) __typename }
          __typename
        }
        sessionCustomFieldValues {
          id sessionId displayValue answers
          translatedDisplayValue(resolveAccountTranslations: $resolveAccountTranslations)
          __typename
        }
        __typename
      }
      paginationMetadata {
        currentToken nextToken previousToken limit totalCount __typename
      }
      __typename
    }
    __typename
  }
}
"""


class CventScraper:
    """Scrapes Cvent-hosted CSUN conference data using the public API.

    The public event snapshot API provides speaker data without authentication.
    Session data requires attendee login through the Cvent hub.
    """

    def __init__(self, year: int, cache_dir: Path | None = None):
        if year not in CVENT_EVENTS:
            raise ValueError(f"Year {year} not supported. Available: {list(CVENT_EVENTS.keys())}")
        self.year = year
        self.config = CVENT_EVENTS[year]
        self.cache_dir = cache_dir or Path(f"data/raw/cvent_cache/{year}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _discover_snapshot_version(self) -> str | None:
        """Discover the snapshot version by fetching the event summary page."""
        if self.config["snapshot_version"]:
            return self.config["snapshot_version"]

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright needed to discover snapshot version for this year")
            return None

        snapshot_version = None
        base = self.config["base_url"]
        event_id = self.config["event_id"]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            def capture_snapshot(response):
                nonlocal snapshot_version
                if "snapshot" in response.url and "snapshotVersion=" in response.url:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(response.url)
                    params = urllib.parse.parse_qs(parsed.query)
                    if "snapshotVersion" in params:
                        snapshot_version = params["snapshotVersion"][0]

            page.on("response", capture_snapshot)
            try:
                page.goto(
                    f"{base}/event/{event_id}/summary",
                    timeout=30000, wait_until="networkidle",
                )
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Failed to discover snapshot version: {e}")
            browser.close()

        if snapshot_version:
            self.config["snapshot_version"] = snapshot_version
            logger.info(f"Discovered snapshot version: {snapshot_version}")
        return snapshot_version

    def fetch_speakers(self) -> list[Presenter]:
        """Fetch all speakers from the public event snapshot API."""
        snapshot_version = self.config["snapshot_version"]
        if not snapshot_version:
            snapshot_version = self._discover_snapshot_version()
        if not snapshot_version:
            logger.error("Cannot fetch speakers without snapshot version")
            return []

        event_id = self.config["event_id"]
        base = self.config["base_url"]
        url = (
            f"{base}/event_guest/v1/snapshot/{event_id}/event"
            f"?snapshotVersion={snapshot_version}"
            f"&registrationTypeId=00000000-0000-0000-0000-000000000000"
        )

        cache_path = self.cache_dir / "event_snapshot_full.json"
        if cache_path.exists():
            logger.info("Using cached event snapshot")
            data = json.loads(cache_path.read_text())
        else:
            logger.info(f"Fetching event snapshot from Cvent API...")
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            cache_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        speakers_data = data.get("speakerInfoSnapshot", {}).get("speakers", {})
        logger.info(f"Found {len(speakers_data)} speakers for {self.year}")

        presenters = []
        for sid, sp in speakers_data.items():
            category_id = sp.get("categoryId", "")
            role = SPEAKER_CATEGORIES.get(category_id, "")

            presenters.append(Presenter(
                name=f"{sp.get('firstName', '')} {sp.get('lastName', '')}".strip(),
                affiliation=sp.get("company", None) or None,
                role=role,
            ))

        return presenters

    def scrape_sessions(self) -> list[Session]:
        """Fetch all sessions via the Cvent public GraphQL API.

        Uses the same Sessions query that the Session Schedule page widget uses.
        Supports pagination to retrieve all sessions.
        """
        cache_path = self.cache_dir / "sessions_graphql.json"
        if cache_path.exists():
            logger.info("Using cached GraphQL session data")
            raw_sessions = json.loads(cache_path.read_text())
        else:
            raw_sessions = self._fetch_sessions_graphql()
            cache_path.write_text(json.dumps(raw_sessions, indent=2, ensure_ascii=False))

        sessions = [self._convert_graphql_session(s) for s in raw_sessions]
        logger.info(f"Loaded {len(sessions)} sessions for {self.year}")
        return sessions

    def _fetch_sessions_graphql(self) -> list[dict]:
        """Fetch all sessions from the GraphQL endpoint with pagination."""
        snapshot_version = self.config["snapshot_version"]
        if not snapshot_version:
            snapshot_version = self._discover_snapshot_version()
        if not snapshot_version:
            logger.error("Cannot fetch sessions without snapshot version")
            return []

        event_id = self.config["event_id"]
        base = self.config["base_url"]
        graphql_url = f"{base}/event/graphql"

        # First, discover the current event snapshot version from the website
        # (the snapshot version can change over time)
        discovered_sv = self._get_current_snapshot_version()
        if discovered_sv:
            snapshot_version = discovered_sv

        all_sessions = []
        token = "0"
        page = 0

        while True:
            payload = [{
                "operationName": "Sessions",
                "variables": {
                    "regTypeId": None,
                    "token": token,
                    "limit": 100,
                    "sort": "startDateOnly:asc,startTimeOnly:asc,featuredSession:desc,displayPriority:desc,name:asc",
                    "filter": "showOnAgenda eq 1 and status ne 7",
                    "timezone": "4",
                    "sessionCustomFieldsFilter": [],
                    "limitByEmptyRegistration": True,
                    "locale": "en-US",
                    "resolveAccountTranslations": True,
                    "eventId": event_id,
                    "environment": "",
                    "eventSnapshotVersion": snapshot_version,
                    "accountSnapshotVersion": self.config.get("account_snapshot_version", ""),
                },
                "query": SESSIONS_GRAPHQL_QUERY,
            }]

            resp = self.session.post(graphql_url, json=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()

            for r in result:
                sessions_data = r.get("data", {}).get("event", {}).get("sessions", {})
                if sessions_data and "data" in sessions_data:
                    batch = sessions_data["data"]
                    pm = sessions_data.get("paginationMetadata", {})
                    all_sessions.extend(batch)

                    total = pm.get("totalCount", "?")
                    next_token = pm.get("nextToken")
                    logger.info(f"Page {page}: got {len(batch)} sessions ({len(all_sessions)}/{total})")

                    if next_token and len(batch) > 0:
                        token = next_token
                    else:
                        token = None
                    break

            if token is None:
                break
            page += 1
            if page > 20:
                break

        return all_sessions

    def _get_current_snapshot_version(self) -> str | None:
        """Fetch the current event snapshot version from the event page."""
        event_id = self.config["event_id"]
        base = self.config["base_url"]
        try:
            url = (
                f"{base}/event_guest/v1/snapshot/{event_id}/event"
                f"?snapshotVersion={self.config['snapshot_version']}"
                f"&registrationTypeId=00000000-0000-0000-0000-000000000000"
            )
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                sv = data.get("snapshotVersion")
                if sv and sv != self.config["snapshot_version"]:
                    logger.info(f"Discovered updated snapshot version: {sv}")
                    return sv
        except Exception:
            pass
        return None

    def _convert_graphql_session(self, s: dict) -> Session:
        """Convert a GraphQL session response to our Session model."""
        import re
        from html import unescape

        def strip_html(html_str):
            if not html_str:
                return ""
            text = re.sub(r"<[^>]+>", "", html_str)
            text = unescape(text)
            return re.sub(r"\s+", " ", text).strip()

        # Parse custom fields
        FIELD_MAP = {
            "38204dff-307c-4238-87bc-50615c84e8df": "Audience Level",
            "0ab703ad-405c-4c31-8743-0ac127df3930": "Topics",
            "594074e6-be75-419b-b33d-8e9c3f8eb6a1": "Audience",
            "6bad6d8f-0464-4b22-9cce-fb5a6c628b28": "Learning Objective 2",
            "8d7d7ad4-a35a-4221-8817-47a40c236260": "Learning Objective 3",
        }
        cf = {}
        for v in s.get("sessionCustomFieldValues", []):
            field_name = FIELD_MAP.get(v.get("id", ""), v.get("id", ""))
            answers = v.get("answers", [])
            display = v.get("displayValue", "")
            if answers and answers != [""]:
                cf[field_name] = answers
            elif display:
                cf[field_name] = [a.strip() for a in display.split(",")]

        # Presenters
        presenters = [
            Presenter(
                name=f"{sp.get('firstName', '')} {sp.get('lastName', '')}".strip(),
                affiliation=sp.get("company", "") or None,
                role=sp.get("title", "") or None,
            )
            for sp in s.get("speakers", [])
        ]

        topics = cf.get("Topics", [])

        # Time: UTC to PT (PDT is UTC-7 in March)
        time_str = s.get("startTimeOnly", "")
        if time_str:
            parts = time_str.split(":")
            if len(parts) >= 2:
                hour = int(parts[0]) - 7
                if hour < 0:
                    hour += 24
                time_str = f"{hour:02d}:{parts[1]}"

        loc = s.get("sessionLocation") or {}
        objectives = []
        for key in ["Learning Objective 2", "Learning Objective 3"]:
            if key in cf:
                objectives.extend(cf[key])

        return Session(
            session_id=s["id"],
            title=s.get("name", ""),
            presenters=presenters,
            description=strip_html(s.get("description", "")),
            track=s.get("presentationType", "") or s.get("code", ""),
            primary_topic=topics[0] if topics else "",
            secondary_topics=topics[1:] if len(topics) > 1 else [],
            audience_level=(cf.get("Audience Level", [""])[0]
                          if cf.get("Audience Level") else ""),
            target_audiences=cf.get("Audience", []),
            date=s.get("startDateOnly", ""),
            time=time_str,
            location=loc.get("locationName", ""),
            year=self.year,
            content_tags=[t.get("text", "") for t in s.get("contentTags", []) if t.get("text")],
            learning_objectives=objectives,
            start_datetime_utc=s.get("startDateTime", ""),
            end_datetime_utc=s.get("endDateTime", ""),
        )

    def fetch_session_categories(self) -> dict:
        """Fetch session category definitions."""
        snapshot_version = self.config.get("account_snapshot_version")
        if not snapshot_version:
            return SESSION_CATEGORIES

        event_id = self.config["event_id"]
        base = self.config["base_url"]
        url = (
            f"{base}/event_guest/v1/snapshot/{event_id}/account"
            f"?snapshotVersion={snapshot_version}"
            f"&eventSnapshotVersion={self.config['snapshot_version']}"
        )

        cache_path = self.cache_dir / "account_snapshot.json"
        if cache_path.exists():
            data = json.loads(cache_path.read_text())
        else:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            cache_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        categories = {}
        for cat_id, cat in data.get("sessionCategories", {}).items():
            categories[cat_id] = cat.get("name", "")

        return categories

    def scrape_exhibitors(self) -> list[Exhibitor]:
        """Exhibitor data also requires auth on Cvent. Returns empty list."""
        logger.info("Exhibitor data requires Cvent attendee login.")
        return []

