"""
Overview / Executive Summary page.

Registered as the home page at path="/".
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

dash.register_page(__name__, path="/", name="Overview", title="Overview")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_json(name: str) -> dict:
    path = PROCESSED_DIR / f"{name}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _analysis_2026() -> dict:
    return _load_json("analysis_2026")


def _multi_year() -> dict:
    return _load_json("analysis_multi_year")


# ---------------------------------------------------------------------------
# Metric card helper
# ---------------------------------------------------------------------------

def _metric_card(title: str, value, subtitle: str = "") -> dbc.Card:
    return dbc.Card(
        dbc.CardBody([
            html.H6(title, className="card-title text-muted mb-1",
                     style={"fontSize": "0.8rem"}),
            html.H3(str(value), className="mb-0"),
            html.Small(subtitle, className="text-muted") if subtitle else None,
        ]),
        className="shadow-sm",
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div([
    html.H2("Executive Summary", className="mb-4"),

    # KPI cards (populated by callback)
    html.Div(id="overview-kpi-row", className="mb-4"),

    dbc.Row([
        dbc.Col(dcc.Graph(id="overview-sessions-per-year"), md=6),
        dbc.Col(dcc.Graph(id="overview-topic-dist"), md=6),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col(dcc.Graph(id="overview-ai-growth"), md=12),
    ]),
])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("overview-kpi-row", "children"),
    Input("year-store", "data"),
)
def update_kpi(years):
    a26 = _analysis_2026()
    my = _multi_year()

    total_sessions = sum(
        my.get("sessions_per_year", {}).get(str(y), 0)
        for y in (years or [2023, 2024, 2025, 2026])
    )
    presenters = a26.get("unique_presenters", 0)
    orgs = a26.get("unique_organizations", 0)
    ai_sessions = a26.get("ai_ml_analysis", {}).get("total_ai_sessions", 0)

    return dbc.Row([
        dbc.Col(_metric_card("Total Sessions (selected years)", f"{total_sessions:,}"), md=3),
        dbc.Col(_metric_card("Unique Presenters (2026)", f"{presenters:,}"), md=3),
        dbc.Col(_metric_card("Organizations (2026)", f"{orgs:,}"), md=3),
        dbc.Col(_metric_card("AI/ML Sessions (2026)", f"{ai_sessions}",
                             f"{a26.get('ai_ml_analysis', {}).get('percentage_of_all', 0)}% of all"),
                md=3),
    ])


@callback(
    Output("overview-sessions-per-year", "figure"),
    Input("year-store", "data"),
)
def update_sessions_per_year(years):
    my = _multi_year()
    spy = my.get("sessions_per_year", {})
    years = sorted(years or [2023, 2024, 2025, 2026])

    x = [str(y) for y in years]
    y = [spy.get(str(y), 0) for y in years]
    colors = [YEAR_COLORS.get(y, "#636EFA") for y in years]

    fig = go.Figure(go.Bar(x=x, y=y, marker_color=colors, text=y, textposition="outside"))
    apply_default_layout(fig, title="Sessions Per Year")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        xaxis=dict(gridcolor="#444", linecolor="#555"),
        yaxis=dict(gridcolor="#444", linecolor="#555"),
    )
    return fig


@callback(
    Output("overview-topic-dist", "figure"),
    Input("year-store", "data"),
)
def update_topic_dist(years):
    a26 = _analysis_2026()
    dist = a26.get("primary_topic_distribution", [])

    # Show 2026 topic distribution (primary)
    topics = [d["name"] for d in dist[:12]]
    counts = [d["count"] for d in dist[:12]]
    colors = [TOPIC_PALETTE[i % len(TOPIC_PALETTE)] for i in range(len(topics))]

    fig = go.Figure(go.Bar(
        x=counts,
        y=topics,
        orientation="h",
        marker_color=colors,
        text=counts,
        textposition="outside",
    ))
    apply_default_layout(fig, title="2026 Topic Distribution (Primary)")
    fig.update_layout(
        yaxis=dict(autorange="reversed", gridcolor="#444", linecolor="#555"),
        xaxis=dict(gridcolor="#444", linecolor="#555"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        height=450,
    )
    return fig


@callback(
    Output("overview-ai-growth", "figure"),
    Input("year-store", "data"),
)
def update_ai_growth(years):
    my = _multi_year()
    ai = my.get("ai_ml_trend", {})
    years_sorted = sorted(years or [2023, 2024, 2025, 2026])

    x = [str(y) for y in years_sorted]
    y_count = [ai.get(str(y), {}).get("count", 0) for y in years_sorted]
    y_pct = [ai.get(str(y), {}).get("percentage", 0) for y in years_sorted]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x, y=y_count, name="AI/ML Sessions",
        marker_color="#AB63FA",
        text=y_count, textposition="outside",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=y_pct, name="% of All Sessions",
        yaxis="y2",
        mode="lines+markers+text",
        text=[f"{p}%" for p in y_pct],
        textposition="top center",
        line=dict(color="#EF553B", width=3),
        marker=dict(size=10),
    ))
    apply_default_layout(fig, title="AI/ML Session Growth Across Years")
    fig.update_layout(
        yaxis=dict(title="Session Count", gridcolor="#444", linecolor="#555"),
        yaxis2=dict(
            title="% of All Sessions",
            overlaying="y",
            side="right",
            range=[0, max(y_pct) * 1.5] if y_pct else [0, 20],
            gridcolor="#444",
            linecolor="#555",
        ),
        xaxis=dict(gridcolor="#444", linecolor="#555"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        legend=dict(bgcolor="rgba(0,0,0,0.3)", font_color="#ccc"),
        height=400,
    )
    return fig
