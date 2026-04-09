"""
Reusable Plotly figure-building functions for CSUN AT Conference analytics.

Every public function returns a plotly.graph_objects.Figure with the CSUN theme
applied, clean hover text, and accessible styling.
"""

from __future__ import annotations

import plotly.graph_objects as go

from csun_analytics.viz.colors import (
    TOPIC_PALETTE,
    YEAR_COLORS,
    apply_default_layout,
    build_topic_colormap,
    get_org_color,
    get_topic_color,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_YEARS = [2023, 2024, 2025, 2026]


def _pct_change(old: int | float, new: int | float) -> float | None:
    if old and old > 0:
        return round(100 * (new - old) / old, 1)
    return None


# ---------------------------------------------------------------------------
# 1. Sessions per year  (bar chart with YoY growth annotations)
# ---------------------------------------------------------------------------

def fig_sessions_per_year(sessions_per_year: dict[int, int]) -> go.Figure:
    """Bar chart of session counts per year with YoY growth annotations."""
    years = sorted(sessions_per_year.keys())
    counts = [sessions_per_year[y] for y in years]
    colors = [YEAR_COLORS.get(y, "#636EFA") for y in years]

    fig = go.Figure(
        go.Bar(
            x=[str(y) for y in years],
            y=counts,
            marker_color=colors,
            text=counts,
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Sessions: %{y}<extra></extra>",
        )
    )

    # Add YoY growth annotations — use category index for x position
    # because plotly.js 3.x treats string annotations like "2024" as numeric.
    annotations = []
    for i in range(1, len(years)):
        pct = _pct_change(sessions_per_year[years[i - 1]], sessions_per_year[years[i]])
        if pct is not None:
            sign = "+" if pct >= 0 else ""
            annotations.append(
                dict(
                    x=i,
                    xref="x",
                    y=counts[i],
                    text=f"{sign}{pct}%",
                    showarrow=False,
                    yshift=30,
                    font=dict(size=12, color="#00796B" if pct >= 0 else "#C62828"),
                )
            )

    apply_default_layout(
        fig,
        title="CSUN AT Conference Sessions Per Year",
        xaxis_title="Year",
        yaxis_title="Number of Sessions",
        annotations=annotations,
        showlegend=False,
    )
    fig.update_yaxes(range=[0, max(counts) * 1.2] if counts else None)
    return fig


# ---------------------------------------------------------------------------
# 2. Topic distribution  (horizontal bar chart)
# ---------------------------------------------------------------------------

def fig_topic_distribution(
    topic_data: list[dict], year: int
) -> go.Figure:
    """Horizontal bar chart of topic distribution for a given year.

    topic_data items: {name, count, percentage}
    """
    # Sort ascending so the highest value is at the top of the horizontal bar
    sorted_data = sorted(topic_data, key=lambda d: d["count"])
    names = [d["name"] for d in sorted_data]
    counts = [d["count"] for d in sorted_data]
    pcts = [d["percentage"] for d in sorted_data]
    colors = [get_topic_color(i) for i in range(len(sorted_data))]

    fig = go.Figure(
        go.Bar(
            y=names,
            x=counts,
            orientation="h",
            marker_color=colors,
            text=[f"{c} ({p}%)" for c, p in zip(counts, pcts)],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Sessions: %{x}<br>Share: %{text}<extra></extra>",
        )
    )

    height = max(400, len(names) * 28 + 120)
    apply_default_layout(
        fig,
        title=f"Topic Distribution ({year})",
        xaxis_title="Number of Sessions",
        yaxis_title="",
        height=height,
        showlegend=False,
    )
    fig.update_xaxes(range=[0, max(counts) * 1.10] if counts else None)
    return fig


# ---------------------------------------------------------------------------
# 3. Topic trends heatmap
# ---------------------------------------------------------------------------

def fig_topic_trends_heatmap(topic_trends: list[dict]) -> go.Figure:
    """Heatmap of topic share (%) across years 2023-2026.

    topic_trends rows: {topic, share_2023, share_2024, share_2025, share_2026}
    """
    # Take top topics by latest year share; cap at 25 for readability
    sorted_trends = sorted(
        topic_trends, key=lambda r: r.get("share_2026", 0), reverse=True
    )[:25]
    # Reverse so highest is at top
    sorted_trends = list(reversed(sorted_trends))

    topics = [r["topic"] for r in sorted_trends]
    z_data = []
    for r in sorted_trends:
        row = [r.get(f"share_{y}", 0) for y in _YEARS]
        z_data.append(row)

    # Build hover text
    hover = []
    for r in sorted_trends:
        row_hover = []
        for y in _YEARS:
            share = r.get(f"share_{y}", 0)
            count = r.get(f"count_{y}", 0)
            row_hover.append(f"<b>{r['topic']}</b><br>{y}: {share}% ({count} sessions)")
        hover.append(row_hover)

    fig = go.Figure(
        go.Heatmap(
            z=z_data,
            x=[str(y) for y in _YEARS],
            y=topics,
            colorscale="YlOrRd",
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
            colorbar=dict(title="Share %", ticksuffix="%"),
        )
    )

    height = max(500, len(topics) * 26 + 120)
    apply_default_layout(
        fig,
        title="Topic Share Trends (2023-2026)",
        xaxis_title="Year",
        height=height,
    )
    return fig


# ---------------------------------------------------------------------------
# 4. AI/ML growth  (line chart with area fill)
# ---------------------------------------------------------------------------

def fig_ai_growth(ai_trend: dict[int, dict]) -> go.Figure:
    """Line chart with area fill showing AI/ML session count and percentage.

    ai_trend: {year: {count, percentage}}
    """
    years = sorted(ai_trend.keys())
    counts = [ai_trend[y]["count"] for y in years]
    pcts = [ai_trend[y]["percentage"] for y in years]

    fig = go.Figure()

    # Count (primary y-axis)
    fig.add_trace(
        go.Scatter(
            x=[str(y) for y in years],
            y=counts,
            mode="lines+markers+text",
            name="AI/ML Sessions",
            line=dict(color="#AB63FA", width=3),
            marker=dict(size=10),
            fill="tozeroy",
            fillcolor="rgba(171, 99, 250, 0.15)",
            text=counts,
            textposition="top center",
            hovertemplate="<b>%{x}</b><br>AI/ML Sessions: %{y}<extra></extra>",
        )
    )

    # Percentage (secondary y-axis)
    fig.add_trace(
        go.Scatter(
            x=[str(y) for y in years],
            y=pcts,
            mode="lines+markers+text",
            name="% of All Sessions",
            line=dict(color="#EF553B", width=2, dash="dot"),
            marker=dict(size=8, symbol="diamond"),
            yaxis="y2",
            text=[f"{p}%" for p in pcts],
            textposition="bottom center",
            hovertemplate="<b>%{x}</b><br>Share: %{text}<extra></extra>",
        )
    )

    apply_default_layout(
        fig,
        title="AI/ML Session Growth at CSUN AT Conference",
        xaxis_title="Year",
        yaxis_title="Number of Sessions",
        yaxis2=dict(
            title="% of All Sessions",
            overlaying="y",
            side="right",
            showgrid=False,
            ticksuffix="%",
            range=[0, max(pcts) * 1.4] if pcts else None,
        ),
        legend=dict(x=0.02, y=0.98, xanchor="left", yanchor="top"),
    )
    fig.update_yaxes(range=[0, max(counts) * 1.3] if counts else None, selector=dict(title_text="Number of Sessions"))
    return fig


# ---------------------------------------------------------------------------
# 5. Organization bubble chart
# ---------------------------------------------------------------------------

def fig_org_bubble(org_trends: list[dict]) -> go.Figure:
    """Horizontal grouped bar chart of organizations across years.

    org_trends rows: {organization, total_sessions, sessions_2023..sessions_2026}
    """
    data = sorted(org_trends[:30], key=lambda d: d["total_sessions"])
    orgs = [d["organization"] for d in data]

    fig = go.Figure()
    for y in _YEARS:
        sessions = [d.get(f"sessions_{y}", 0) for d in data]
        fig.add_trace(
            go.Bar(
                y=orgs,
                x=sessions,
                name=str(y),
                orientation="h",
                marker_color=YEAR_COLORS.get(y, "#636EFA"),
                hovertemplate="<b>%{y}</b><br>Year: " + str(y) + "<br>Sessions: %{x}<extra></extra>",
            )
        )

    height = max(600, len(data) * 28 + 120)
    apply_default_layout(
        fig,
        title="Organization Presence Across Years",
        xaxis_title="Sessions",
        height=height,
        barmode="group",
        legend=dict(title="Year"),
    )
    return fig


# ---------------------------------------------------------------------------
# 6. Presenter continuity  (bar chart)
# ---------------------------------------------------------------------------

def fig_presenter_continuity(continuity: dict) -> go.Figure:
    """Bar chart showing number of presenters by years appeared.

    continuity keys: presenters_appearing_1_year, ..._2_years, ..._3_years, ..._4_years
    """
    labels = ["1 Year", "2 Years", "3 Years", "4 Years"]
    keys = [
        "presenters_appearing_1_year",
        "presenters_appearing_2_years",
        "presenters_appearing_3_years",
        "presenters_appearing_4_years",
    ]
    values = [continuity.get(k, 0) for k in keys]
    colors = ["#AEC7E8", "#1F77B4", "#FF7F0E", "#D62728"]

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=values,
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Presenters: %{y}<extra></extra>",
        )
    )

    apply_default_layout(
        fig,
        title="Presenter Continuity (2023-2026)",
        xaxis_title="Number of Years Presenting",
        yaxis_title="Number of Presenters",
        showlegend=False,
    )
    fig.update_yaxes(range=[0, max(values) * 1.2] if values else None)
    return fig


# ---------------------------------------------------------------------------
# 7. Audience level distribution  (donut chart)
# ---------------------------------------------------------------------------

def fig_audience_level_distribution(
    level_data: list[dict], year: int
) -> go.Figure:
    """Donut chart of audience level distribution.

    level_data items: {name, count, percentage}
    """
    names = [d["name"] for d in level_data]
    counts = [d["count"] for d in level_data]
    pcts = [d["percentage"] for d in level_data]

    level_colors = {
        "Beginning": "#2CA02C",
        "Intermediate": "#1F77B4",
        "Advanced": "#D62728",
        "Not specified": "#C7C7C7",
    }
    colors = [level_colors.get(n, get_topic_color(i)) for i, n in enumerate(names)]

    fig = go.Figure(
        go.Pie(
            labels=names,
            values=counts,
            hole=0.45,
            marker=dict(colors=colors, line=dict(color="white", width=2)),
            textinfo="label+percent",
            textposition="outside",
            hovertemplate="<b>%{label}</b><br>Sessions: %{value}<br>Share: %{percent}<extra></extra>",
        )
    )

    fig.add_annotation(
        text=f"<b>{sum(counts)}</b><br>sessions",
        x=0.5, y=0.5,
        font=dict(size=16, color="#2E2E2E"),
        showarrow=False,
    )

    apply_default_layout(
        fig,
        title=f"Audience Level Distribution ({year})",
        showlegend=True,
        legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
    )
    return fig


# ---------------------------------------------------------------------------
# 8. Sessions by day  (bar chart)
# ---------------------------------------------------------------------------

def fig_sessions_by_day(day_data: list[dict]) -> go.Figure:
    """Bar chart of sessions per day.

    day_data items: {date, count}
    """
    dates = [d["date"] for d in day_data]
    counts = [d["count"] for d in day_data]

    fig = go.Figure(
        go.Bar(
            x=dates,
            y=counts,
            marker_color="#17BECF",
            text=counts,
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Sessions: %{y}<extra></extra>",
        )
    )

    apply_default_layout(
        fig,
        title="Sessions by Day",
        xaxis_title="Date",
        yaxis_title="Number of Sessions",
        showlegend=False,
    )
    fig.update_yaxes(range=[0, max(counts) * 1.2] if counts else None)
    return fig


# ---------------------------------------------------------------------------
# 9. Topic network graph
# ---------------------------------------------------------------------------

def fig_topic_network(nodes: list[dict], edges: list[dict]) -> go.Figure:
    """Network graph visualization using Plotly Scatter traces.

    nodes: [{id, label, primary_topic, size}]
    edges: [{source, target, weight}]

    Uses networkx spring_layout for positioning. Nodes colored by primary_topic,
    sized by degree/centrality.
    """
    import networkx as nx

    G = nx.Graph()
    node_map = {n["id"]: n for n in nodes}
    for n in nodes:
        G.add_node(n["id"])
    for e in edges:
        G.add_edge(e["source"], e["target"], weight=e.get("weight", e.get("combined_weight", 1)))

    # Use pre-computed positions if available, else compute
    if nodes and "x" in nodes[0] and "y" in nodes[0]:
        pos = {n["id"]: (float(n["x"]), float(n["y"])) for n in nodes if "x" in n and "y" in n}
    else:
        pos = nx.spring_layout(G, seed=42, k=1.5 / (len(nodes) ** 0.5) if nodes else 1)

    # Compute sizes from degree if not provided
    for n in nodes:
        if "label" not in n:
            title = n.get("title", n["id"])
            n["label"] = title[:40] + "..." if len(title) > 40 else title
        if "size" not in n:
            n["size"] = max(8, min(30, 8 + G.degree(n["id"]) * 2))

    # Unique topics for coloring
    all_topics = sorted(set(n.get("primary_topic", "Other") for n in nodes))
    topic_cmap = build_topic_colormap(all_topics)

    # Edge traces
    edge_x, edge_y = [], []
    for e in edges:
        x0, y0 = pos.get(e["source"], (0, 0))
        x1, y1 = pos.get(e["target"], (0, 0))
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(width=0.5, color="#CCCCCC"),
        hoverinfo="skip",
        showlegend=False,
    )

    # Build one trace per topic for legend grouping
    fig = go.Figure()
    fig.add_trace(edge_trace)

    for topic in all_topics:
        topic_nodes = [n for n in nodes if n.get("primary_topic", "Other") == topic]
        xs = [pos[n["id"]][0] for n in topic_nodes if n["id"] in pos]
        ys = [pos[n["id"]][1] for n in topic_nodes if n["id"] in pos]
        sizes = [max(n.get("size", 5), 5) for n in topic_nodes if n["id"] in pos]
        labels = [n.get("label", n["id"]) for n in topic_nodes if n["id"] in pos]
        hover = [
            f"<b>{n.get('label', n['id'])}</b><br>Topic: {n.get('primary_topic', 'N/A')}<br>"
            f"Connections: {G.degree(n['id'])}"
            for n in topic_nodes if n["id"] in pos
        ]

        fig.add_trace(
            go.Scatter(
                x=xs, y=ys,
                mode="markers+text",
                name=topic,
                marker=dict(
                    size=sizes,
                    color=topic_cmap.get(topic, "#7F7F7F"),
                    line=dict(width=1, color="white"),
                    opacity=0.85,
                ),
                text=labels,
                textposition="top center",
                textfont=dict(size=8),
                hovertext=hover,
                hovertemplate="%{hovertext}<extra></extra>",
            )
        )

    apply_default_layout(
        fig,
        title="Session-Presenter Network",
        showlegend=True,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, linecolor="rgba(0,0,0,0)"),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, linecolor="rgba(0,0,0,0)"),
        height=700,
        width=900,
    )
    return fig


# ---------------------------------------------------------------------------
# 10. Topic community graph
# ---------------------------------------------------------------------------

def fig_topic_community(
    topic_nodes: list[dict], topic_edges: list[dict]
) -> go.Figure:
    """Simplified topic-to-topic community graph.

    topic_nodes: [{topic, session_count}]
    topic_edges: [{source, target, weight}]
    """
    import networkx as nx

    G = nx.Graph()
    for n in topic_nodes:
        G.add_node(n["topic"], session_count=n["session_count"])
    for e in topic_edges:
        G.add_edge(e["source"], e["target"], weight=e.get("weight", e.get("combined_weight", 1)))

    pos = nx.spring_layout(G, seed=42, k=2.0 / (len(topic_nodes) ** 0.5) if topic_nodes else 1)

    # Edges with variable width
    fig = go.Figure()

    max_weight = max((e.get("weight", e.get("combined_weight", 1)) for e in topic_edges), default=1)
    for e in topic_edges:
        x0, y0 = pos.get(e["source"], (0, 0))
        x1, y1 = pos.get(e["target"], (0, 0))
        w = e.get("weight", e.get("combined_weight", 1))
        norm_w = 0.5 + 3.5 * (w / max_weight) if max_weight else 1

        fig.add_trace(
            go.Scatter(
                x=[x0, x1, None], y=[y0, y1, None],
                mode="lines",
                line=dict(width=norm_w, color="rgba(150,150,150,0.5)"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Node trace
    topics = [n["topic"] for n in topic_nodes]
    xs = [pos[t][0] for t in topics if t in pos]
    ys = [pos[t][1] for t in topics if t in pos]
    counts = [n["session_count"] for n in topic_nodes if n["topic"] in pos]

    max_count = max(counts) if counts else 1
    sizes = [max(12, 50 * (c / max_count)) for c in counts]
    colors = [get_topic_color(i) for i in range(len(topics))]

    hover = [
        f"<b>{t}</b><br>Sessions: {c}<br>Connections: {G.degree(t)}"
        for t, c in zip(topics, counts) if t in pos
    ]

    fig.add_trace(
        go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            marker=dict(
                size=sizes,
                color=colors,
                line=dict(width=2, color="white"),
                opacity=0.9,
            ),
            text=[t for t in topics if t in pos],
            textposition="top center",
            textfont=dict(size=10),
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
            showlegend=False,
        )
    )

    apply_default_layout(
        fig,
        title="Topic Co-occurrence Network",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, linecolor="rgba(0,0,0,0)"),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, linecolor="rgba(0,0,0,0)"),
        height=700,
        width=900,
        showlegend=False,
    )
    return fig
