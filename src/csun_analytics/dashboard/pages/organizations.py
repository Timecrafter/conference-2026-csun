"""
Organization analysis page.

Registered at path="/organizations".
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
    ORG_COLORS,
    apply_default_layout,
)

dash.register_page(__name__, path="/organizations", name="Organizations",
                   title="Organization Analysis")

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
    html.H2("Organization Analysis", className="mb-4"),

    dbc.Row([
        dbc.Col(dcc.Graph(id="org-bubble"), md=7),
        dbc.Col(dcc.Graph(id="org-top-bar"), md=5),
    ], className="mb-4"),

    html.Hr(),
    html.H3("Organization Trends Across Years", className="mb-3"),
    html.Div(id="org-trends-table"),
])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("org-bubble", "figure"),
    Input("year-store", "data"),
)
def update_bubble(years):
    my = _load_json("analysis_multi_year")
    trends = my.get("organization_trends", [])
    years_sorted = sorted(years or YEARS)

    # Take top 25 orgs
    top = trends[:25]

    fig = go.Figure()
    for row in top:
        name = row["organization"]
        total = row["total_sessions"]
        # Latest year count for size scaling
        latest = row.get(f"sessions_{years_sorted[-1]}", 0) if years_sorted else 0
        color = ORG_COLORS.get(name, TOPIC_PALETTE[hash(name) % len(TOPIC_PALETTE)])

        fig.add_trace(go.Scatter(
            x=[total],
            y=[latest],
            mode="markers+text",
            text=[name],
            textposition="top center",
            marker=dict(
                size=max(total * 2, 10),
                color=color,
                opacity=0.7,
                line=dict(width=1, color="#fff"),
            ),
            name=name,
            hovertemplate=(
                f"<b>{name}</b><br>"
                f"Total sessions: {total}<br>"
                f"Latest year: {latest}<br>"
                "<extra></extra>"
            ),
            showlegend=False,
        ))

    apply_default_layout(fig, title="Top Organizations (Total vs. Latest Year)")
    fig.update_layout(
        xaxis=dict(title="Total Sessions (all years)", gridcolor="#444", linecolor="#555"),
        yaxis=dict(title=f"Sessions in {years_sorted[-1]}" if years_sorted else "Sessions",
                   gridcolor="#444", linecolor="#555"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        height=500,
    )
    return fig


@callback(
    Output("org-top-bar", "figure"),
    Input("year-store", "data"),
)
def update_top_bar(_years):
    a26 = _load_json("analysis_2026")
    orgs = a26.get("top_organizations", [])[:15]

    names = [o["name"] for o in orgs]
    counts = [o["count"] for o in orgs]
    colors = [
        ORG_COLORS.get(n, TOPIC_PALETTE[i % len(TOPIC_PALETTE)])
        for i, n in enumerate(names)
    ]

    fig = go.Figure(go.Bar(
        x=counts, y=names, orientation="h",
        marker_color=colors,
        text=counts, textposition="outside",
    ))
    apply_default_layout(fig, title="Top 15 Orgs by Presenters (2026)")
    fig.update_layout(
        yaxis=dict(autorange="reversed", gridcolor="#444", linecolor="#555"),
        xaxis=dict(gridcolor="#444", linecolor="#555"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        height=500,
        margin=dict(l=160),
    )
    return fig


@callback(
    Output("org-trends-table", "children"),
    Input("year-store", "data"),
)
def update_trends_table(years):
    my = _load_json("analysis_multi_year")
    trends = my.get("organization_trends", [])
    years_sorted = sorted(years or YEARS)

    # Build table
    header = [
        html.Thead(html.Tr(
            [html.Th("Organization")] +
            [html.Th(str(y)) for y in years_sorted] +
            [html.Th("Total"), html.Th("Growth %")]
        ))
    ]

    rows = []
    for row in trends[:30]:
        cells = [html.Td(row["organization"])]
        for y in years_sorted:
            val = row.get(f"sessions_{y}", 0)
            cells.append(html.Td(str(val)))
        cells.append(html.Td(str(row["total_sessions"]),
                             style={"fontWeight": "bold"}))
        growth = row.get("growth_pct")
        if growth is not None:
            color = "#2CA02C" if growth >= 0 else "#D62728"
            sign = "+" if growth >= 0 else ""
            cells.append(html.Td(
                f"{sign}{growth}%",
                style={"color": color},
            ))
        else:
            cells.append(html.Td("N/A", className="text-muted"))
        rows.append(html.Tr(cells))

    body = [html.Tbody(rows)]
    return dbc.Table(
        header + body,
        bordered=True,
        dark=True,
        hover=True,
        striped=True,
        responsive=True,
        size="sm",
    )
