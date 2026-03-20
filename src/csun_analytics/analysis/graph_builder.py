"""Networkx-based graph builder for CSUN AT Conference knowledge graphs.

Converts existing knowledge graph JSON data into networkx Graph objects
for visualization, analysis, and layout computation.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx

from csun_analytics.analysis.knowledge_graph import (
    build_node,
    clean_sessions,
    compute_audience_edges,
    compute_copresenter_edges,
    compute_keyword_edges,
    compute_org_edges,
    compute_temporal_edges,
    compute_topic_edges,
    merge_edges,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


# ---------------------------------------------------------------------------
# 1. Load a knowledge graph JSON into a networkx Graph
# ---------------------------------------------------------------------------

def load_graph(path: str | Path) -> nx.Graph:
    """Load a knowledge graph JSON file into a networkx Graph.

    All node and edge attributes from the JSON are preserved on the
    resulting graph objects.

    Parameters
    ----------
    path : str or Path
        Path to a knowledge_graph JSON file.

    Returns
    -------
    nx.Graph
        Graph with node/edge attributes populated from the JSON.
    """
    path = Path(path)
    with open(path) as f:
        data = json.load(f)

    G = nx.Graph()
    G.graph["metadata"] = data.get("metadata", {})

    for node in data["nodes"]:
        sid = node["session_id"]
        attrs = {k: v for k, v in node.items() if k != "session_id"}
        G.add_node(sid, **attrs)

    for edge in data["edges"]:
        src, tgt = edge["source"], edge["target"]
        attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
        G.add_edge(src, tgt, **attrs)

    return G


# ---------------------------------------------------------------------------
# 2. Build a fresh graph from raw session data
# ---------------------------------------------------------------------------

def build_full_graph(sessions: list[dict]) -> nx.Graph:
    """Build a networkx Graph from raw session dicts.

    Reuses edge-computation logic from
    ``csun_analytics.analysis.knowledge_graph`` rather than duplicating it.

    Parameters
    ----------
    sessions : list[dict]
        Raw session dictionaries (as loaded from ``sessions_YYYY.json``).

    Returns
    -------
    nx.Graph
        Complete session similarity graph.
    """
    sessions = clean_sessions(sessions)
    idx = {s["session_id"]: i for i, s in enumerate(sessions)}

    # Compute all edge types
    all_edges: list[dict] = []
    all_edges.extend(compute_topic_edges(sessions, idx))
    all_edges.extend(compute_org_edges(sessions, idx))
    all_edges.extend(compute_keyword_edges(sessions, idx))
    all_edges.extend(compute_audience_edges(sessions, idx))
    all_edges.extend(compute_copresenter_edges(sessions, idx))
    all_edges.extend(compute_temporal_edges(sessions, idx))

    merged = merge_edges(all_edges)

    # Determine which session IDs appear in at least one edge
    node_ids_in_edges: set[str] = set()
    for e in merged:
        node_ids_in_edges.add(e["source"])
        node_ids_in_edges.add(e["target"])

    G = nx.Graph()

    # Add every session as a node (even isolated ones)
    for s in sessions:
        node = build_node(s)
        sid = node.pop("session_id")
        G.add_node(sid, **node)

    # Add merged edges
    for e in merged:
        src, tgt = e["source"], e["target"]
        attrs = {k: v for k, v in e.items() if k not in ("source", "target")}
        G.add_edge(src, tgt, **attrs)

    return G


# ---------------------------------------------------------------------------
# 3. Ego graph (focused subgraph around a session)
# ---------------------------------------------------------------------------

def ego_graph(
    G: nx.Graph,
    session_id: str,
    radius: int = 2,
    min_weight: float = 0.3,
) -> nx.Graph:
    """Extract a focused subgraph around a session.

    First prunes edges below *min_weight*, then extracts the ego graph
    of the given node up to *radius* hops.

    Parameters
    ----------
    G : nx.Graph
        Full knowledge graph.
    session_id : str
        Central session node.
    radius : int
        Number of hops from the central node (default 2).
    min_weight : float
        Minimum ``combined_weight`` for an edge to be kept (default 0.3).

    Returns
    -------
    nx.Graph
        Subgraph centered on *session_id*.
    """
    if session_id not in G:
        raise KeyError(f"Session {session_id!r} not found in graph")

    # Build a filtered view keeping only edges above the weight threshold
    filtered = nx.Graph()
    filtered.add_nodes_from(G.nodes(data=True))
    for u, v, d in G.edges(data=True):
        if d.get("combined_weight", 0) >= min_weight:
            filtered.add_edge(u, v, **d)

    # Use networkx ego_graph on the filtered version
    sub = nx.ego_graph(filtered, session_id, radius=radius)

    # Copy graph-level metadata
    sub.graph["metadata"] = {
        "focal_session": session_id,
        "radius": radius,
        "min_weight": min_weight,
        "total_nodes": sub.number_of_nodes(),
        "total_edges": sub.number_of_edges(),
    }
    return sub


# ---------------------------------------------------------------------------
# 4. Topic community graph
# ---------------------------------------------------------------------------

def topic_community_graph(G: nx.Graph) -> nx.Graph:
    """Aggregate sessions by primary_topic into a topic-level graph.

    Nodes represent topics (with a ``session_count`` attribute).  Edges
    carry the sum of ``combined_weight`` across all session pairs that
    bridge two topics.  This typically produces a ~20-30 node graph
    that is ideal for high-level visualization.

    Parameters
    ----------
    G : nx.Graph
        Session-level knowledge graph.

    Returns
    -------
    nx.Graph
        Topic community graph.
    """
    # Map sessions to their primary topic
    session_topic: dict[str, str] = {}
    topic_counts: dict[str, int] = defaultdict(int)
    for node, attrs in G.nodes(data=True):
        topic = attrs.get("primary_topic", "").strip() or "Unknown"
        session_topic[node] = topic
        topic_counts[topic] += 1

    # Aggregate edge weights between topic pairs
    topic_edge_weights: dict[tuple[str, str], float] = defaultdict(float)
    topic_edge_counts: dict[tuple[str, str], int] = defaultdict(int)
    for u, v, d in G.edges(data=True):
        t_u = session_topic.get(u, "Unknown")
        t_v = session_topic.get(v, "Unknown")
        if t_u == t_v:
            continue  # Skip intra-topic edges
        key = (min(t_u, t_v), max(t_u, t_v))
        topic_edge_weights[key] += d.get("combined_weight", 0)
        topic_edge_counts[key] += 1

    TG = nx.Graph()
    for topic, count in topic_counts.items():
        TG.add_node(topic, session_count=count, topic=topic)

    for (t1, t2), weight in topic_edge_weights.items():
        TG.add_edge(
            t1, t2,
            combined_weight=round(weight, 4),
            edge_count=topic_edge_counts[(t1, t2)],
        )

    return TG


# ---------------------------------------------------------------------------
# 5. Organization network (bipartite)
# ---------------------------------------------------------------------------

def org_network(G: nx.Graph) -> nx.Graph:
    """Build a bipartite graph of organizations and topics.

    One set of nodes represents organizations (``bipartite=0``), the
    other represents primary topics (``bipartite=1``).  An edge connects
    an organization to a topic when at least one presenter from that
    organization gave a session in that topic.  The edge ``weight``
    equals the number of such sessions.

    Parameters
    ----------
    G : nx.Graph
        Session-level knowledge graph.

    Returns
    -------
    nx.Graph
        Bipartite graph (organizations <-> topics).
    """
    org_topic_counts: dict[tuple[str, str], int] = defaultdict(int)
    orgs: set[str] = set()
    topics: set[str] = set()

    for _, attrs in G.nodes(data=True):
        topic = attrs.get("primary_topic", "").strip()
        if not topic:
            continue
        topics.add(topic)
        for p in attrs.get("presenters", []):
            aff = (p.get("affiliation") or "").strip()
            if not aff:
                continue
            orgs.add(aff)
            org_topic_counts[(aff, topic)] += 1

    BG = nx.Graph()
    for org in orgs:
        BG.add_node(org, bipartite=0, node_type="organization")
    for topic in topics:
        BG.add_node(topic, bipartite=1, node_type="topic")

    for (org, topic), count in org_topic_counts.items():
        BG.add_edge(org, topic, weight=count)

    return BG


# ---------------------------------------------------------------------------
# 6. Layout computation
# ---------------------------------------------------------------------------

_LAYOUT_ALGORITHMS = {
    "spring": nx.spring_layout,
    "kamada_kawai": nx.kamada_kawai_layout,
    "circular": nx.circular_layout,
}


def compute_layout(
    G: nx.Graph,
    algorithm: str = "spring",
) -> dict[str, tuple[float, float]]:
    """Compute 2-D node positions for a graph.

    Parameters
    ----------
    G : nx.Graph
        The graph to lay out.
    algorithm : str
        One of ``'spring'``, ``'kamada_kawai'``, or ``'circular'``.

    Returns
    -------
    dict[str, tuple[float, float]]
        Mapping of node id -> (x, y) position.
    """
    if algorithm not in _LAYOUT_ALGORITHMS:
        raise ValueError(
            f"Unknown layout algorithm {algorithm!r}. "
            f"Choose from {sorted(_LAYOUT_ALGORITHMS)}"
        )

    layout_fn = _LAYOUT_ALGORITHMS[algorithm]

    kwargs: dict[str, Any] = {}
    if algorithm == "spring":
        # Use combined_weight for better clustering
        kwargs["weight"] = "combined_weight"
        kwargs["k"] = None  # auto
        kwargs["iterations"] = 100
        kwargs["seed"] = 42

    pos = layout_fn(G, **kwargs)

    # Convert numpy arrays to plain tuples
    return {str(node): (float(xy[0]), float(xy[1])) for node, xy in pos.items()}


# ---------------------------------------------------------------------------
# 7. Convert to viz data format
# ---------------------------------------------------------------------------

def graph_to_viz_data(
    G: nx.Graph,
    layout: dict[str, tuple[float, float]] | None = None,
) -> dict:
    """Convert a networkx graph to a dict suitable for viz/charts.py.

    Returns ``{"nodes": [...], "edges": [...]}`` with position data
    included when a *layout* is provided (or computed automatically
    via spring layout).

    Parameters
    ----------
    G : nx.Graph
        The graph to convert.
    layout : dict or None
        Pre-computed layout from :func:`compute_layout`.  If *None*,
        a spring layout is computed automatically.

    Returns
    -------
    dict
        ``{"nodes": [...], "edges": [...]}`` ready for visualization.
    """
    if layout is None:
        layout = compute_layout(G, algorithm="spring")

    nodes = []
    for node, attrs in G.nodes(data=True):
        entry: dict[str, Any] = {"id": str(node)}
        entry.update(attrs)
        pos = layout.get(str(node))
        if pos is not None:
            entry["x"] = pos[0]
            entry["y"] = pos[1]
        nodes.append(entry)

    edges = []
    for u, v, attrs in G.edges(data=True):
        entry: dict[str, Any] = {"source": str(u), "target": str(v)}
        entry.update(attrs)
        edges.append(entry)

    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# 8. Centrality metrics
# ---------------------------------------------------------------------------

def compute_centrality(G: nx.Graph) -> dict[str, dict]:
    """Compute betweenness, degree, and eigenvector centrality for each node.

    Parameters
    ----------
    G : nx.Graph
        The graph to analyse.

    Returns
    -------
    dict[str, dict]
        Mapping of node id -> {"betweenness": float, "degree": float,
        "eigenvector": float}.
    """
    betweenness = nx.betweenness_centrality(G, weight="combined_weight")
    degree = nx.degree_centrality(G)

    # Eigenvector centrality can fail on disconnected graphs; fall back to 0
    try:
        eigenvector = nx.eigenvector_centrality(
            G, max_iter=1000, weight="combined_weight"
        )
    except nx.NetworkXError:
        # Graph may be disconnected or empty
        eigenvector = {n: 0.0 for n in G.nodes()}

    result: dict[str, dict] = {}
    for node in G.nodes():
        result[str(node)] = {
            "betweenness": round(betweenness.get(node, 0.0), 6),
            "degree": round(degree.get(node, 0.0), 6),
            "eigenvector": round(eigenvector.get(node, 0.0), 6),
        }

    return result
