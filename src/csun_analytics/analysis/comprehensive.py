"""
Comprehensive analysis of CSUN AT Conference data.

Produces:
  - data/processed/analysis_2026.json     (deep dive into 2026)
  - data/processed/analysis_multi_year.json (cross-year trends 2023-2026)
  - data/processed/conference_report_2026.md (human-readable summary)
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUT_DIR = PROJECT_ROOT / "data" / "processed"

YEARS = [2023, 2024, 2025, 2026]

AI_KEYWORDS = re.compile(
    r"\b(artificial intelligence|machine learning|deep learning|neural network|"
    r"llm|large language model|generative ai|gen[\s\-]?ai|chatgpt|gpt|copilot|"
    r"ai[\s\-]powered|ai[\s\-]driven|natural language processing|nlp|"
    r"computer vision|automation|automated|chatbot)\b",
    re.IGNORECASE,
)

A11Y_TESTING_KEYWORDS = re.compile(
    r"\b(testing|test|validation|validate|audit|auditing|wcag|compliance|"
    r"conformance|assessment|evaluate|evaluation|checker|scanning|remediat)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_sessions(year: int) -> list[dict]:
    path = RAW_DIR / f"sessions_{year}.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def load_all_sessions() -> dict[int, list[dict]]:
    return {y: load_sessions(y) for y in YEARS}


def _apply_normalization(all_data: dict[int, list[dict]]) -> dict[int, list[dict]]:
    """Apply topic normalization if taxonomy exists."""
    from csun_analytics.analysis.normalize import normalize_session_topics, load_taxonomy
    taxonomy = load_taxonomy()
    if taxonomy is None:
        return all_data
    print("Applying topic normalization...")
    return {y: normalize_session_topics(sessions, taxonomy) for y, sessions in all_data.items()}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _normalize_level(raw: str) -> str:
    """Collapse verbose audience-level strings to short labels."""
    if not raw:
        return "Not specified"
    low = raw.lower()
    if "beginning" in low or "beginner" in low:
        return "Beginning"
    if "intermediate" in low:
        return "Intermediate"
    if "advanced" in low:
        return "Advanced"
    return raw.strip()


def _all_topics(session: dict) -> list[str]:
    """Return primary + secondary topics for a session."""
    topics = []
    if session.get("primary_topic"):
        topics.append(session["primary_topic"])
    for t in session.get("secondary_topics") or []:
        if t:
            topics.append(t)
    return topics


def _text_blob(session: dict) -> str:
    """Concatenate title + description for keyword searching."""
    parts = [session.get("title", ""), session.get("description", ""), session.get("abstract", "")]
    return " ".join(p for p in parts if p)


def _matches_keywords(session: dict, pattern: re.Pattern) -> bool:
    return bool(pattern.search(_text_blob(session)))


def _normalize_org(name: str | None) -> str:
    if not name:
        return "Independent / Not specified"
    name = name.strip()
    # Common normalizations
    replacements = {
        "Google, Inc.": "Google",
        "Google LLC": "Google",
        "Google Inc": "Google",
        "Microsoft Corporation": "Microsoft",
        "Microsoft Corp": "Microsoft",
        "Amazon.com": "Amazon",
        "Amazon Web Services": "Amazon (AWS)",
        "Meta Platforms": "Meta",
        "Facebook": "Meta",
        "International Business Machines": "IBM",
    }
    for pattern, replacement in replacements.items():
        if name.lower().startswith(pattern.lower()):
            return replacement
    return name


def _counter_to_ranked(counter: Counter, top_n: int = 0) -> list[dict]:
    items = counter.most_common(top_n if top_n else None)
    total = sum(counter.values())
    return [
        {"name": name, "count": count, "percentage": round(100 * count / total, 1) if total else 0}
        for name, count in items
    ]


# ---------------------------------------------------------------------------
# 2026 deep-dive analysis
# ---------------------------------------------------------------------------

def analyze_2026(sessions: list[dict]) -> dict[str, Any]:
    print("\n" + "=" * 70)
    print("  2026 CSUN AT Conference Deep-Dive Analysis")
    print("=" * 70)

    result: dict[str, Any] = {}

    # --- Basic counts ---
    all_presenters = []
    all_orgs = set()
    for s in sessions:
        for p in s.get("presenters") or []:
            all_presenters.append(p)
            org = _normalize_org(p.get("affiliation"))
            if org != "Independent / Not specified":
                all_orgs.add(org)

    unique_presenter_names = set(p["name"] for p in all_presenters if p.get("name"))
    result["total_sessions"] = len(sessions)
    result["unique_presenters"] = len(unique_presenter_names)
    result["unique_organizations"] = len(all_orgs)
    print(f"\nTotal sessions: {len(sessions)}")
    print(f"Unique presenters: {len(unique_presenter_names)}")
    print(f"Unique organizations: {len(all_orgs)}")

    # --- Topic distribution (primary + secondary combined) ---
    topic_counter = Counter()
    primary_counter = Counter()
    for s in sessions:
        if s.get("primary_topic"):
            primary_counter[s["primary_topic"]] += 1
        for t in _all_topics(s):
            topic_counter[t] += 1

    result["primary_topic_distribution"] = _counter_to_ranked(primary_counter)
    result["all_topic_distribution"] = _counter_to_ranked(topic_counter)

    print("\n--- Primary Topic Distribution ---")
    for item in result["primary_topic_distribution"][:15]:
        print(f"  {item['name']:40s} {item['count']:4d}  ({item['percentage']}%)")

    # --- Audience level ---
    level_counter = Counter(_normalize_level(s.get("audience_level", "")) for s in sessions)
    result["audience_level_distribution"] = _counter_to_ranked(level_counter)
    print("\n--- Audience Level Distribution ---")
    for item in result["audience_level_distribution"]:
        print(f"  {item['name']:20s} {item['count']:4d}  ({item['percentage']}%)")

    # --- Target audiences ---
    ta_counter = Counter()
    for s in sessions:
        for ta in s.get("target_audiences") or []:
            if ta:
                ta_counter[ta] += 1
    result["target_audience_distribution"] = _counter_to_ranked(ta_counter)
    print("\n--- Target Audience Distribution (top 10) ---")
    for item in result["target_audience_distribution"][:10]:
        print(f"  {item['name']:45s} {item['count']:4d}  ({item['percentage']}%)")

    # --- Sessions per day ---
    day_counter = Counter()
    for s in sessions:
        d = s.get("date", "Unknown")
        day_counter[d] += 1
    result["sessions_per_day"] = [
        {"date": d, "count": c} for d, c in sorted(day_counter.items())
    ]
    print("\n--- Sessions per Day ---")
    for item in result["sessions_per_day"]:
        print(f"  {item['date']}: {item['count']} sessions")

    # --- Room / location utilization ---
    loc_counter = Counter()
    for s in sessions:
        loc = s.get("location", "").strip() or "TBD"
        loc_counter[loc] += 1
    result["location_utilization"] = _counter_to_ranked(loc_counter, top_n=30)
    print(f"\n--- Unique rooms/locations: {len(loc_counter)} ---")
    for item in result["location_utilization"][:10]:
        print(f"  {item['name']:30s} {item['count']:4d} sessions")

    # --- Top 30 organizations ---
    org_counter = Counter()
    for p in all_presenters:
        org = _normalize_org(p.get("affiliation"))
        org_counter[org] += 1
    result["top_organizations"] = _counter_to_ranked(org_counter, top_n=30)
    print("\n--- Top 15 Presenting Organizations ---")
    for item in result["top_organizations"][:15]:
        print(f"  {item['name']:40s} {item['count']:4d} presenters")

    # --- Top 30 individual presenters ---
    presenter_session_counter = Counter()
    for s in sessions:
        for p in s.get("presenters") or []:
            if p.get("name"):
                presenter_session_counter[p["name"]] += 1
    result["top_presenters"] = _counter_to_ranked(presenter_session_counter, top_n=30)
    print("\n--- Top 10 Individual Presenters ---")
    for item in result["top_presenters"][:10]:
        print(f"  {item['name']:40s} {item['count']:4d} sessions")

    # --- Content tag analysis ---
    tag_counter = Counter()
    sessions_with_tags = 0
    for s in sessions:
        tags = s.get("content_tags") or []
        if tags:
            sessions_with_tags += 1
        for t in tags:
            tag_counter[t] += 1
    result["content_tags"] = {
        "sessions_with_tags": sessions_with_tags,
        "unique_tags": len(tag_counter),
        "distribution": _counter_to_ranked(tag_counter, top_n=30) if tag_counter else [],
    }
    print(f"\n--- Content Tags: {sessions_with_tags} sessions have tags, {len(tag_counter)} unique tags ---")

    # --- AI/ML sessions ---
    ai_sessions = [s for s in sessions if _matches_keywords(s, AI_KEYWORDS)]
    ai_topics = Counter()
    for s in ai_sessions:
        for t in _all_topics(s):
            ai_topics[t] += 1
    result["ai_ml_analysis"] = {
        "total_ai_sessions": len(ai_sessions),
        "percentage_of_all": round(100 * len(ai_sessions) / len(sessions), 1) if sessions else 0,
        "titles": [s["title"] for s in ai_sessions],
        "topic_overlap": _counter_to_ranked(ai_topics),
        "ai_org_distribution": _counter_to_ranked(
            Counter(
                _normalize_org(p.get("affiliation"))
                for s in ai_sessions
                for p in s.get("presenters") or []
            ),
            top_n=15,
        ),
    }
    print(f"\n--- AI/ML Sessions: {len(ai_sessions)} ({result['ai_ml_analysis']['percentage_of_all']}% of all) ---")
    for title in ai_sessions[:5]:
        print(f"  - {title['title'][:80]}")
    if len(ai_sessions) > 5:
        print(f"  ... and {len(ai_sessions) - 5} more")

    # --- Accessibility testing sessions ---
    a11y_sessions = [s for s in sessions if _matches_keywords(s, A11Y_TESTING_KEYWORDS)]
    result["accessibility_testing_analysis"] = {
        "total_sessions": len(a11y_sessions),
        "percentage_of_all": round(100 * len(a11y_sessions) / len(sessions), 1) if sessions else 0,
        "titles": [s["title"] for s in a11y_sessions],
    }
    print(f"\n--- Accessibility Testing Sessions: {len(a11y_sessions)} ({result['accessibility_testing_analysis']['percentage_of_all']}%) ---")

    # --- Session format / track analysis ---
    track_counter = Counter(s.get("track", "Unknown") or "Unknown" for s in sessions)
    result["track_distribution"] = _counter_to_ranked(track_counter)
    print("\n--- Track / Format Distribution ---")
    for item in result["track_distribution"]:
        print(f"  {item['name']:40s} {item['count']:4d}  ({item['percentage']}%)")

    # --- Average presenters per session ---
    presenter_counts = [len(s.get("presenters") or []) for s in sessions]
    avg_presenters = round(sum(presenter_counts) / len(presenter_counts), 2) if presenter_counts else 0
    result["avg_presenters_per_session"] = avg_presenters
    result["presenter_count_distribution"] = _counter_to_ranked(Counter(presenter_counts))
    print(f"\nAverage presenters per session: {avg_presenters}")

    # --- Presenter role distribution ---
    role_counter = Counter()
    for p in all_presenters:
        role = (p.get("role") or "Not specified").strip()
        if not role:
            role = "Not specified"
        role_counter[role] += 1
    result["presenter_role_distribution"] = _counter_to_ranked(role_counter, top_n=20)
    print("\n--- Presenter Role Distribution (top 10) ---")
    for item in result["presenter_role_distribution"][:10]:
        print(f"  {item['name']:50s} {item['count']:4d}")

    # --- Description length statistics ---
    desc_lengths = [len(s.get("description") or "") for s in sessions]
    df_desc = pd.Series(desc_lengths)
    result["description_stats"] = {
        "mean_length": round(df_desc.mean(), 1),
        "median_length": round(df_desc.median(), 1),
        "min_length": int(df_desc.min()),
        "max_length": int(df_desc.max()),
        "sessions_with_description": int((df_desc > 0).sum()),
        "sessions_without_description": int((df_desc == 0).sum()),
    }
    print(f"\nDescription length — mean: {result['description_stats']['mean_length']}, "
          f"median: {result['description_stats']['median_length']}, "
          f"max: {result['description_stats']['max_length']}")

    # --- Learning objectives ---
    with_lo = sum(1 for s in sessions if s.get("learning_objectives"))
    without_lo = len(sessions) - with_lo
    lo_counts = [len(s.get("learning_objectives") or []) for s in sessions if s.get("learning_objectives")]
    result["learning_objectives"] = {
        "sessions_with_objectives": with_lo,
        "sessions_without_objectives": without_lo,
        "avg_objectives_per_session": round(sum(lo_counts) / len(lo_counts), 2) if lo_counts else 0,
    }
    print(f"Learning objectives — with: {with_lo}, without: {without_lo}")

    return result


# ---------------------------------------------------------------------------
# Multi-year trend analysis
# ---------------------------------------------------------------------------

def analyze_multi_year(all_data: dict[int, list[dict]]) -> dict[str, Any]:
    print("\n\n" + "=" * 70)
    print("  Cross-Year Trend Analysis (2023-2026)")
    print("=" * 70)

    result: dict[str, Any] = {}

    # --- Sessions per year ---
    sessions_per_year = {y: len(s) for y, s in all_data.items()}
    result["sessions_per_year"] = sessions_per_year
    print("\n--- Sessions Per Year ---")
    for y in YEARS:
        count = sessions_per_year.get(y, 0)
        growth = ""
        prev = sessions_per_year.get(y - 1, 0)
        if prev:
            pct = round(100 * (count - prev) / prev, 1)
            growth = f"  ({'+' if pct >= 0 else ''}{pct}% YoY)"
        print(f"  {y}: {count}{growth}")

    result["yoy_growth"] = {}
    for i in range(1, len(YEARS)):
        prev_count = sessions_per_year.get(YEARS[i - 1], 0)
        curr_count = sessions_per_year.get(YEARS[i], 0)
        if prev_count:
            result["yoy_growth"][f"{YEARS[i-1]}-{YEARS[i]}"] = round(
                100 * (curr_count - prev_count) / prev_count, 1
            )

    # --- Topic trends ---
    topic_by_year: dict[str, dict[int, int]] = defaultdict(lambda: {y: 0 for y in YEARS})
    primary_by_year: dict[str, dict[int, int]] = defaultdict(lambda: {y: 0 for y in YEARS})
    for y, sessions in all_data.items():
        for s in sessions:
            if s.get("primary_topic"):
                primary_by_year[s["primary_topic"]][y] += 1
            for t in _all_topics(s):
                topic_by_year[t][y] += 1

    # Build topic share table
    topic_trends = []
    for topic, year_counts in sorted(topic_by_year.items()):
        row = {"topic": topic}
        for y in YEARS:
            total = sessions_per_year.get(y, 1)
            cnt = year_counts.get(y, 0)
            row[f"count_{y}"] = cnt
            row[f"share_{y}"] = round(100 * cnt / total, 1)
        # Calculate overall growth from first year with data to last
        first_share = next((row[f"share_{y}"] for y in YEARS if row.get(f"count_{y}", 0) > 0), 0)
        last_share = row.get(f"share_{YEARS[-1]}", 0)
        row["share_change_pp"] = round(last_share - first_share, 1) if first_share else last_share
        topic_trends.append(row)

    topic_trends.sort(key=lambda r: r.get(f"count_{YEARS[-1]}", 0), reverse=True)
    result["topic_trends"] = topic_trends

    print("\n--- Primary Topic Trends (by share %) ---")
    primary_trends = []
    for topic, year_counts in sorted(primary_by_year.items()):
        row = {"topic": topic}
        for y in YEARS:
            total = sessions_per_year.get(y, 1)
            cnt = year_counts.get(y, 0)
            row[f"count_{y}"] = cnt
            row[f"share_{y}"] = round(100 * cnt / total, 1)
        primary_trends.append(row)
    primary_trends.sort(key=lambda r: r.get(f"count_{YEARS[-1]}", 0), reverse=True)
    result["primary_topic_trends"] = primary_trends

    for row in primary_trends[:12]:
        shares = "  ".join(f"{row.get(f'share_{y}', 0):5.1f}%" for y in YEARS)
        print(f"  {row['topic']:35s} {shares}")

    # --- AI/ML trend ---
    ai_by_year = {}
    for y, sessions in all_data.items():
        ai_count = sum(1 for s in sessions if _matches_keywords(s, AI_KEYWORDS))
        ai_by_year[y] = {
            "count": ai_count,
            "percentage": round(100 * ai_count / len(sessions), 1) if sessions else 0,
        }
    result["ai_ml_trend"] = ai_by_year
    print("\n--- AI/ML Session Growth ---")
    for y in YEARS:
        info = ai_by_year.get(y, {})
        print(f"  {y}: {info.get('count', 0):4d} sessions  ({info.get('percentage', 0)}%)")

    # --- Organization trends ---
    org_by_year: dict[str, dict[int, int]] = defaultdict(lambda: {y: 0 for y in YEARS})
    for y, sessions in all_data.items():
        for s in sessions:
            orgs_in_session = set()
            for p in s.get("presenters") or []:
                org = _normalize_org(p.get("affiliation"))
                orgs_in_session.add(org)
            for org in orgs_in_session:
                org_by_year[org][y] += 1

    org_trends = []
    for org, year_counts in org_by_year.items():
        if org == "Independent / Not specified":
            continue
        total_sessions = sum(year_counts.values())
        if total_sessions < 3:
            continue
        row = {"organization": org, "total_sessions": total_sessions}
        for y in YEARS:
            row[f"sessions_{y}"] = year_counts.get(y, 0)
        # Growth from earliest presence to latest
        first_val = next((year_counts.get(y, 0) for y in YEARS if year_counts.get(y, 0) > 0), 0)
        last_val = year_counts.get(YEARS[-1], 0)
        if first_val > 0 and last_val > 0:
            row["growth_pct"] = round(100 * (last_val - first_val) / first_val, 1)
        else:
            row["growth_pct"] = None
        org_trends.append(row)

    org_trends.sort(key=lambda r: r["total_sessions"], reverse=True)
    result["organization_trends"] = org_trends[:50]

    print("\n--- Top 15 Organizations Across Years (sessions with at least one presenter) ---")
    header = "  " + f"{'Organization':35s}" + "".join(f" {y:>5}" for y in YEARS) + "  Total"
    print(header)
    for row in org_trends[:15]:
        vals = "".join(f" {row.get(f'sessions_{y}', 0):5d}" for y in YEARS)
        print(f"  {row['organization']:35s}{vals}  {row['total_sessions']:5d}")

    # --- Presenter continuity ---
    presenter_years: dict[str, set[int]] = defaultdict(set)
    presenter_orgs: dict[str, str] = {}
    for y, sessions in all_data.items():
        for s in sessions:
            for p in s.get("presenters") or []:
                name = p.get("name", "").strip()
                if name:
                    presenter_years[name].add(y)
                    if p.get("affiliation"):
                        presenter_orgs[name] = _normalize_org(p["affiliation"])

    multi_year_presenters = []
    for name, years_set in presenter_years.items():
        if len(years_set) >= 2:
            multi_year_presenters.append({
                "name": name,
                "years": sorted(years_set),
                "num_years": len(years_set),
                "organization": presenter_orgs.get(name, "Unknown"),
            })
    multi_year_presenters.sort(key=lambda r: r["num_years"], reverse=True)
    result["presenter_continuity"] = {
        "presenters_appearing_1_year": sum(1 for v in presenter_years.values() if len(v) == 1),
        "presenters_appearing_2_years": sum(1 for v in presenter_years.values() if len(v) == 2),
        "presenters_appearing_3_years": sum(1 for v in presenter_years.values() if len(v) == 3),
        "presenters_appearing_4_years": sum(1 for v in presenter_years.values() if len(v) == 4),
        "top_returning_presenters": multi_year_presenters[:30],
    }

    print("\n--- Presenter Continuity ---")
    for n in [1, 2, 3, 4]:
        cnt = sum(1 for v in presenter_years.values() if len(v) == n)
        print(f"  Appeared in {n} year(s): {cnt} presenters")
    print(f"  Top returning presenters (4 years):")
    for p in multi_year_presenters[:10]:
        if p["num_years"] == 4:
            print(f"    {p['name']:35s} ({p['organization']})")

    # --- New topics ---
    topics_first_seen: dict[str, int] = {}
    for y in YEARS:
        for s in all_data.get(y, []):
            for t in _all_topics(s):
                if t not in topics_first_seen:
                    topics_first_seen[t] = y
    new_topics_by_year: dict[int, list[str]] = defaultdict(list)
    for t, y in topics_first_seen.items():
        new_topics_by_year[y].append(t)
    result["new_topics_by_year"] = {y: sorted(new_topics_by_year.get(y, [])) for y in YEARS}
    print("\n--- New Topics by Year ---")
    for y in YEARS:
        topics = new_topics_by_year.get(y, [])
        if topics:
            print(f"  {y}: {', '.join(sorted(topics))}")

    # --- Audience level trends ---
    level_by_year = {}
    for y, sessions in all_data.items():
        level_counter = Counter(_normalize_level(s.get("audience_level", "")) for s in sessions)
        total = len(sessions)
        level_by_year[y] = {
            level: {"count": cnt, "percentage": round(100 * cnt / total, 1)}
            for level, cnt in level_counter.most_common()
        }
    result["audience_level_trends"] = level_by_year

    print("\n--- Audience Level Trends ---")
    for level in ["Beginning", "Intermediate", "Advanced", "Not specified"]:
        vals = []
        for y in YEARS:
            info = level_by_year.get(y, {}).get(level, {})
            vals.append(f"{info.get('percentage', 0):5.1f}%")
        print(f"  {level:20s} {'  '.join(vals)}")

    # --- Description quality trends ---
    desc_trends = {}
    for y, sessions in all_data.items():
        lengths = [len(s.get("description") or "") for s in sessions]
        has_lo = sum(1 for s in sessions if s.get("learning_objectives"))
        df = pd.Series(lengths)
        desc_trends[y] = {
            "mean_desc_length": round(df.mean(), 1) if len(df) else 0,
            "median_desc_length": round(df.median(), 1) if len(df) else 0,
            "sessions_with_learning_objectives": has_lo,
            "pct_with_learning_objectives": round(100 * has_lo / len(sessions), 1) if sessions else 0,
        }
    result["description_quality_trends"] = desc_trends

    print("\n--- Description Quality Trends ---")
    for y in YEARS:
        info = desc_trends[y]
        print(f"  {y}: mean length={info['mean_desc_length']}, "
              f"learning objectives={info['pct_with_learning_objectives']}%")

    return result


# ---------------------------------------------------------------------------
# Markdown report generation
# ---------------------------------------------------------------------------

def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Generate a markdown table."""
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def generate_markdown_report(analysis_2026: dict, multi_year: dict) -> str:
    lines: list[str] = []

    lines.append("# CSUN Assistive Technology Conference 2026 -- Comprehensive Report")
    lines.append("")
    lines.append("*Auto-generated analysis of CSUN AT Conference data (2023-2026)*")
    lines.append("")

    # ---- Executive summary ----
    lines.append("## Executive Summary")
    lines.append("")
    total = analysis_2026["total_sessions"]
    presenters = analysis_2026["unique_presenters"]
    orgs = analysis_2026["unique_organizations"]
    ai_count = analysis_2026["ai_ml_analysis"]["total_ai_sessions"]
    ai_pct = analysis_2026["ai_ml_analysis"]["percentage_of_all"]

    spy = multi_year["sessions_per_year"]
    growth_23_26 = round(100 * (spy[2026] - spy[2023]) / spy[2023], 1) if spy.get(2023) else 0

    lines.append(f"The 2026 CSUN AT Conference features **{total} sessions** presented by "
                 f"**{presenters} unique presenters** from **{orgs} organizations**. "
                 f"The conference has grown {growth_23_26}% in session count from 2023 to 2026.")
    lines.append("")

    ai_trend = multi_year["ai_ml_trend"]
    ai_2023 = ai_trend.get(2023, {}).get("count", 0)
    ai_2026 = ai_trend.get(2026, {}).get("count", 0)
    if ai_2023 > 0:
        ai_growth = round(100 * (ai_2026 - ai_2023) / ai_2023, 1)
        lines.append(f"**Key trend**: AI/ML-related sessions grew from {ai_2023} in 2023 to "
                     f"{ai_2026} in 2026 ({ai_growth}% growth), now representing {ai_pct}% of all sessions.")
    else:
        lines.append(f"**Key trend**: AI/ML-related sessions now number {ai_2026} ({ai_pct}% of all sessions).")
    lines.append("")

    # ---- Sessions per year ----
    lines.append("## Conference Growth")
    lines.append("")
    headers = ["Year", "Sessions", "YoY Growth"]
    rows = []
    for y in YEARS:
        cnt = spy.get(y, 0)
        growth_str = ""
        yoy = multi_year.get("yoy_growth", {}).get(f"{y-1}-{y}")
        if yoy is not None:
            growth_str = f"{'+' if yoy >= 0 else ''}{yoy}%"
        rows.append([str(y), str(cnt), growth_str])
    lines.append(_md_table(headers, rows))
    lines.append("")

    # ---- 2026 Topic distribution ----
    lines.append("## 2026 Topic Distribution")
    lines.append("")
    headers = ["Topic", "Sessions", "Share"]
    rows = []
    for item in analysis_2026["primary_topic_distribution"]:
        if item["count"] > 0:
            rows.append([item["name"], str(item["count"]), f"{item['percentage']}%"])
    lines.append(_md_table(headers, rows))
    lines.append("")

    # ---- Topic trends ----
    lines.append("## Topic Trends Across Years (Primary Topics)")
    lines.append("")
    headers = ["Topic"] + [f"{y}" for y in YEARS] + ["Change (pp)"]
    rows = []
    for row_data in multi_year.get("primary_topic_trends", [])[:15]:
        r = [row_data["topic"]]
        for y in YEARS:
            r.append(f"{row_data.get(f'count_{y}', 0)} ({row_data.get(f'share_{y}', 0)}%)")
        first_y = next((y for y in YEARS if row_data.get(f"count_{y}", 0) > 0), YEARS[0])
        change = round(row_data.get(f"share_{YEARS[-1]}", 0) - row_data.get(f"share_{first_y}", 0), 1)
        r.append(f"{'+' if change >= 0 else ''}{change}")
        rows.append(r)
    lines.append(_md_table(headers, rows))
    lines.append("")

    # ---- AI/ML ----
    lines.append("## AI/ML Sessions")
    lines.append("")
    lines.append("### Growth Over Time")
    lines.append("")
    headers = ["Year", "AI/ML Sessions", "% of All"]
    rows = []
    for y in YEARS:
        info = ai_trend.get(y, {})
        rows.append([str(y), str(info.get("count", 0)), f"{info.get('percentage', 0)}%"])
    lines.append(_md_table(headers, rows))
    lines.append("")

    lines.append("### 2026 AI/ML Session Titles")
    lines.append("")
    for title in analysis_2026["ai_ml_analysis"]["titles"]:
        lines.append(f"- {title}")
    lines.append("")

    # ---- Accessibility testing ----
    a11y = analysis_2026["accessibility_testing_analysis"]
    lines.append("## Accessibility Testing & Compliance Sessions (2026)")
    lines.append("")
    lines.append(f"**{a11y['total_sessions']}** sessions ({a11y['percentage_of_all']}%) "
                 f"relate to testing, auditing, WCAG compliance, or validation.")
    lines.append("")

    # ---- Top organizations ----
    lines.append("## Top Presenting Organizations (2026)")
    lines.append("")
    headers = ["Rank", "Organization", "Presenters"]
    rows = []
    for i, item in enumerate(analysis_2026["top_organizations"][:20], 1):
        rows.append([str(i), item["name"], str(item["count"])])
    lines.append(_md_table(headers, rows))
    lines.append("")

    # ---- Organization trends ----
    lines.append("## Organization Trends Across Years")
    lines.append("")
    headers = ["Organization"] + [str(y) for y in YEARS] + ["Total"]
    rows = []
    for row_data in multi_year.get("organization_trends", [])[:20]:
        r = [row_data["organization"]]
        for y in YEARS:
            r.append(str(row_data.get(f"sessions_{y}", 0)))
        r.append(str(row_data["total_sessions"]))
        rows.append(r)
    lines.append(_md_table(headers, rows))
    lines.append("")

    # ---- Top presenters ----
    lines.append("## Top Individual Presenters (2026)")
    lines.append("")
    headers = ["Rank", "Presenter", "Sessions"]
    rows = []
    for i, item in enumerate(analysis_2026["top_presenters"][:15], 1):
        rows.append([str(i), item["name"], str(item["count"])])
    lines.append(_md_table(headers, rows))
    lines.append("")

    # ---- Presenter continuity ----
    cont = multi_year["presenter_continuity"]
    lines.append("## Presenter Continuity")
    lines.append("")
    lines.append(f"- Presented in 1 year only: {cont['presenters_appearing_1_year']}")
    lines.append(f"- Presented in 2 years: {cont['presenters_appearing_2_years']}")
    lines.append(f"- Presented in 3 years: {cont['presenters_appearing_3_years']}")
    lines.append(f"- Presented in all 4 years: {cont['presenters_appearing_4_years']}")
    lines.append("")

    if cont["top_returning_presenters"]:
        lines.append("### Presenters Across All 4 Years")
        lines.append("")
        headers = ["Name", "Organization", "Years"]
        rows = []
        for p in cont["top_returning_presenters"]:
            if p["num_years"] == 4:
                rows.append([p["name"], p["organization"], ", ".join(str(y) for y in p["years"])])
        if rows:
            lines.append(_md_table(headers, rows))
        else:
            lines.append("*No presenters appeared in all 4 years.*")
        lines.append("")

    # ---- Audience level ----
    lines.append("## Audience Level Distribution (2026)")
    lines.append("")
    headers = ["Level", "Sessions", "Share"]
    rows = []
    for item in analysis_2026["audience_level_distribution"]:
        rows.append([item["name"], str(item["count"]), f"{item['percentage']}%"])
    lines.append(_md_table(headers, rows))
    lines.append("")

    # ---- Sessions per day ----
    lines.append("## 2026 Sessions by Day")
    lines.append("")
    headers = ["Date", "Sessions"]
    rows = [[item["date"], str(item["count"])] for item in analysis_2026["sessions_per_day"]]
    lines.append(_md_table(headers, rows))
    lines.append("")

    # ---- Description quality ----
    lines.append("## Session Description Quality Trends")
    lines.append("")
    headers = ["Year", "Mean Desc Length", "Median Desc Length", "% with Learning Objectives"]
    rows = []
    for y in YEARS:
        info = multi_year["description_quality_trends"][y]
        rows.append([
            str(y),
            str(info["mean_desc_length"]),
            str(info["median_desc_length"]),
            f"{info['pct_with_learning_objectives']}%",
        ])
    lines.append(_md_table(headers, rows))
    lines.append("")

    # ---- New topics ----
    lines.append("## New Topics by Year")
    lines.append("")
    for y in YEARS:
        topics = multi_year.get("new_topics_by_year", {}).get(y, [])
        if topics:
            lines.append(f"### {y}")
            for t in topics:
                lines.append(f"- {t}")
            lines.append("")

    lines.append("---")
    lines.append("*Report generated by csun_analytics comprehensive analysis module.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_comprehensive_analysis():
    """Run full analysis and write output files."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_data = load_all_sessions()
    all_data = _apply_normalization(all_data)

    # --- 2026 deep dive ---
    analysis_2026 = analyze_2026(all_data[2026])

    out_2026 = OUT_DIR / "analysis_2026.json"
    with open(out_2026, "w") as f:
        json.dump(analysis_2026, f, indent=2, default=str)
    print(f"\nSaved: {out_2026}")

    # --- Multi-year trends ---
    multi_year = analyze_multi_year(all_data)

    out_multi = OUT_DIR / "analysis_multi_year.json"
    with open(out_multi, "w") as f:
        json.dump(multi_year, f, indent=2, default=str)
    print(f"Saved: {out_multi}")

    # --- Markdown report ---
    md_report = generate_markdown_report(analysis_2026, multi_year)
    out_md = OUT_DIR / "conference_report_2026.md"
    with open(out_md, "w") as f:
        f.write(md_report)
    print(f"Saved: {out_md}")

    print("\n" + "=" * 70)
    print("  Analysis complete. All reports saved to data/processed/")
    print("=" * 70)


if __name__ == "__main__":
    run_comprehensive_analysis()
