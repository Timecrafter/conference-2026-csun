# Methodology

## Data Collection

### 2023-2024: HTML Scraping
Sessions scraped from `csun.edu/cod/conference/sessions/{year}/index.php` using
`requests` + `beautifulsoup4`. HTML uses `<dl><dt><dd>` structure for fields.

### 2025-2026: Cvent GraphQL API
Sessions fetched from Cvent's public GraphQL endpoint at `conference.csun.at/event/graphql`.
The `Sessions` query returns full session data with pagination (100 per page), including
custom fields for topics, audience level, and learning objectives.

Speaker data from the Cvent event snapshot API at `/event_guest/v1/snapshot/{event_id}/event`.

## Topic Normalization

Topics are normalized using Claude (Anthropic API) to handle naming inconsistencies:
- 2023-2024 use `&` (e.g., "AI & ML")
- 2025-2026 use `and` (e.g., "AI and ML")

The LLM creates a canonical taxonomy mapping all variants to standard names.

## Knowledge Graph

Session connections are computed via 6 edge types:
1. **Topic overlap** — shared primary/secondary topics
2. **Organization overlap** — shared presenter affiliations
3. **Keyword similarity** — TF-IDF cosine similarity of descriptions
4. **Audience overlap** — shared target audiences
5. **Co-presenter** — same person presenting multiple sessions
6. **Temporal proximity** — sessions on the same day (2026 only)

Edge weights are combined across types. The topic community graph aggregates
sessions by topic, with edges representing the total connection weight between
topic groups.

## Tools

- **Python 3.12** with `uv` package manager
- **Scraping**: requests, beautifulsoup4, playwright
- **Analysis**: pandas, networkx
- **Visualization**: plotly, dash
- **AI**: anthropic SDK (Claude) for topic normalization
- **Documentation**: mkdocs with Material theme
