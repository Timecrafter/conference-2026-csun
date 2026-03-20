"""LLM-based topic normalizer for CSUN conference session data.

Uses Claude to build a canonical topic taxonomy from the varied topic strings
across conference years (2023-2026), then applies it to normalize session data
and classify sessions with missing topics.
"""

import copy
import json
import logging
from pathlib import Path

import anthropic

from csun_analytics.data import load_all_sessions_flat, PROCESSED_DIR, RAW_DIR

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5-20250514"
TAXONOMY_PATH = PROCESSED_DIR / "topic_taxonomy.json"

# ---------------------------------------------------------------------------
# Step 1: Collect unique topics from all session data
# ---------------------------------------------------------------------------


def collect_unique_topics(sessions: list[dict]) -> set[str]:
    """Extract all unique non-empty topic strings across primary and secondary topics."""
    topics = set()
    for s in sessions:
        pt = s.get("primary_topic", "")
        if pt and pt.strip():
            topics.add(pt.strip())
        for st in s.get("secondary_topics", []):
            if st and st.strip():
                topics.add(st.strip())
    return topics


def collect_unclassified_sessions(sessions: list[dict]) -> list[dict]:
    """Return sessions that have an empty or missing primary_topic."""
    return [
        s for s in sessions
        if not (s.get("primary_topic") or "").strip()
    ]


# ---------------------------------------------------------------------------
# Step 2: Build taxonomy via Claude
# ---------------------------------------------------------------------------


def _build_taxonomy_prompt(unique_topics: list[str]) -> str:
    topics_block = "\n".join(f"- {t}" for t in sorted(unique_topics))
    return f"""You are an expert in assistive technology and accessibility conferences.

Below is a list of {len(unique_topics)} unique topic labels used across the CSUN Assistive Technology Conference from 2023 to 2026. Many are duplicates or near-duplicates that differ only in punctuation, use of "&" vs "and", or minor wording changes.

TOPIC LIST:
{topics_block}

Your task:
1. Group these into canonical topics. Merge variants that clearly refer to the same subject.
2. Pick a single canonical name for each group — prefer the clearest, most concise version.
3. Write a one-sentence description of what each canonical topic covers.

Return ONLY valid JSON with this structure (no markdown fences):
{{
  "canonical_topics": {{
    "Canonical Topic Name": {{
      "variants": ["variant 1", "variant 2"],
      "description": "One-sentence description."
    }}
  }}
}}

Important:
- Every topic from the input list must appear in exactly one group's variants list.
- The canonical name should also appear in its own variants list.
- Use title case for canonical names.
- Keep it practical — don't over-split or over-merge."""


def _build_classification_prompt(
    sessions_batch: list[dict], canonical_names: list[str]
) -> str:
    topics_list = "\n".join(f"- {t}" for t in sorted(canonical_names))
    sessions_block = json.dumps(
        [
            {
                "session_id": str(s.get("session_id", "")),
                "title": s.get("title", ""),
                "description": (s.get("description") or s.get("abstract") or "")[:500],
                "secondary_topics": s.get("secondary_topics", []),
            }
            for s in sessions_batch
        ],
        indent=2,
    )
    return f"""You are classifying sessions from the CSUN Assistive Technology Conference.

CANONICAL TOPICS:
{topics_list}

SESSIONS TO CLASSIFY:
{sessions_block}

For each session, determine the single best-fit canonical topic based on the title, description, and secondary topics. Return ONLY valid JSON (no markdown fences):
{{
  "classifications": [
    {{
      "session_id": "...",
      "suggested_primary": "Canonical Topic Name",
      "confidence": 0.85
    }}
  ]
}}

Rules:
- suggested_primary MUST be one of the canonical topics listed above.
- confidence is 0.0-1.0 reflecting how certain you are.
- If truly ambiguous, pick the best fit and set confidence below 0.5."""


def _call_claude(prompt: str) -> str:
    """Send a prompt to Claude and return the text response."""
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_json_response(text: str) -> dict:
    """Parse JSON from Claude's response, stripping markdown fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (with optional language tag) and closing fence
        lines = cleaned.split("\n")
        lines = lines[1:]  # drop opening ```json or ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


def build_taxonomy(unique_topics: set[str]) -> dict:
    """Call Claude to create the canonical topic taxonomy."""
    logger.info("Requesting taxonomy from Claude for %d unique topics...", len(unique_topics))
    prompt = _build_taxonomy_prompt(sorted(unique_topics))
    response_text = _call_claude(prompt)
    taxonomy = _parse_json_response(response_text)

    # Build the reverse mapping: variant -> canonical
    variant_to_canonical = {}
    for canonical, info in taxonomy["canonical_topics"].items():
        for variant in info["variants"]:
            variant_to_canonical[variant] = canonical

    taxonomy["variant_to_canonical"] = variant_to_canonical

    # Verify all input topics are covered
    missing = unique_topics - set(variant_to_canonical.keys())
    if missing:
        logger.warning(
            "%d input topics not mapped by Claude: %s",
            len(missing),
            sorted(missing)[:10],
        )

    return taxonomy


# ---------------------------------------------------------------------------
# Step 3: Classify sessions with missing primary_topic
# ---------------------------------------------------------------------------


def classify_empty_sessions(
    sessions: list[dict], canonical_names: list[str], batch_size: int = 20
) -> dict:
    """Classify sessions that lack a primary_topic, batching API calls."""
    reclassifications = {}
    total = len(sessions)
    if total == 0:
        return reclassifications

    logger.info("Classifying %d sessions with empty primary_topic...", total)

    for i in range(0, total, batch_size):
        batch = sessions[i : i + batch_size]
        logger.info("  Batch %d-%d of %d", i + 1, min(i + batch_size, total), total)
        prompt = _build_classification_prompt(batch, canonical_names)
        response_text = _call_claude(prompt)
        result = _parse_json_response(response_text)

        for item in result.get("classifications", []):
            sid = str(item["session_id"])
            reclassifications[sid] = {
                "original_primary": "",
                "suggested_primary": item["suggested_primary"],
                "confidence": item.get("confidence", 0.0),
            }

    return reclassifications


# ---------------------------------------------------------------------------
# Step 4: Apply taxonomy to sessions
# ---------------------------------------------------------------------------


def normalize_session_topics(sessions: list[dict], taxonomy: dict) -> list[dict]:
    """Return copies of sessions with topics mapped to canonical names.

    - primary_topic is replaced with its canonical equivalent.
    - secondary_topics are each replaced with their canonical equivalent.
    - Sessions with empty primary_topic get the suggested reclassification
      (if available and confidence >= 0.5).
    """
    v2c = taxonomy.get("variant_to_canonical", {})
    reclassifications = taxonomy.get("session_reclassifications", {})

    normalized = []
    for s in sessions:
        ns = copy.deepcopy(s)

        # Normalize primary topic
        pt = (ns.get("primary_topic") or "").strip()
        if pt and pt in v2c:
            ns["primary_topic"] = v2c[pt]
        elif not pt:
            # Try reclassification
            sid = str(ns.get("session_id", ""))
            reclass = reclassifications.get(sid, {})
            if reclass.get("confidence", 0) >= 0.5:
                ns["primary_topic"] = reclass["suggested_primary"]

        # Normalize secondary topics
        ns["secondary_topics"] = [
            v2c.get(st.strip(), st.strip())
            for st in ns.get("secondary_topics", [])
            if st and st.strip()
        ]

        normalized.append(ns)

    return normalized


# ---------------------------------------------------------------------------
# Step 5: Orchestration
# ---------------------------------------------------------------------------


def save_taxonomy(taxonomy: dict) -> Path:
    """Write taxonomy to disk."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(TAXONOMY_PATH, "w") as f:
        json.dump(taxonomy, f, indent=2, ensure_ascii=False)
    logger.info("Taxonomy saved to %s", TAXONOMY_PATH)
    return TAXONOMY_PATH


def load_taxonomy() -> dict | None:
    """Load existing taxonomy from disk, or return None."""
    if TAXONOMY_PATH.exists():
        with open(TAXONOMY_PATH) as f:
            return json.load(f)
    return None


def run_normalization(force: bool = False) -> dict:
    """Main entry point. Builds or loads the topic taxonomy and returns it.

    Args:
        force: If True, rebuild the taxonomy even if a cached version exists.

    Returns:
        The complete taxonomy dict.
    """
    # Check cache
    if not force:
        existing = load_taxonomy()
        if existing is not None:
            logger.info("Using cached taxonomy from %s", TAXONOMY_PATH)
            return existing

    # Load all sessions
    sessions = load_all_sessions_flat()
    if not sessions:
        raise RuntimeError("No session data found. Run scrapers first.")

    logger.info("Loaded %d sessions across all years.", len(sessions))

    # Collect unique topics
    unique_topics = collect_unique_topics(sessions)
    logger.info("Found %d unique topic strings.", len(unique_topics))

    # Build taxonomy via Claude
    taxonomy = build_taxonomy(unique_topics)

    # Classify sessions with empty primary_topic
    unclassified = collect_unclassified_sessions(sessions)
    canonical_names = sorted(taxonomy["canonical_topics"].keys())
    reclassifications = classify_empty_sessions(unclassified, canonical_names)
    taxonomy["session_reclassifications"] = reclassifications

    logger.info(
        "Taxonomy complete: %d canonical topics, %d reclassifications.",
        len(taxonomy["canonical_topics"]),
        len(reclassifications),
    )

    # Save
    save_taxonomy(taxonomy)
    return taxonomy


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Build/apply CSUN topic taxonomy")
    parser.add_argument(
        "--force", action="store_true", help="Rebuild taxonomy even if cached"
    )
    args = parser.parse_args()

    taxonomy = run_normalization(force=args.force)
    print(f"\nCanonical topics ({len(taxonomy['canonical_topics'])}):")
    for name in sorted(taxonomy["canonical_topics"]):
        info = taxonomy["canonical_topics"][name]
        print(f"  {name} ({len(info['variants'])} variants)")
    print(f"\nReclassified sessions: {len(taxonomy.get('session_reclassifications', {}))}")
