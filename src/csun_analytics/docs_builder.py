"""MkDocs documentation site generator.

Reads analysis JSON data and generates markdown pages with embedded
Plotly HTML charts for the mkdocs documentation site.

Charts are embedded as inline HTML divs (using Plotly CDN) rather than
iframes, avoiding cross-origin and path resolution issues with mkdocs serve.
"""

import json
import shutil
from pathlib import Path

from csun_analytics.data import PROCESSED_DIR, YEARS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = PROJECT_ROOT / "docs"
ASSETS_DIR = DOCS_DIR / "assets" / "charts"

# Cache of generated chart HTML divs (name -> html string)
_CHART_DIVS: dict[str, str] = {}


def _load_analysis() -> tuple[dict, dict]:
    """Load pre-computed analysis JSON files."""
    with open(PROCESSED_DIR / "analysis_2026.json") as f:
        a2026 = json.load(f)
    with open(PROCESSED_DIR / "analysis_multi_year.json") as f:
        multi = json.load(f)
    return a2026, multi


def _embed_chart(name: str) -> str:
    """Return the inline HTML div for a chart, or a placeholder if not generated."""
    html = _CHART_DIVS.get(name, "")
    if not html:
        return f'\n<p><em>Chart "{name}" not available.</em></p>\n'
    return f"\n{html}\n"


# Keep alias for root-level pages (same behavior with inline divs)
_embed_chart_root = _embed_chart


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def generate_charts():
    """Generate all Plotly chart HTML divs (inline, CDN-based)."""
    a2026, multi = _load_analysis()

    from csun_analytics.viz.charts import (
        fig_sessions_per_year,
        fig_topic_distribution,
        fig_topic_trends_heatmap,
        fig_ai_growth,
        fig_org_bubble,
        fig_presenter_continuity,
        fig_audience_level_distribution,
        fig_sessions_by_day,
    )

    def _save(name: str, fig):
        """Convert figure to inline HTML div and cache it."""
        html = fig.to_html(full_html=False, include_plotlyjs="cdn", default_height="500px")
        _CHART_DIVS[name] = html
        # Also save standalone for direct viewing / dashboard export
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(ASSETS_DIR / f"{name}.html"), include_plotlyjs=True, full_html=True)

    # Sessions per year
    spy = multi["sessions_per_year"]
    spy_int = {int(k): v for k, v in spy.items()}
    _save("sessions_per_year", fig_sessions_per_year(spy_int))

    # Topic distribution 2026
    _save("topic_distribution_2026",
          fig_topic_distribution(a2026["primary_topic_distribution"], 2026))

    # Topic trends heatmap
    _save("topic_trends_heatmap",
          fig_topic_trends_heatmap(multi.get("primary_topic_trends", [])))

    # AI/ML growth
    ai_trend = multi.get("ai_ml_trend", {})
    ai_int = {int(k): v for k, v in ai_trend.items()}
    _save("ai_growth", fig_ai_growth(ai_int))

    # Organization bubble
    _save("org_bubble", fig_org_bubble(multi.get("organization_trends", [])))

    # Presenter continuity
    _save("presenter_continuity",
          fig_presenter_continuity(multi.get("presenter_continuity", {})))

    # Audience level 2026
    _save("audience_level_2026",
          fig_audience_level_distribution(a2026.get("audience_level_distribution", []), 2026))

    # Sessions by day 2026
    _save("sessions_by_day_2026",
          fig_sessions_by_day(a2026.get("sessions_per_day", [])))

    # Knowledge graph (topic community)
    try:
        from csun_analytics.analysis.graph_builder import (
            load_graph, topic_community_graph, graph_to_viz_data,
        )
        from csun_analytics.viz.charts import fig_topic_community

        kg_path = PROCESSED_DIR / "knowledge_graph_2026.json"
        if kg_path.exists():
            G = load_graph(kg_path)
            tg = topic_community_graph(G)
            viz_data = graph_to_viz_data(tg)
            _save("topic_community",
                  fig_topic_community(viz_data["nodes"], viz_data["edges"]))
    except Exception as e:
        print(f"  Warning: Could not generate knowledge graph chart: {e}")

    # Knowledge graph (ego graph around Putz)
    try:
        from csun_analytics.analysis.graph_builder import load_graph, graph_to_viz_data
        from csun_analytics.viz.charts import fig_topic_network

        kg_path = PROCESSED_DIR / "knowledge_graph_putz.json"
        if kg_path.exists():
            G = load_graph(kg_path)
            viz_data = graph_to_viz_data(G)
            _save("knowledge_graph_putz",
                  fig_topic_network(viz_data["nodes"], viz_data["edges"]))
    except Exception as e:
        print(f"  Warning: Could not generate Putz ego graph: {e}")

    print(f"  Generated {len(_CHART_DIVS)} inline charts")


def generate_index():
    """Generate docs/index.md — landing page."""
    a2026, multi = _load_analysis()
    spy = multi["sessions_per_year"]

    content = f"""# CSUN AT Conference Analytics

Analytics and insights from the world's largest assistive technology conference.

## Quick Stats (2026)

| Metric | Value |
|--------|-------|
| Total Sessions | **{a2026['total_sessions']}** |
| Unique Presenters | **{a2026['unique_presenters']}** |
| Organizations | **{a2026['unique_organizations']}** |
| AI/ML Sessions | **{a2026['ai_ml_analysis']['total_ai_sessions']}** ({a2026['ai_ml_analysis']['percentage_of_all']}%) |

## Conference Growth

{_embed_chart_root('sessions_per_year')}

## Data Coverage

| Year | Sessions | Source |
|------|----------|--------|
| 2023 | {spy.get('2023', spy.get(2023, 0))} | csun.edu |
| 2024 | {spy.get('2024', spy.get(2024, 0))} | csun.edu |
| 2025 | {spy.get('2025', spy.get(2025, 0))} | Cvent GraphQL |
| 2026 | {spy.get('2026', spy.get(2026, 0))} | Cvent GraphQL |

!!! info "About this project"
    This analytics toolkit scrapes, normalizes, and analyzes session data from the
    CSUN Assistive Technology Conference across multiple years. It uses Cvent's public
    GraphQL API for 2025-2026 data and direct HTML scraping for earlier years.
"""
    _write_doc("index.md", content)


def generate_conference_growth():
    a2026, multi = _load_analysis()
    spy = multi["sessions_per_year"]

    rows = []
    for y in YEARS:
        cnt = spy.get(str(y), spy.get(y, 0))
        yoy = multi.get("yoy_growth", {}).get(f"{y-1}-{y}", "")
        growth_str = f"+{yoy}%" if yoy and float(str(yoy)) >= 0 else f"{yoy}%" if yoy else "—"
        rows.append([str(y), str(cnt), growth_str])

    content = f"""# Conference Growth

## Sessions Per Year

{_embed_chart('sessions_per_year')}

{_md_table(["Year", "Sessions", "YoY Growth"], rows)}

## Sessions by Day (2026)

{_embed_chart('sessions_by_day_2026')}

## Audience Level Distribution (2026)

{_embed_chart('audience_level_2026')}
"""
    _write_doc("conference-growth.md", content)


def generate_topics():
    a2026, multi = _load_analysis()

    # Topics index
    rows = []
    for item in a2026.get("primary_topic_distribution", []):
        if item["count"] > 0:
            rows.append([item["name"], str(item["count"]), f"{item['percentage']}%"])

    content = f"""# Topic Distribution

## 2026 Primary Topics

{_embed_chart('topic_distribution_2026')}

{_md_table(["Topic", "Sessions", "Share"], rows)}
"""
    _write_doc("topics/index.md", content)

    # Trends
    content = f"""# Topic Trends

## Topic Share Across Years

{_embed_chart('topic_trends_heatmap')}

The heatmap shows how topic shares have shifted from 2023 to 2026.
Digital Accessibility remains dominant, while AI/ML has seen the most growth.
"""
    _write_doc("topics/trends.md", content)

    # AI/ML
    ai = a2026.get("ai_ml_analysis", {})
    ai_trend = multi.get("ai_ml_trend", {})
    rows = []
    for y in YEARS:
        info = ai_trend.get(str(y), ai_trend.get(y, {}))
        rows.append([str(y), str(info.get("count", 0)), f"{info.get('percentage', 0)}%"])

    titles_md = "\n".join(f"- {t}" for t in ai.get("titles", [])[:20])

    content = f"""# AI & Machine Learning Sessions

## Growth Over Time

{_embed_chart('ai_growth')}

{_md_table(["Year", "AI/ML Sessions", "% of All"], rows)}

## 2026 AI/ML Sessions ({ai.get('total_ai_sessions', 0)} total)

{titles_md}
{"" if len(ai.get("titles", [])) <= 20 else f"*...and {len(ai['titles']) - 20} more*"}
"""
    _write_doc("topics/ai-ml.md", content)


def generate_organizations():
    a2026, multi = _load_analysis()

    # Index
    rows = []
    for i, item in enumerate(a2026.get("top_organizations", [])[:20], 1):
        rows.append([str(i), item["name"], str(item["count"])])

    content = f"""# Organizations

## Top Presenting Organizations (2026)

{_embed_chart('org_bubble')}

{_md_table(["Rank", "Organization", "Presenters"], rows)}
"""
    _write_doc("organizations/index.md", content)

    # Trends
    headers = ["Organization"] + [str(y) for y in YEARS] + ["Total"]
    rows = []
    for row_data in multi.get("organization_trends", [])[:25]:
        r = [row_data["organization"]]
        for y in YEARS:
            r.append(str(row_data.get(f"sessions_{y}", 0)))
        r.append(str(row_data["total_sessions"]))
        rows.append(r)

    content = f"""# Organization Trends

## Sessions by Organization Across Years

{_md_table(headers, rows)}
"""
    _write_doc("organizations/trends.md", content)


def generate_speakers():
    a2026, multi = _load_analysis()
    cont = multi.get("presenter_continuity", {})

    # Index
    rows = []
    for i, item in enumerate(a2026.get("top_presenters", [])[:15], 1):
        rows.append([str(i), item["name"], str(item["count"])])

    content = f"""# Speakers

## Top Individual Presenters (2026)

{_md_table(["Rank", "Presenter", "Sessions"], rows)}
"""
    _write_doc("speakers/index.md", content)

    # Continuity
    content = f"""# Presenter Continuity

## How Often Do Presenters Return?

{_embed_chart('presenter_continuity')}

| Appearances | Presenters |
|-------------|-----------|
| 1 year | {cont.get('presenters_appearing_1_year', 0)} |
| 2 years | {cont.get('presenters_appearing_2_years', 0)} |
| 3 years | {cont.get('presenters_appearing_3_years', 0)} |
| All 4 years | {cont.get('presenters_appearing_4_years', 0)} |
"""

    all_four = [p for p in cont.get("top_returning_presenters", []) if p.get("num_years") == 4]
    if all_four:
        content += "\n## Presenters Across All 4 Years\n\n"
        rows = [[p["name"], p.get("organization", ""), ", ".join(str(y) for y in p["years"])]
                for p in all_four[:30]]
        content += _md_table(["Name", "Organization", "Years"], rows)
        content += "\n"

    _write_doc("speakers/continuity.md", content)


def generate_knowledge_graph():
    tc = _embed_chart("topic_community")
    kgp = _embed_chart("knowledge_graph_putz")

    content = f"""# Knowledge Graph

## Topic Community Network (2026)

This graph shows how topics are interconnected based on shared sessions,
presenters, and content similarity.

{tc}

## Andreas Putz's Talk — Connection Network

An ego graph centered on "Leveraging AI for A11y: Lessons in Validation and Safeguarding",
showing the 50 most closely related sessions across all years.

{kgp}

!!! tip "Interactive"
    Hover over nodes to see session details. Node size reflects connection strength.
    Colors represent primary topics.
"""
    _write_doc("knowledge-graph/index.md", content)


def generate_methodology():
    content = """# Methodology

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
"""
    _write_doc("methodology.md", content)


def _write_doc(rel_path: str, content: str):
    path = DOCS_DIR / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  Generated {rel_path}")


def build_docs():
    """Generate all documentation pages and charts."""
    print("Generating charts...")
    generate_charts()

    print("\nGenerating documentation pages...")
    generate_index()
    generate_conference_growth()
    generate_topics()
    generate_organizations()
    generate_speakers()
    generate_knowledge_graph()
    generate_methodology()

    print(f"\nDocumentation generated in {DOCS_DIR}/")
    print("Run 'mkdocs serve' to preview, or 'mkdocs build' to generate the static site.")


if __name__ == "__main__":
    build_docs()
