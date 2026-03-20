"""
Knowledge Graph explorer page.

Registered at path="/knowledge-graph".
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import callback, dcc, html, Input, Output, State

from csun_analytics.viz.colors import TOPIC_PALETTE, apply_default_layout

dash.register_page(__name__, path="/knowledge-graph", name="Knowledge Graph",
                   title="Knowledge Graph Explorer")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def _load_graph(name: str) -> dict:
    path = PROCESSED_DIR / f"{name}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"metadata": {}, "nodes": [], "edges": []}


# Pre-build topic-to-color map from the 2026 graph for consistent coloring
_GRAPH_2026 = _load_graph("knowledge_graph_2026")
_GRAPH_PUTZ = _load_graph("knowledge_graph_putz")

_ALL_TOPICS_SORTED = sorted(
    set(n.get("primary_topic", "") for n in _GRAPH_2026.get("nodes", []) if n.get("primary_topic")),
    key=lambda t: -sum(1 for n in _GRAPH_2026.get("nodes", []) if n.get("primary_topic") == t),
)
_TOPIC_COLOR = {t: TOPIC_PALETTE[i % len(TOPIC_PALETTE)] for i, t in enumerate(_ALL_TOPICS_SORTED)}
_TOPIC_COLOR[""] = "#555"


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _build_network_figure(graph: dict, min_weight: float = 0.0, title: str = "") -> go.Figure:
    """Build a Plotly network graph figure from a knowledge graph dict."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not nodes:
        fig = go.Figure()
        fig.add_annotation(text="No graph data available", showarrow=False,
                           font=dict(size=18, color="#999"))
        return fig

    # Filter edges by weight
    edges = [e for e in edges if e.get("combined_weight", 0) >= min_weight]

    # Build node position using a simple force-directed-ish layout
    # Use a spring layout approximation via adjacency
    node_ids = [n["session_id"] for n in nodes]
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}

    # Degree for sizing
    degree = Counter()
    for e in edges:
        if e["source"] in id_to_idx and e["target"] in id_to_idx:
            degree[e["source"]] += 1
            degree[e["target"]] += 1

    # Simple circular layout with topic clustering
    import math
    topic_groups = defaultdict(list)
    for i, n in enumerate(nodes):
        topic_groups[n.get("primary_topic", "")].append(i)

    pos = {}
    group_angle = 0
    angle_step = 2 * math.pi / max(len(topic_groups), 1)
    for topic, indices in topic_groups.items():
        cx = 3 * math.cos(group_angle)
        cy = 3 * math.sin(group_angle)
        for j, idx in enumerate(indices):
            spread_angle = group_angle + (j - len(indices) / 2) * 0.15
            r = 2 + (j % 5) * 0.4
            pos[idx] = (cx + r * math.cos(spread_angle) * 0.3,
                        cy + r * math.sin(spread_angle) * 0.3)
        group_angle += angle_step

    # Edge traces
    edge_x = []
    edge_y = []
    for e in edges:
        src = id_to_idx.get(e["source"])
        tgt = id_to_idx.get(e["target"])
        if src is not None and tgt is not None and src in pos and tgt in pos:
            x0, y0 = pos[src]
            x1, y1 = pos[tgt]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(width=0.3, color="#555"),
        hoverinfo="none",
        showlegend=False,
    )

    # Node traces grouped by topic for legend
    node_traces = []
    focal_id = graph.get("metadata", {}).get("focal_session", "")

    for topic in _ALL_TOPICS_SORTED + [""]:
        indices = topic_groups.get(topic, [])
        if not indices:
            continue
        x_vals = [pos[i][0] for i in indices if i in pos]
        y_vals = [pos[i][1] for i in indices if i in pos]
        texts = []
        sizes = []
        customdata = []
        for i in indices:
            if i not in pos:
                continue
            n = nodes[i]
            nid = n["session_id"]
            deg = degree.get(nid, 0)
            sizes.append(max(6, min(deg * 0.8 + 6, 30)))
            presenters = ", ".join(p.get("name", "") for p in n.get("presenters", [])[:3])
            texts.append(
                f"<b>{n.get('title', '')[:60]}</b><br>"
                f"Topic: {n.get('primary_topic', 'N/A')}<br>"
                f"Presenters: {presenters or 'N/A'}<br>"
                f"Connections: {deg}"
            )
            customdata.append(json.dumps(n))

        color = _TOPIC_COLOR.get(topic, "#555")
        node_traces.append(go.Scatter(
            x=x_vals, y=y_vals,
            mode="markers",
            marker=dict(
                size=sizes,
                color=color,
                opacity=0.85,
                line=dict(width=1, color="#fff"),
            ),
            text=texts,
            customdata=customdata,
            hoverinfo="text",
            name=topic or "(no topic)",
        ))

    fig = go.Figure(data=[edge_trace] + node_traces)
    apply_default_layout(fig, title=title)
    fig.update_layout(
        showlegend=True,
        legend=dict(
            bgcolor="rgba(30,30,30,0.8)",
            font=dict(color="#ccc", size=10),
            itemsizing="constant",
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, linecolor="rgba(0,0,0,0)"),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, linecolor="rgba(0,0,0,0)"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc",
        height=650,
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div([
    html.H2("Knowledge Graph Explorer", className="mb-4"),

    dbc.Row([
        dbc.Col([
            html.Label("Graph View", className="text-muted mb-1"),
            dcc.Dropdown(
                id="kg-view-select",
                options=[
                    {"label": "Topic Communities (2026)", "value": "topics"},
                    {"label": "Ego Graph (Putz)", "value": "ego"},
                    {"label": "Full 2026 Network", "value": "full"},
                ],
                value="topics",
                clearable=False,
            ),
        ], md=4),
        dbc.Col([
            html.Label("Min Edge Weight", className="text-muted mb-1"),
            dcc.Slider(
                id="kg-weight-slider",
                min=0, max=3, step=0.1, value=0.5,
                marks={0: "0", 0.5: "0.5", 1: "1", 1.5: "1.5", 2: "2", 3: "3"},
                tooltip={"placement": "bottom"},
            ),
        ], md=5),
    ], className="mb-3"),

    dcc.Graph(id="kg-graph"),

    html.Hr(),
    html.H4("Session Details", className="mb-2"),
    html.Div(id="kg-session-details", children=[
        html.P("Click a node in the graph to see session details.",
               className="text-muted"),
    ]),
])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("kg-graph", "figure"),
    Input("kg-view-select", "value"),
    Input("kg-weight-slider", "value"),
)
def update_graph(view, min_weight):
    if view == "ego":
        graph = _GRAPH_PUTZ
        title = f"Ego Network: {graph.get('metadata', {}).get('focal_title', 'Putz')}"
    elif view == "full":
        graph = _GRAPH_2026
        title = "Full 2026 Conference Network"
    else:
        # Topic communities: use full 2026 but with higher weight threshold
        graph = _GRAPH_2026
        title = "2026 Topic Communities"
        min_weight = max(min_weight, 0.5)

    return _build_network_figure(graph, min_weight=min_weight, title=title)


@callback(
    Output("kg-session-details", "children"),
    Input("kg-graph", "clickData"),
)
def show_session_details(click_data):
    if not click_data or not click_data.get("points"):
        return html.P("Click a node in the graph to see session details.",
                       className="text-muted")

    point = click_data["points"][0]
    raw = point.get("customdata")
    if not raw:
        return html.P("No session data for this point.", className="text-muted")

    try:
        session = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return html.P("Could not parse session data.", className="text-muted")

    presenters = session.get("presenters", [])
    presenter_items = []
    for p in presenters:
        name = p.get("name", "Unknown")
        aff = p.get("affiliation", "")
        presenter_items.append(html.Li(f"{name} ({aff})" if aff else name))

    return dbc.Card(dbc.CardBody([
        html.H5(session.get("title", "Untitled"), className="card-title"),
        html.P([
            html.Strong("Primary Topic: "),
            session.get("primary_topic", "N/A"),
        ]),
        html.P([
            html.Strong("Secondary Topics: "),
            ", ".join(session.get("secondary_topics", [])) or "None",
        ]),
        html.P([
            html.Strong("Date/Time: "),
            f"{session.get('date', 'N/A')} at {session.get('time', 'N/A')}",
        ]),
        html.P([
            html.Strong("Location: "),
            session.get("location", "N/A"),
        ]),
        html.P([html.Strong("Presenters:")]),
        html.Ul(presenter_items) if presenter_items else html.P("No presenters listed."),
        html.P([
            html.Strong("Target Audiences: "),
            ", ".join(session.get("target_audiences", [])) or "None",
        ]),
    ]), className="mb-3")
