"""Check the markdown in data/schemes.sqlite against the source it was rendered from.

Each markdown value is parsed the way the frontend renders it (remark-parse + remark-gfm, run with node from
frontend/) and must contain the same characters in the same order as the source's text (whitespace aside),
no raw HTML, no leftover markup or entities, only http(s)/mailto links, and the source's headings, quotes
and tables.

Usage (from backend/, after `npm install` in frontend/):
  uv run python scripts/verify_clean_db.py
"""
import argparse
import collections
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

from build_clean_db import BACKEND_DIR, DEFAULT_OUT, DEFAULT_SOURCE, HEADINGS, clean_url, link_target, normalize_chars, render_rich

FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")
CHECKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_clean_db.mjs")


def tree_text(nodes) -> str:
    """The text of a source tree, collected independently of the renderer: every text leaf, plus the
    address of links that have no text."""
    parts = []

    def walk(n):
        if isinstance(n, list):
            for x in n:
                walk(x)
        elif "type" not in n:
            parts.append(normalize_chars(n.get("text", "")))
        elif n["type"] == "link":
            start = len(parts)
            walk(n.get("children", []))
            if not "".join(parts[start:]).strip():
                url = clean_url(link_target(n))[0]
                if url:
                    parts.append(url)
        else:
            walk(n.get("children", []))

    walk(nodes or [])
    return "".join(parts)


def structure(nodes) -> dict:
    """Headings, quotes and tables the markdown must contain: those outside lists (inside a list they become
    items), with text, and tables not nested in another table (those become cell text)."""
    counts = {"heading": 0, "blockquote": 0, "table": 0}

    def walk(n, in_list=False, in_table=False):
        if isinstance(n, list):
            for x in n:
                walk(x, in_list, in_table)
            return
        t = n.get("type")
        has_text = bool(tree_text(n.get("children", [])).strip())
        if t in HEADINGS and not in_list and has_text:
            counts["heading"] += 1
        elif t == "block_quote" and not in_list and has_text:
            counts["blockquote"] += 1
        elif t == "table" and not in_table and has_text:
            counts["table"] += 1
        walk(n.get("children", []), in_list or t in ("ol_list", "ul_list"), in_table or t == "table")

    walk(nodes or [])
    return counts


def collect_pairs(db_path: str, source_path: str) -> list[dict]:
    src = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    docs = {json.loads(r)["slug"]: json.loads(r) for (r,) in src.execute("SELECT doc_json FROM scheme_details")}
    src.close()
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    slug_of = dict(db.execute("SELECT id, slug FROM schemes WHERE slug IS NOT NULL"))
    pairs = []

    def add(key, md, tree):
        expected = tree_text(tree)
        if md is None:
            if expected.strip():
                raise SystemExit(f"{key}: no markdown, but the source has text")
            return
        pairs.append({"key": key, "md": md, "expected": expected, "structure": structure(tree)})

    for scheme_id, description, benefits, eligibility, exclusions in db.execute("SELECT * FROM scheme_content"):
        doc = docs[slug_of[scheme_id]]
        sc = doc["schemeContent"]
        ec = doc["eligibilityCriteria"] if isinstance(doc.get("eligibilityCriteria"), dict) else {}
        slug = slug_of[scheme_id]
        add(f"{slug}.description", description, sc.get("detailedDescription"))
        add(f"{slug}.benefits", benefits, sc.get("benefits"))
        add(f"{slug}.eligibility", eligibility, ec.get("eligibilityDescription"))
        add(f"{slug}.exclusions", exclusions, sc.get("exclusions"))

    channels = collections.defaultdict(list)
    for scheme_id, _, mode, url, steps in db.execute("SELECT * FROM application_channels ORDER BY scheme_id, position"):
        channels[scheme_id].append(steps)
    for scheme_id, rows in channels.items():
        # The build skips channels listed twice; skip them the same way here
        sources, seen = [], []
        for c in docs[slug_of[scheme_id]]["applicationProcess"]:
            key = (c["mode"].strip().lower(), clean_url(c.get("url"))[0], render_rich(c.get("process")))
            if key not in seen:
                seen.append(key)
                sources.append(c)
        if len(sources) != len(rows):
            raise SystemExit(f"{slug_of[scheme_id]}: {len(rows)} channels, but the source has {len(sources)}")
        for i, (c, steps) in enumerate(zip(sources, rows), 1):
            add(f"{slug_of[scheme_id]}.channel{i}", steps, c["process"])

    definitions = collections.defaultdict(list)
    for scheme_id, _, _, md, _ in db.execute("SELECT * FROM scheme_definitions ORDER BY scheme_id, position"):
        definitions[scheme_id].append(md)
    for scheme_id, rows in definitions.items():
        for i, (d, md) in enumerate(zip(docs[slug_of[scheme_id]]["schemeDefinitions"], rows), 1):
            add(f"{slug_of[scheme_id]}.definition{i}", md, d["definition"])
    db.close()
    return pairs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check the clean database's markdown against its source")
    parser.add_argument("--db", default=DEFAULT_OUT, help="Clean database to check")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Backup database it was built from")
    args = parser.parse_args()

    pairs = collect_pairs(os.path.abspath(args.db), os.path.abspath(args.source))
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    try:
        with open(CHECKER, encoding="utf-8") as script:
            # Evaluated with frontend/ as the working directory, so its packages resolve
            result = subprocess.run(["node", "--input-type=module", "-e", script.read(), f.name], cwd=FRONTEND_DIR)
    finally:
        os.remove(f.name)
    sys.exit(result.returncode)
