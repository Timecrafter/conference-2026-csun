"""
Dash application for CSUN AT Conference Analytics.

Run with:
    PYTHONPATH=src uv run python -m csun_analytics.dashboard.app
"""

import json
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, callback

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PAGES_DIR = Path(__file__).resolve().parent / "pages"


def _load_cached_analysis():
    """Load pre-computed analysis JSON files so pages don't re-analyze on every request."""
    processed = PROJECT_ROOT / "data" / "processed"
    data = {}
    for name in ("analysis_2026", "analysis_multi_year",
                 "knowledge_graph_2026", "knowledge_graph_putz"):
        path = processed / f"{name}.json"
        if path.exists():
            with open(path) as f:
                data[name] = json.load(f)
        else:
            data[name] = {}
    return data


CACHED = _load_cached_analysis()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "16rem",
    "padding": "2rem 1rem",
    "backgroundColor": "#303030",
    "overflowY": "auto",
}

CONTENT_STYLE = {
    "marginLeft": "17rem",
    "marginRight": "1rem",
    "padding": "1rem 1rem",
}

NAV_ITEMS = [
    {"label": "Overview", "href": "/"},
    {"label": "Topics", "href": "/topics"},
    {"label": "Organizations", "href": "/organizations"},
    {"label": "Knowledge Graph", "href": "/knowledge-graph"},
]


def _sidebar():
    return html.Div(
        [
            html.H4("CSUN AT Analytics", className="text-light mb-4"),
            html.Hr(style={"borderColor": "#555"}),
            dbc.Nav(
                [
                    dbc.NavLink(
                        item["label"],
                        href=item["href"],
                        active="exact",
                        className="mb-1",
                    )
                    for item in NAV_ITEMS
                ],
                vertical=True,
                pills=True,
            ),
            html.Hr(style={"borderColor": "#555"}),
            html.Label("Filter by Year", className="text-light mb-1",
                        style={"fontSize": "0.85rem"}),
            dcc.Dropdown(
                id="global-year-filter",
                options=[{"label": str(y), "value": y} for y in [2023, 2024, 2025, 2026]],
                value=[2023, 2024, 2025, 2026],
                multi=True,
                placeholder="Select years...",
                className="mb-3",
            ),
            html.Hr(style={"borderColor": "#555"}),
            dbc.Button(
                "Export Charts",
                id="export-btn",
                color="secondary",
                size="sm",
                className="w-100",
            ),
            dcc.Download(id="chart-download"),
        ],
        style=SIDEBAR_STYLE,
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> dash.Dash:
    app = dash.Dash(
        __name__,
        use_pages=True,
        pages_folder=str(PAGES_DIR),
        external_stylesheets=[dbc.themes.DARKLY],
        suppress_callback_exceptions=True,
        title="CSUN AT Conference Analytics",
    )

    app.layout = html.Div([
        dcc.Store(id="year-store", data=[2023, 2024, 2025, 2026]),
        _sidebar(),
        html.Div(
            dash.page_container,
            style=CONTENT_STYLE,
        ),
    ])

    # Keep the store in sync with the dropdown
    @app.callback(
        Output("year-store", "data"),
        Input("global-year-filter", "value"),
    )
    def _sync_year_store(years):
        return years or [2023, 2024, 2025, 2026]

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_dashboard(port: int = 8050, debug: bool = False):
    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    run_dashboard(debug=True)
