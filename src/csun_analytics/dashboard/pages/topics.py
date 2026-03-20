"""
Topic analysis page.

Registered at path="/topics".
"""

import json
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import callback, dcc, html, Input, Output

from csun_analytics.viz.colors import (
    TOPIC_PALETTE,
    YEAR_COLORS,
    apply_default_layout,
)

dash.register_page(__name__, path="/topics", name="Topics", title="Topic Analysis")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

YEARS = [2023, 2024, 2025, 2026]


def _load_json(name: str) -> dict:
    path = PROCESSED_DIR / f"{name}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div([
    html.H2("Topic Analysis", className="mb-4"),

    dbc.Row([
        dbc.Col([
            html.Label("Select Year for Distribution", className="text-muted mb-1"),
            dcc.Dropdown(
                id="topic-year-select",
                options=[{"label": str(y), "value": y} for y in YEARS],
                value=2026,
                clearable=False,
                className="mb-3",
            ),
            dcc.Graph(id="topic-dist-bar"),
        ], md=6),
        dbc.Col([
            html.Label("Topic Trends Heatmap (share %)", className="text-muted mb-1"),
            dcc.Graph(id="topic-heatmap"),
        ], md=6),
    ], className="mb-4"),

    html.Hr(),
    html.H3("AI/ML Deep Dive", className="mb-3"),
    dbc.Row([
        dbc.Col(dcc.Graph(id="topic-ai-trend"), md=6),
        dbc.Col(dcc.Graph(id="topic-ai-topics"), md=6),
    ]),
])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("topic-dist-bar", "figure"),
    Input("topic-year-select", "value"),
)
def update_topic_dist(year):
    a26 = _load_json("analysis_2026")
    my = _load_json("analysis_multi_year")

    if year == 2026:
        dist = a26.get("primary_topic_distribution", [])
    else:
        # Reconstruct from multi-year primary_topic_trends
        trends = my.get("primary_topic_trends", [])
        dist = []
        total = my.get("sessions_per_year", {}).get(str(year), 1)
        for row in trends:
            cnt = row.get(f"count_{year}", 0)
            if cnt > 0:
                dist.append({
                    "name": row["topic"],
                    "count": cnt,
                    "percentage": round(100 * cnt / total, 1) if total else 0,
                })
        dist.sort(key=lambda d: d["count"], reverse=True)

    topics = [d["name"] for d in dist[:15]]
    counts = [d["count"] for d in dist[:15]]
    colors = [TOPIC_PALETTE[i % len(TOPIC_PALETTE)] for i in range(len(topics))]

    fig = go.Figure(go.Bar(
        x=counts,
        y=topics,
        orientation="h",
        marker_color=colors,
        text=[f'{c}  ({d.get("percentage", 0)}%)' for c, d in zip(counts, dist[:15])],
        textposition="outside",
    ))
    apply_default_layout(fig, title=f"Primary Topic Distribution ({year})")
    fig.update_layout(
        yaxis=dict(autorange="reversed", gridcolor="#444", linecolor="#555"),
        xaxis=dict(gridcolor="#444", linecolor="#555"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        height=500,
        margin=dict(l=200),
    )
    return fig


@callback(
    Output("topic-heatmap", "figure"),
    Input("year-store", "data"),
)
def update_heatmap(years):
    my = _load_json("analysis_multi_year")
    trends = my.get("topic_trends", [])
    years_sorted = sorted(years or YEARS)

    # Take top 15 topics by latest year count
    top = trends[:15]
    topic_names = [r["topic"] for r in top]
    z = []
    for row in top:
        z.append([row.get(f"share_{y}", 0) for y in years_sorted])

    fig = go.Figure(go.Heatmap(
        z=z,
        x=[str(y) for y in years_sorted],
        y=topic_names,
        colorscale="Viridis",
        text=[[f"{v:.1f}%" for v in row] for row in z],
        texttemplate="%{text}",
        hovertemplate="Topic: %{y}<br>Year: %{x}<br>Share: %{text}<extra></extra>",
    ))
    apply_default_layout(fig, title="Topic Share Trends (%)")
    fig.update_layout(
        yaxis=dict(autorange="reversed", gridcolor="#444", linecolor="#555"),
        xaxis=dict(gridcolor="#444", linecolor="#555"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        height=500,
        margin=dict(l=200),
    )
    return fig


@callback(
    Output("topic-ai-trend", "figure"),
    Input("year-store", "data"),
)
def update_ai_trend(years):
    my = _load_json("analysis_multi_year")
    ai = my.get("ai_ml_trend", {})
    years_sorted = sorted(years or YEARS)

    x = [str(y) for y in years_sorted]
    counts = [ai.get(str(y), {}).get("count", 0) for y in years_sorted]
    pcts = [ai.get(str(y), {}).get("percentage", 0) for y in years_sorted]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=counts, name="Count",
        mode="lines+markers+text",
        text=counts, textposition="top center",
        line=dict(color="#AB63FA", width=3),
        marker=dict(size=12),
    ))
    apply_default_layout(fig, title="AI/ML Sessions Over Time")
    fig.update_layout(
        yaxis=dict(title="Number of Sessions", gridcolor="#444", linecolor="#555"),
        xaxis=dict(gridcolor="#444", linecolor="#555"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        height=400,
    )
    return fig


@callback(
    Output("topic-ai-topics", "figure"),
    Input("year-store", "data"),
)
def update_ai_topics(_years):
    a26 = _load_json("analysis_2026")
    ai = a26.get("ai_ml_analysis", {})
    overlap = ai.get("topic_overlap", [])

    topics = [d["name"] for d in overlap[:10]]
    counts = [d["count"] for d in overlap[:10]]
    colors = [TOPIC_PALETTE[i % len(TOPIC_PALETTE)] for i in range(len(topics))]

    fig = go.Figure(go.Bar(
        x=counts, y=topics, orientation="h",
        marker_color=colors,
        text=counts, textposition="outside",
    ))
    apply_default_layout(fig, title="2026 AI/ML Sessions by Topic Overlap")
    fig.update_layout(
        yaxis=dict(autorange="reversed", gridcolor="#444", linecolor="#555"),
        xaxis=dict(gridcolor="#444", linecolor="#555"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        height=400,
        margin=dict(l=200),
    )
    return fig
