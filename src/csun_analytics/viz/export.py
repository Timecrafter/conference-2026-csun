"""
Export utilities for CSUN AT Conference visualizations.

Provides functions to save Plotly figures as HTML divs, PNGs, and standalone
HTML pages, plus a batch-export function that generates all charts from
analysis data.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from csun_analytics.viz.charts import (
    fig_ai_growth,
    fig_audience_level_distribution,
    fig_org_bubble,
    fig_presenter_continuity,
    fig_sessions_by_day,
    fig_sessions_per_year,
    fig_topic_community,
    fig_topic_distribution,
    fig_topic_trends_heatmap,
)


# ---------------------------------------------------------------------------
# Individual export helpers
# ---------------------------------------------------------------------------

def to_html_div(
    fig: go.Figure, filename: str, output_dir: str | Path
) -> Path:
    """Save a figure as an embeddable HTML <div> (no <html> wrapper).

    Suitable for embedding inside MkDocs or other static site generators.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{filename}.html"
    html = fig.to_html(full_html=False, include_plotlyjs="cdn")
    path.write_text(html, encoding="utf-8")
    return path


def to_png(
    fig: go.Figure, filename: str, output_dir: str | Path, scale: int = 2
) -> Path:
    """Save a figure as a PNG image.

    Requires the kaleido package for static image export.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{filename}.png"
    fig.write_image(str(path), scale=scale)
    return path


def to_standalone(
    fig: go.Figure, filename: str, output_dir: str | Path
) -> Path:
    """Save a figure as a standalone HTML page with embedded Plotly JS."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{filename}.html"
    fig.write_html(str(path), include_plotlyjs=True, full_html=True)
    return path


# ---------------------------------------------------------------------------
# Batch export: generate all charts from analysis dicts
# ---------------------------------------------------------------------------

_YEARS = [2023, 2024, 2025, 2026]


def _build_topic_community_data(
    analysis_2026: dict[str, Any],
) -> tuple[list[dict], list[dict]]:
    """Derive topic community nodes and edges from 2026 primary topic distribution.

    Two topics are connected if they appear as primary and secondary topic on
    the same session.  Since we only have aggregated analysis data (not raw
    sessions) here, we approximate by connecting topics that share the top-10
    list with a weight proportional to their session counts.
    """
    dist = analysis_2026.get("all_topic_distribution") or analysis_2026.get(
        "primary_topic_distribution", []
    )
    nodes = [{"topic": d["name"], "session_count": d["count"]} for d in dist[:20]]
    topic_names = [n["topic"] for n in nodes]

    # Simple heuristic: connect every pair weighted by min(count_a, count_b)
    edges = []
    count_map = {d["name"]: d["count"] for d in dist}
    for i, a in enumerate(topic_names):
        for b in topic_names[i + 1 :]:
            w = min(count_map.get(a, 0), count_map.get(b, 0))
            if w > 0:
                edges.append({"source": a, "target": b, "weight": w})

    return nodes, edges


def export_all_charts(
    analysis_2026: dict[str, Any],
    multi_year: dict[str, Any],
    output_dir: str | Path,
    formats: list[str] | None = None,
) -> list[Path]:
    """Generate all standard charts from analysis data and export them.

    Parameters
    ----------
    analysis_2026 : dict
        Output of ``analyze_2026()`` from comprehensive.py.
    multi_year : dict
        Output of ``analyze_multi_year()`` from comprehensive.py.
    output_dir : str | Path
        Directory to write chart files into.
    formats : list[str], optional
        Which formats to export.  Supported values: ``"html_div"``,
        ``"standalone"``, ``"png"``.  Defaults to ``["html_div", "standalone"]``.

    Returns
    -------
    list[Path]
        Paths of all files written.
    """
    if formats is None:
        formats = ["html_div", "standalone"]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    def _export(fig: go.Figure, name: str) -> None:
        if "html_div" in formats:
            written.append(to_html_div(fig, name, output_dir))
        if "standalone" in formats:
            written.append(to_standalone(fig, f"{name}_full", output_dir))
        if "png" in formats:
            try:
                written.append(to_png(fig, name, output_dir))
            except Exception as exc:
                print(f"  [warn] PNG export failed for {name}: {exc}")

    # 1. Sessions per year
    spy = multi_year.get("sessions_per_year", {})
    # Ensure keys are ints (JSON round-trips may stringify them)
    spy = {int(k): v for k, v in spy.items()}
    if spy:
        _export(fig_sessions_per_year(spy), "sessions_per_year")

    # 2. Topic distribution (2026)
    topic_dist = analysis_2026.get("primary_topic_distribution", [])
    if topic_dist:
        _export(fig_topic_distribution(topic_dist, 2026), "topic_distribution_2026")

    # 3. Topic trends heatmap
    topic_trends = multi_year.get("topic_trends") or multi_year.get(
        "primary_topic_trends", []
    )
    if topic_trends:
        _export(fig_topic_trends_heatmap(topic_trends), "topic_trends_heatmap")

    # 4. AI/ML growth
    ai_trend = multi_year.get("ai_ml_trend", {})
    # Ensure int keys
    ai_trend = {int(k): v for k, v in ai_trend.items()}
    if ai_trend:
        _export(fig_ai_growth(ai_trend), "ai_ml_growth")

    # 5. Organization bubble chart
    org_trends = multi_year.get("organization_trends", [])
    if org_trends:
        _export(fig_org_bubble(org_trends), "org_bubble")

    # 6. Presenter continuity
    continuity = multi_year.get("presenter_continuity", {})
    if continuity:
        _export(fig_presenter_continuity(continuity), "presenter_continuity")

    # 7. Audience level distribution (2026)
    level_data = analysis_2026.get("audience_level_distribution", [])
    if level_data:
        _export(fig_audience_level_distribution(level_data, 2026), "audience_level_2026")

    # 8. Sessions by day (2026)
    day_data = analysis_2026.get("sessions_per_day", [])
    if day_data:
        _export(fig_sessions_by_day(day_data), "sessions_by_day_2026")

    # 9. Topic community graph (derived from analysis data)
    topic_nodes, topic_edges = _build_topic_community_data(analysis_2026)
    if topic_nodes:
        _export(fig_topic_community(topic_nodes, topic_edges), "topic_community")

    print(f"\nExported {len(written)} chart files to {output_dir}")
    return written
