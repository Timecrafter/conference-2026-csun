# CSUN Assistive Technology Conference Analytics

## Project Overview
Analytics toolkit for scraping and analyzing data from the CSUN Assistive Technology Conference (the world's largest assistive technology conference, held annually in Anaheim, CA).

## Tech Stack
- **Python 3.12** with `uv` for package management and `hatchling` as build backend
- **Scraping**: `requests` + `beautifulsoup4` + `lxml` (static pages), `playwright` (for Cvent JS SPA)
- **Analysis**: `pandas`, `networkx`, `matplotlib`, `seaborn`
- **Visualization**: `plotly` for charts, `dash` + `dash-bootstrap-components` for dashboard
- **AI**: `anthropic` SDK for Claude-powered topic normalization
- **Documentation**: `mkdocs` + `mkdocs-material` for static site
- **CLI**: `rich` for terminal output, `tqdm` for progress bars

## Setup
```bash
make setup        # Creates venv, installs deps, creates .env.local
make env-check    # Verify everything is working
```

Or manually:
```bash
uv venv --python 3.12 && uv sync --all-extras
cp .env.example .env.local  # Add your ANTHROPIC_API_KEY
```

## Project Structure
```
src/csun_analytics/
├── data.py              # Shared data loading layer (cached)
├── models/              # Dataclasses: Session, Presenter, Exhibitor, Sponsor
├── scrapers/
│   ├── base.py          # BaseScraper with caching, rate limiting
│   ├── sessions.py      # SessionScraper for csun.edu (2023-2024)
│   ├── cvent.py         # CventScraper for conference.csun.at (2025-2026)
│   ├── exhibitors.py
│   └── sponsors.py
├── analysis/
│   ├── sessions.py      # Topic trends, presenter networks, affiliation analysis
│   ├── speakers.py      # Speaker analysis for Cvent data
│   ├── exhibitors.py
│   ├── comprehensive.py # Full multi-year analysis (auto-applies topic normalization)
│   ├── knowledge_graph.py # Knowledge graph builder (TF-IDF, topic/org overlap)
│   ├── graph_builder.py # NetworkX graph operations, layouts, centrality
│   └── normalize.py     # LLM-based topic taxonomy (Claude API)
├── viz/
│   ├── charts.py        # Plotly figure builders (10 chart types)
│   ├── colors.py        # Color palettes and theme
│   └── export.py        # Export to HTML/PNG/standalone
├── dashboard/
│   ├── app.py           # Dash app factory
│   └── pages/           # Multi-page dashboard (overview, topics, orgs, knowledge graph)
└── docs_builder.py      # MkDocs page + chart generator

docs/                    # Generated mkdocs source pages
site/                    # Built static site (mkdocs build output)
data/
├── raw/                 # Scraped JSON + cached HTML + speakers + brochures
└── processed/           # Analysis JSONs, reports, topic_taxonomy.json, knowledge graphs
```

## Key Commands
```bash
# Via Makefile (recommended)
make help              # Show all targets
make setup             # First-time install
make scrape YEAR=2026  # Scrape sessions
make comprehensive     # Full multi-year analysis
make pipeline          # Analysis + knowledge graph
make dashboard         # Launch Dash app (http://localhost:8050)
make docs              # Build + serve docs (http://localhost:8000)
make normalize-force   # Re-generate taxonomy via Claude API

# Or directly via uv
uv run python main.py scrape-sessions --year all
uv run python main.py comprehensive
uv run python main.py dashboard --port 8050
uv run python main.py docs --serve
```

## Data Availability
| Year | Sessions | Speakers | Exhibitors | Source |
|------|----------|----------|------------|--------|
| 2026 | 359 | 514 | (behind auth) | Cvent GraphQL + API snapshot |
| 2025 | 342 | 473 | (behind auth) | Cvent GraphQL + API snapshot |
| 2024 | 329 | (in sessions) | 126 | csun.edu |
| 2023 | 316 | (in sessions) | TBD | csun.edu |
| 2022 | 404 error | - | - | csun.edu (offline) |

## Data Sources
- **Sessions (2023-2024)**: `csun.edu/cod/conference/sessions/{year}/index.php`
- **Sessions (2025-2026)**: Cvent public GraphQL at `conference.csun.at/event/graphql`
- **Speakers (2025-2026)**: Cvent snapshot API at `/event_guest/v1/snapshot/{event_id}/event`
- **Exhibitors (2024)**: `csun.edu/cod/conference/ebb/rbk/2024/index.php/public/exhibitors/`
- **Topic taxonomy**: `data/processed/topic_taxonomy.json` (29 canonical topics from 48 variants)

## Key Findings
- 1,346 sessions across 4 years (2023-2026), steady 4-5% annual growth
- AI/ML sessions: 29→39→48→51 from 2023→2026 (76% growth)
- Digital Accessibility dominates at ~30% of all sessions
- 29 canonical topics after LLM normalization (was 48 inconsistent variants)
- Top presenting orgs: Amazon, Google, Microsoft, Vispero, TPGi
- 32 presenters appeared in all 4 years

## Conventions
- Rate limit: 1 second between requests
- Cache HTML in `data/raw/html_cache/`
- JSON for raw data, CSV for processed/analysis outputs
- Topic normalization applied automatically by comprehensive analysis
- 2022 sessions are offline (404)
- Cvent PDFs require attendee login (follow-up task pending)
