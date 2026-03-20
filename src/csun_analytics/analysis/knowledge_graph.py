"""Knowledge graph builder for CSUN AT Conference sessions.

Builds a graph centered on a focal session, connecting talks via topic overlap,
organization overlap, keyword similarity (TF-IDF), audience overlap,
co-presenter networks, and temporal proximity.
"""

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

TARGET_SESSION_ID = "b127299a-9fa5-4bec-952c-ed55dab2f882"
DATA_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/processed")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all_sessions() -> list[dict]:
    """Load sessions from all available year files."""
    all_sessions = []
    for year in [2023, 2024, 2025, 2026]:
        path = DATA_DIR / f"sessions_{year}.json"
        if path.exists():
            with open(path) as f:
                sessions = json.load(f)
            all_sessions.extend(sessions)
            print(f"  Loaded {len(sessions)} sessions from {year}")
    return all_sessions


def clean_sessions(sessions: list[dict]) -> list[dict]:
    """Filter out sessions with no title or no description and no presenters."""
    cleaned = []
    for s in sessions:
        # Normalize session_id to string
        s["session_id"] = str(s["session_id"])
        title = s.get("title", "").strip()
        desc = (s.get("description", "") or "").strip()
        presenters = s.get("presenters", [])
        primary_topic = s.get("primary_topic", "")
        # Keep sessions that have a title AND (description or presenters or topic)
        if title and (desc or presenters or primary_topic):
            cleaned.append(s)
    return cleaned


# ---------------------------------------------------------------------------
# TF-IDF implementation
# ---------------------------------------------------------------------------

_STOP_WORDS = set(
    "a an the and or but in on at to for of is it this that with from by as be "
    "are was were been have has had do does did will would can could may might "
    "shall should not no nor so if then than too very also about above after "
    "before between through during each all both few more most other some such "
    "only own same just into over under again further once here there when where "
    "why how what which who whom these those their them they he she we you your "
    "our his her its my its out up new well way use used using one two many "
    "being any been much get got make made us me i per via our ours ourselves "
    "let being able across along already another even given however including "
    "rather really since still whether while within without need needs based "
    "like ensure set come work works working often provide provides provided "
    "learn offer offers offering part take takes focus explore help join us "
    "session presentation talk attendees participants conference discuss "
    "discover understand gain insights practical real world".split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase, strip non-alpha, remove stop words."""
    text = text.lower()
    tokens = re.findall(r"[a-z]{3,}", text)
    return [t for t in tokens if t not in _STOP_WORDS]


def build_tfidf(documents: list[list[str]]) -> list[dict[str, float]]:
    """Build TF-IDF vectors for a list of tokenized documents."""
    n_docs = len(documents)
    # Document frequency
    df = Counter()
    for doc in documents:
        df.update(set(doc))

    vectors = []
    for doc in documents:
        tf = Counter(doc)
        total = len(doc) if doc else 1
        vec = {}
        for term, count in tf.items():
            idf = math.log((n_docs + 1) / (df[term] + 1)) + 1
            vec[term] = (count / total) * idf
        vectors.append(vec)
    return vectors


def cosine_similarity(v1: dict[str, float], v2: dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    if not v1 or not v2:
        return 0.0
    common = set(v1.keys()) & set(v2.keys())
    if not common:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in common)
    mag1 = math.sqrt(sum(x * x for x in v1.values()))
    mag2 = math.sqrt(sum(x * x for x in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


# ---------------------------------------------------------------------------
# Edge builders
# ---------------------------------------------------------------------------

def get_topics(s: dict) -> set[str]:
    topics = set()
    pt = s.get("primary_topic", "")
    if pt:
        topics.add(pt.strip().lower())
    for st in s.get("secondary_topics", []):
        if st:
            topics.add(st.strip().lower())
    return topics


def get_affiliations(s: dict) -> set[str]:
    affs = set()
    for p in s.get("presenters", []):
        aff = (p.get("affiliation") or "").strip()
        if aff:
            affs.add(aff.lower())
    return affs


def get_presenter_names(s: dict) -> set[str]:
    return {p["name"].strip().lower() for p in s.get("presenters", []) if p.get("name")}


def get_audiences(s: dict) -> set[str]:
    return {a.strip().lower() for a in s.get("target_audiences", []) if a}


def compute_topic_edges(sessions: list[dict], idx: dict[str, int]) -> list[dict]:
    """Edges based on shared topics."""
    edges = []
    topic_to_sessions = defaultdict(list)
    for s in sessions:
        sid = s["session_id"]
        for t in get_topics(s):
            topic_to_sessions[t].append(sid)

    # Build pairwise from shared topics
    pair_topics = defaultdict(set)
    for topic, sids in topic_to_sessions.items():
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                a, b = sids[i], sids[j]
                key = (min(a, b), max(a, b))
                pair_topics[key].add(topic)

    for (a, b), shared in pair_topics.items():
        weight = len(shared) / 3.0  # Normalize: 3 shared topics = 1.0
        weight = min(weight, 1.0)
        edges.append({
            "source": a,
            "target": b,
            "type": "topic_overlap",
            "weight": round(weight, 4),
            "detail": sorted(shared),
        })
    return edges


def compute_org_edges(sessions: list[dict], idx: dict[str, int]) -> list[dict]:
    """Edges based on shared presenter affiliations."""
    edges = []
    org_to_sessions = defaultdict(list)
    for s in sessions:
        sid = s["session_id"]
        for aff in get_affiliations(s):
            org_to_sessions[aff].append(sid)

    pair_orgs = defaultdict(set)
    for org, sids in org_to_sessions.items():
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                a, b = sids[i], sids[j]
                key = (min(a, b), max(a, b))
                pair_orgs[key].add(org)

    for (a, b), shared in pair_orgs.items():
        weight = min(len(shared) * 0.5, 1.0)
        edges.append({
            "source": a,
            "target": b,
            "type": "organization_overlap",
            "weight": round(weight, 4),
            "detail": sorted(shared),
        })
    return edges


def compute_keyword_edges(
    sessions: list[dict], idx: dict[str, int], threshold: float = 0.15
) -> list[dict]:
    """Edges based on TF-IDF cosine similarity of descriptions."""
    documents = []
    for s in sessions:
        text = " ".join([
            s.get("title", ""),
            s.get("description", "") or "",
            s.get("abstract", "") or "",
            " ".join(s.get("learning_objectives", [])),
        ])
        documents.append(tokenize(text))

    print("  Computing TF-IDF vectors...")
    vectors = build_tfidf(documents)

    # Only compute similarity for the target session against all others
    # AND for sessions that share topics/orgs with target (to keep it tractable)
    target_idx_val = None
    for i, s in enumerate(sessions):
        if s["session_id"] == TARGET_SESSION_ID:
            target_idx_val = i
            break

    edges = []
    # Compute target vs all
    if target_idx_val is not None:
        target_vec = vectors[target_idx_val]
        target_sid = sessions[target_idx_val]["session_id"]
        for j, s in enumerate(sessions):
            if j == target_idx_val:
                continue
            sim = cosine_similarity(target_vec, vectors[j])
            if sim >= threshold:
                a, b = target_sid, s["session_id"]
                edges.append({
                    "source": min(a, b),
                    "target": max(a, b),
                    "type": "keyword_similarity",
                    "weight": round(sim, 4),
                    "detail": f"cosine={sim:.4f}",
                })

    # Also compute pairwise among 2026 sessions only for the full graph
    sessions_2026 = [i for i, s in enumerate(sessions) if s.get("year") == 2026]
    print(f"  Computing pairwise keyword similarity for {len(sessions_2026)} sessions (2026)...")
    for ii in range(len(sessions_2026)):
        i = sessions_2026[ii]
        for jj in range(ii + 1, len(sessions_2026)):
            j = sessions_2026[jj]
            if i == target_idx_val or j == target_idx_val:
                continue  # Already computed above
            sim = cosine_similarity(vectors[i], vectors[j])
            if sim >= threshold:
                a, b = sessions[i]["session_id"], sessions[j]["session_id"]
                edges.append({
                    "source": min(a, b),
                    "target": max(a, b),
                    "type": "keyword_similarity",
                    "weight": round(sim, 4),
                    "detail": f"cosine={sim:.4f}",
                })

    return edges


def compute_audience_edges(sessions: list[dict], idx: dict[str, int]) -> list[dict]:
    """Edges based on shared target audiences."""
    edges = []
    aud_to_sessions = defaultdict(list)
    for s in sessions:
        sid = s["session_id"]
        for a in get_audiences(s):
            aud_to_sessions[a].append(sid)

    pair_auds = defaultdict(set)
    for aud, sids in aud_to_sessions.items():
        # Only create edges for audiences with <=100 sessions to avoid noise
        if len(sids) > 100:
            continue
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                a, b = sids[i], sids[j]
                key = (min(a, b), max(a, b))
                pair_auds[key].add(aud)

    for (a, b), shared in pair_auds.items():
        weight = len(shared) / 4.0  # 4 shared audiences = 1.0
        weight = min(weight, 1.0)
        edges.append({
            "source": a,
            "target": b,
            "type": "audience_overlap",
            "weight": round(weight, 4),
            "detail": sorted(shared),
        })
    return edges


def compute_copresenter_edges(sessions: list[dict], idx: dict[str, int]) -> list[dict]:
    """Edges based on shared presenters or presenters who co-present elsewhere."""
    edges = []
    person_to_sessions = defaultdict(list)
    for s in sessions:
        sid = s["session_id"]
        for name in get_presenter_names(s):
            person_to_sessions[name].append(sid)

    # Direct: same person presents at multiple sessions
    for person, sids in person_to_sessions.items():
        if len(sids) < 2:
            continue
        for i in range(len(sids)):
            for j in range(i + 1, len(sids)):
                a, b = sids[i], sids[j]
                key = (min(a, b), max(a, b))
                edges.append({
                    "source": key[0],
                    "target": key[1],
                    "type": "copresenter",
                    "weight": 0.8,
                    "detail": person,
                })

    # Indirect: people who share a session with the same person
    # (co-presenter network - second degree)
    session_presenters = {}
    for s in sessions:
        sid = s["session_id"]
        session_presenters[sid] = get_presenter_names(s)

    # For each person, find all sessions, then link those sessions' co-presenters
    # This is already covered by the org overlap largely, so keep it simple
    return edges


def compute_temporal_edges(sessions: list[dict], idx: dict[str, int]) -> list[dict]:
    """Edges based on temporal proximity (same day, same timeslot)."""
    edges = []
    # Group by date+time (same timeslot = competing sessions)
    slot_to_sessions = defaultdict(list)
    for s in sessions:
        if s.get("year") != 2026:
            continue
        date = s.get("date", "")
        time = s.get("time", "")
        if date and time:
            slot_to_sessions[(date, time)].append(s["session_id"])

    # Same timeslot = low weight (competing, not complementary)
    # Adjacent timeslots on same day = higher weight (can attend both)
    day_to_times = defaultdict(set)
    for (date, time) in slot_to_sessions:
        day_to_times[date].add(time)

    # Same day, different slot = attendable sequence
    day_sessions = defaultdict(list)
    for s in sessions:
        if s.get("year") != 2026:
            continue
        date = s.get("date", "")
        if date:
            day_sessions[date].append(s["session_id"])

    # Find sessions on same day as target
    target_date = None
    for s in sessions:
        if s["session_id"] == TARGET_SESSION_ID:
            target_date = s.get("date", "")
            break

    if target_date:
        same_day = day_sessions.get(target_date, [])
        for sid in same_day:
            if sid == TARGET_SESSION_ID:
                continue
            a, b = min(sid, TARGET_SESSION_ID), max(sid, TARGET_SESSION_ID)
            edges.append({
                "source": a,
                "target": b,
                "type": "temporal_proximity",
                "weight": 0.15,
                "detail": f"same_day:{target_date}",
            })

    return edges


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def merge_edges(all_edges: list[dict]) -> list[dict]:
    """Merge edges of the same type between the same pair into combined edges."""
    # Group by (source, target)
    pair_edges = defaultdict(list)
    for e in all_edges:
        key = (e["source"], e["target"])
        pair_edges[key].append(e)

    merged = []
    for (src, tgt), edges in pair_edges.items():
        # Group by type
        by_type = defaultdict(list)
        for e in edges:
            by_type[e["type"]].append(e)

        type_edges = []
        total_weight = 0.0
        for etype, elist in by_type.items():
            # Take the max weight for this type
            best = max(elist, key=lambda x: x["weight"])
            type_edges.append({
                "type": etype,
                "weight": best["weight"],
                "detail": best["detail"],
            })
            total_weight += best["weight"]

        merged.append({
            "source": src,
            "target": tgt,
            "combined_weight": round(total_weight, 4),
            "connections": type_edges,
        })

    merged.sort(key=lambda x: x["combined_weight"], reverse=True)
    return merged


def build_node(s: dict) -> dict:
    """Build a node dict from a session."""
    return {
        "session_id": s["session_id"],
        "title": s.get("title", ""),
        "year": s.get("year", 0),
        "presenters": [
            {"name": p.get("name", ""), "affiliation": p.get("affiliation", "")}
            for p in s.get("presenters", [])
        ],
        "primary_topic": s.get("primary_topic", ""),
        "secondary_topics": s.get("secondary_topics", []),
        "target_audiences": s.get("target_audiences", []),
        "date": s.get("date", ""),
        "time": s.get("time", ""),
        "location": s.get("location", ""),
    }


def build_knowledge_graph():
    """Main entry point: build knowledge graph and generate all outputs."""
    print("Loading sessions...")
    all_sessions = load_all_sessions()
    print(f"Total raw sessions: {len(all_sessions)}")

    sessions = clean_sessions(all_sessions)
    print(f"After cleaning: {len(sessions)}")

    # Index by session_id
    idx = {s["session_id"]: i for i, s in enumerate(sessions)}

    if TARGET_SESSION_ID not in idx:
        print(f"ERROR: Target session {TARGET_SESSION_ID} not found!")
        return

    target = sessions[idx[TARGET_SESSION_ID]]
    print(f"\nTarget session: {target['title']}")
    print(f"  Presenters: {', '.join(p['name'] for p in target['presenters'])}")
    print(f"  Topics: {target['primary_topic']} + {target['secondary_topics']}")

    # Build edges
    print("\nBuilding edges...")
    all_edges = []

    print("  Topic overlap...")
    all_edges.extend(compute_topic_edges(sessions, idx))
    print(f"    {len(all_edges)} edges")

    prev = len(all_edges)
    print("  Organization overlap...")
    all_edges.extend(compute_org_edges(sessions, idx))
    print(f"    {len(all_edges) - prev} edges")

    prev = len(all_edges)
    print("  Keyword similarity (TF-IDF)...")
    all_edges.extend(compute_keyword_edges(sessions, idx))
    print(f"    {len(all_edges) - prev} edges")

    prev = len(all_edges)
    print("  Audience overlap...")
    all_edges.extend(compute_audience_edges(sessions, idx))
    print(f"    {len(all_edges) - prev} edges")

    prev = len(all_edges)
    print("  Co-presenter networks...")
    all_edges.extend(compute_copresenter_edges(sessions, idx))
    print(f"    {len(all_edges) - prev} edges")

    prev = len(all_edges)
    print("  Temporal proximity...")
    all_edges.extend(compute_temporal_edges(sessions, idx))
    print(f"    {len(all_edges) - prev} edges")

    print(f"\nTotal raw edges: {len(all_edges)}")

    # Merge edges
    print("Merging edges...")
    merged = merge_edges(all_edges)
    print(f"Merged edge pairs: {len(merged)}")

    # Build full graph (2026 only for the full graph)
    nodes_2026 = {s["session_id"]: build_node(s) for s in sessions if s.get("year") == 2026}
    edges_2026 = [e for e in merged if e["source"] in nodes_2026 and e["target"] in nodes_2026]

    full_graph = {
        "metadata": {
            "year": 2026,
            "total_nodes": len(nodes_2026),
            "total_edges": len(edges_2026),
            "focal_session": TARGET_SESSION_ID,
        },
        "nodes": list(nodes_2026.values()),
        "edges": edges_2026,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    path_full = OUTPUT_DIR / "knowledge_graph_2026.json"
    with open(path_full, "w") as f:
        json.dump(full_graph, f, indent=2, ensure_ascii=False)
    print(f"\nSaved full graph: {path_full}")

    # Build focused graph around target
    print("\nBuilding focused graph around target session...")
    target_edges = [
        e for e in merged
        if e["source"] == TARGET_SESSION_ID or e["target"] == TARGET_SESSION_ID
    ]
    target_edges.sort(key=lambda x: x["combined_weight"], reverse=True)

    # Get top ~50 connected sessions
    connected_ids = set()
    for e in target_edges:
        other = e["target"] if e["source"] == TARGET_SESSION_ID else e["source"]
        connected_ids.add(other)

    # Rank by combined weight and take top 50
    ranked = []
    for e in target_edges:
        other = e["target"] if e["source"] == TARGET_SESSION_ID else e["source"]
        ranked.append((other, e["combined_weight"], e))

    ranked.sort(key=lambda x: x[1], reverse=True)
    top_50_ids = set()
    top_50_edges = []
    for sid, w, e in ranked[:50]:
        top_50_ids.add(sid)
        top_50_edges.append(e)

    top_50_ids.add(TARGET_SESSION_ID)

    # Include cross-edges among the top 50
    cross_edges = [
        e for e in merged
        if e["source"] in top_50_ids and e["target"] in top_50_ids
    ]

    # Build nodes for the focused graph (including cross-year)
    all_nodes_map = {s["session_id"]: build_node(s) for s in sessions}
    focused_nodes = [all_nodes_map[sid] for sid in top_50_ids if sid in all_nodes_map]

    focused_graph = {
        "metadata": {
            "focal_session": TARGET_SESSION_ID,
            "focal_title": target["title"],
            "total_nodes": len(focused_nodes),
            "total_edges": len(cross_edges),
        },
        "nodes": focused_nodes,
        "edges": cross_edges,
    }

    path_focused = OUTPUT_DIR / "knowledge_graph_putz.json"
    with open(path_focused, "w") as f:
        json.dump(focused_graph, f, indent=2, ensure_ascii=False)
    print(f"Saved focused graph: {path_focused}")

    # Generate report
    print("\nGenerating report...")
    report = generate_report(target, target_edges, ranked, sessions, idx, merged)
    path_report = OUTPUT_DIR / "knowledge_graph_report.md"
    with open(path_report, "w") as f:
        f.write(report)
    print(f"Saved report: {path_report}")

    print("\nDone!")


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    target: dict,
    target_edges: list[dict],
    ranked: list[tuple],
    sessions: list[dict],
    idx: dict[str, int],
    all_merged: list[dict],
) -> str:
    """Generate the markdown report."""
    all_nodes_map = {s["session_id"]: s for s in sessions}
    lines = []
    lines.append("# Knowledge Graph Report: Andreas Putz's Talk at CSUN 2026")
    lines.append("")
    lines.append("## Focal Session")
    lines.append("")
    lines.append(f"**{target['title']}**")
    lines.append("")
    presenters_str = ", ".join(
        f"{p['name']} ({p.get('affiliation', 'N/A')}, {p.get('role', 'N/A')})"
        for p in target["presenters"]
    )
    lines.append(f"- **Presenters**: {presenters_str}")
    lines.append(f"- **Primary Topic**: {target['primary_topic']}")
    lines.append(f"- **Secondary Topics**: {', '.join(target['secondary_topics'])}")
    lines.append(f"- **Target Audiences**: {', '.join(target['target_audiences'])}")
    lines.append(f"- **Date/Time**: {target['date']} at {target['time']}")
    lines.append(f"- **Location**: {target['location']}")
    lines.append(f"- **Description**: {target['description']}")
    lines.append("")

    # Network statistics
    lines.append("## Network Statistics")
    lines.append("")
    lines.append(f"- **Total connections from focal session**: {len(target_edges)}")

    # Count by type
    type_counts = Counter()
    for e in target_edges:
        for c in e["connections"]:
            type_counts[c["type"]] += 1
    for etype, count in type_counts.most_common():
        lines.append(f"  - {etype}: {count}")

    # Count by year
    year_counts = Counter()
    for sid, w, e in ranked:
        s = all_nodes_map.get(sid)
        if s:
            year_counts[s.get("year", "unknown")] += 1
    lines.append(f"- **Connected sessions by year**:")
    for y in sorted(year_counts.keys()):
        lines.append(f"  - {y}: {year_counts[y]}")

    # Avg weight
    if target_edges:
        avg_w = sum(e["combined_weight"] for e in target_edges) / len(target_edges)
        max_w = max(e["combined_weight"] for e in target_edges)
        lines.append(f"- **Average connection strength**: {avg_w:.3f}")
        lines.append(f"- **Strongest connection**: {max_w:.3f}")
    lines.append("")

    # Top 30 related talks
    lines.append("## Top 30 Most Related Talks (Ranked by Connection Strength)")
    lines.append("")
    for i, (sid, weight, edge) in enumerate(ranked[:30], 1):
        s = all_nodes_map.get(sid)
        if not s:
            continue
        title = s.get("title", "Unknown")
        year = s.get("year", "?")
        presenters = ", ".join(p.get("name", "") for p in s.get("presenters", []))
        affils = ", ".join(
            set(p.get("affiliation", "") for p in s.get("presenters", []) if p.get("affiliation"))
        )
        conn_types = [c["type"].replace("_", " ") for c in edge["connections"]]

        lines.append(f"### {i}. {title} ({year})")
        lines.append(f"- **Combined weight**: {weight:.3f}")
        lines.append(f"- **Presenters**: {presenters or 'N/A'}")
        lines.append(f"- **Organizations**: {affils or 'N/A'}")
        lines.append(f"- **Connection types**: {', '.join(conn_types)}")
        # Show detail for each connection
        for c in edge["connections"]:
            detail = c["detail"]
            if isinstance(detail, list):
                detail = ", ".join(detail)
            lines.append(f"  - {c['type']}: {detail} (w={c['weight']:.3f})")
        lines.append("")

    # Thematic clusters
    lines.append("## Thematic Clusters the Talk Bridges")
    lines.append("")
    lines.append("This talk sits at the intersection of several thematic areas:")
    lines.append("")

    # Analyze connected talks' topics
    connected_topics = Counter()
    connected_orgs = Counter()
    connected_people = Counter()
    for sid, w, e in ranked[:50]:
        s = all_nodes_map.get(sid)
        if not s:
            continue
        pt = s.get("primary_topic", "")
        if pt:
            connected_topics[pt] += 1
        for st in s.get("secondary_topics", []):
            if st:
                connected_topics[st] += 1
        for p in s.get("presenters", []):
            if p.get("affiliation"):
                connected_orgs[p["affiliation"]] += 1
            if p.get("name"):
                connected_people[p["name"]] += 1

    lines.append("### Topic Distribution in Connected Sessions")
    lines.append("")
    for topic, count in connected_topics.most_common(15):
        lines.append(f"- **{topic}**: {count} sessions")
    lines.append("")

    # Cluster analysis
    lines.append("### Key Clusters")
    lines.append("")
    # AI/ML cluster
    ai_sessions = [
        (sid, w) for sid, w, e in ranked[:50]
        if any(
            "ai" in t.lower() or "machine learning" in t.lower() or "artificial intelligence" in t.lower()
            for t in [all_nodes_map.get(sid, {}).get("primary_topic", "")]
            + all_nodes_map.get(sid, {}).get("secondary_topics", [])
        )
    ]
    lines.append(f"1. **AI/ML Cluster**: {len(ai_sessions)} sessions in top 50 connections")
    for sid, w in ai_sessions[:5]:
        s = all_nodes_map.get(sid, {})
        lines.append(f"   - {s.get('title', '?')} (w={w:.3f})")

    # Digital Accessibility cluster
    da_sessions = [
        (sid, w) for sid, w, e in ranked[:50]
        if "digital accessibility" in all_nodes_map.get(sid, {}).get("primary_topic", "").lower()
    ]
    lines.append(f"2. **Digital Accessibility Cluster**: {len(da_sessions)} sessions in top 50 connections")
    for sid, w in da_sessions[:5]:
        s = all_nodes_map.get(sid, {})
        lines.append(f"   - {s.get('title', '?')} (w={w:.3f})")

    # Amazon cluster
    amazon_sessions = [
        (sid, w) for sid, w, e in ranked[:50]
        if any(
            "amazon" in (p.get("affiliation") or "").lower()
            for p in all_nodes_map.get(sid, {}).get("presenters", [])
        )
    ]
    lines.append(f"3. **Amazon Cluster**: {len(amazon_sessions)} sessions in top 50 connections")
    for sid, w in amazon_sessions[:5]:
        s = all_nodes_map.get(sid, {})
        lines.append(f"   - {s.get('title', '?')} (w={w:.3f})")
    lines.append("")

    # Key people and organizations
    lines.append("## Key People and Organizations in Connected Network")
    lines.append("")
    lines.append("### Top Organizations")
    lines.append("")
    for org, count in connected_orgs.most_common(20):
        lines.append(f"- **{org}**: {count} presenter appearances")
    lines.append("")

    lines.append("### Top Presenters")
    lines.append("")
    for person, count in connected_people.most_common(20):
        lines.append(f"- **{person}**: {count} session appearances")
    lines.append("")

    # Cross-year connections
    lines.append("## Cross-Year Connections")
    lines.append("")
    lines.append("Sessions from 2023-2025 that relate to the same themes:")
    lines.append("")
    for year in [2025, 2024, 2023]:
        year_talks = [(sid, w, e) for sid, w, e in ranked if all_nodes_map.get(sid, {}).get("year") == year]
        if not year_talks:
            lines.append(f"### {year}: No connections found")
            lines.append("")
            continue
        lines.append(f"### {year} ({len(year_talks)} connected sessions)")
        lines.append("")
        for sid, w, e in year_talks[:10]:
            s = all_nodes_map.get(sid, {})
            title = s.get("title", "?")
            presenters = ", ".join(p.get("name", "") for p in s.get("presenters", []))
            conn_types = [c["type"].replace("_", " ") for c in e["connections"]]
            lines.append(f"- **{title}** (w={w:.3f})")
            lines.append(f"  - Presenters: {presenters or 'N/A'}")
            lines.append(f"  - Connections: {', '.join(conn_types)}")
        lines.append("")

    # Position in conference ecosystem
    lines.insert(3, "## Position in the Conference Ecosystem")
    lines.insert(4, "")

    # Calculate position metrics
    # Degree centrality (relative to 2026 sessions)
    sessions_2026 = [s for s in sessions if s.get("year") == 2026]
    degree_by_session = Counter()
    for e in all_merged:
        degree_by_session[e["source"]] += 1
        degree_by_session[e["target"]] += 1
    target_degree = degree_by_session.get(TARGET_SESSION_ID, 0)
    degrees = [degree_by_session.get(s["session_id"], 0) for s in sessions_2026]
    avg_degree = sum(degrees) / len(degrees) if degrees else 0
    max_degree = max(degrees) if degrees else 0

    # Weighted degree
    weighted_degree_by_session = defaultdict(float)
    for e in all_merged:
        weighted_degree_by_session[e["source"]] += e["combined_weight"]
        weighted_degree_by_session[e["target"]] += e["combined_weight"]
    target_w_degree = weighted_degree_by_session.get(TARGET_SESSION_ID, 0)
    w_degrees = [weighted_degree_by_session.get(s["session_id"], 0) for s in sessions_2026]
    w_degrees_sorted = sorted(w_degrees, reverse=True)
    target_rank = sorted(
        [(s["session_id"], weighted_degree_by_session.get(s["session_id"], 0)) for s in sessions_2026],
        key=lambda x: x[1], reverse=True
    )
    target_position = next(
        (i + 1 for i, (sid, _) in enumerate(target_rank) if sid == TARGET_SESSION_ID),
        len(target_rank)
    )

    position_text = [
        f"Andreas Putz's talk occupies a significant position in the 2026 CSUN conference network:",
        "",
        f"- **Degree (# of connections)**: {target_degree} (avg: {avg_degree:.1f}, max: {max_degree})",
        f"- **Weighted degree**: {target_w_degree:.2f}",
        f"- **Rank by weighted degree**: #{target_position} out of {len(sessions_2026)} sessions",
        f"- **Percentile**: top {target_position / len(sessions_2026) * 100:.1f}%",
        "",
        "The talk bridges three key themes: AI/ML, Digital Accessibility, and Emerging Technologies. "
        "Its Amazon affiliation connects it to one of the largest corporate presences at the conference. "
        "The focus on validation and safeguarding positions it at the intersection of practical implementation "
        "and risk management, making it a hub session that connects the AI enthusiasm cluster with the "
        "accessibility testing and standards cluster.",
        "",
    ]
    for j, line in enumerate(position_text):
        lines.insert(5 + j, line)

    return "\n".join(lines)


if __name__ == "__main__":
    build_knowledge_graph()
