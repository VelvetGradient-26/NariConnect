"""Build a cleaned, normalized SQLite database of the schemes from the backup.

Reads backend/data/nariconnect_data.sqlite (read-only; see backup_data.py) and writes backend/data/schemes.sqlite:
  - one row per distinct scheme, with lookup tables for states, categories, tags, ministries, departments, ...
  - every piece of text normalized (entities, invisible characters, whitespace) and all rich text as
    GitHub-flavoured markdown
  - a data_issues table listing every value that is missing, was dropped, or was repaired by a guess

The output is derived, so rebuilding replaces it.

Usage (from backend/):
  uv run python scripts/build_clean_db.py
"""
import argparse
import collections
import hashlib
import html
import json
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlsplit

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_SOURCE = os.path.join(BACKEND_DIR, "data", "nariconnect_data.sqlite")
DEFAULT_OUT = os.path.join(BACKEND_DIR, "data", "schemes.sqlite")
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE build_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

-- Lookup tables. myscheme_id is myScheme's own identifier, where it has one.
CREATE TABLE states (
    id INTEGER PRIMARY KEY,
    myscheme_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE ministries (
    id INTEGER PRIMARY KEY,
    myscheme_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE
) STRICT;

-- Department names repeat across states, so they are identified by myScheme id, not name
CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    myscheme_id INTEGER UNIQUE,                       -- NULL when myScheme gives none
    name TEXT NOT NULL,
    state_id INTEGER REFERENCES states (id),          -- set when every scheme it runs belongs to one state
    ministry_id INTEGER REFERENCES ministries (id)    -- set when every scheme it runs names one ministry
) STRICT;

CREATE TABLE categories (
    id INTEGER PRIMARY KEY,
    myscheme_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE
) STRICT;

-- myScheme's category -> subcategory lists are partial and overlap, so subcategories stand alone
CREATE TABLE subcategories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
) STRICT;

CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
) STRICT;

-- Who can apply: individual, family, business-entity, self-help-groups, ...
CREATE TABLE beneficiary_types (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE schemes (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE,                                 -- myscheme.gov.in/schemes/<slug>; NULL when unknown
    myscheme_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    short_title TEXT,
    brief_description TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('central', 'state')),
    state_id INTEGER REFERENCES states (id),          -- the state running the scheme; NULL for central schemes
    scheme_for TEXT CHECK (scheme_for IN ('individual', 'family', 'infra')),
    available_in_all_states INTEGER NOT NULL CHECK (available_in_all_states IN (0, 1)),  -- else see scheme_beneficiary_states
    benefit_type TEXT CHECK (benefit_type IN ('cash', 'in_kind', 'composite')),
    nodal_ministry_id INTEGER REFERENCES ministries (id),
    nodal_department_id INTEGER REFERENCES departments (id),
    implementing_agency TEXT,
    is_dbt INTEGER CHECK (is_dbt IN (0, 1)),          -- paid by direct benefit transfer; NULL when unknown
    open_date TEXT CHECK (open_date IS NULL OR date(open_date) IS open_date),
    close_date TEXT CHECK (close_date IS NULL OR date(close_date) IS close_date),
    image_url TEXT
) STRICT;
CREATE INDEX schemes_state ON schemes (state_id);
CREATE INDEX schemes_ministry ON schemes (nodal_ministry_id);
CREATE INDEX schemes_department ON schemes (nodal_department_id);

-- The long sections, as markdown. Schemes without detailed data have no row.
CREATE TABLE scheme_content (
    scheme_id INTEGER PRIMARY KEY REFERENCES schemes (id),
    description_md TEXT NOT NULL,
    benefits_md TEXT NOT NULL,
    eligibility_md TEXT,                              -- NULL where the source section was lost (see data_issues)
    exclusions_md TEXT
) STRICT;

CREATE TABLE application_channels (
    scheme_id INTEGER NOT NULL REFERENCES schemes (id),
    position INTEGER NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('online', 'offline', 'online_csc')),  -- online_csc: through a Common Service Centre
    url TEXT,
    steps_md TEXT NOT NULL,
    PRIMARY KEY (scheme_id, position)
) STRICT;

CREATE TABLE scheme_references (
    scheme_id INTEGER NOT NULL REFERENCES schemes (id),
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT,                                         -- NULL when the source value wasn't a web address
    PRIMARY KEY (scheme_id, position)
) STRICT;

CREATE TABLE scheme_definitions (
    scheme_id INTEGER NOT NULL REFERENCES schemes (id),
    position INTEGER NOT NULL,
    term TEXT NOT NULL,
    definition_md TEXT NOT NULL,
    source TEXT,                                      -- a URL or a citation
    PRIMARY KEY (scheme_id, position)
) STRICT;

CREATE TABLE scheme_categories (
    scheme_id INTEGER NOT NULL REFERENCES schemes (id),
    category_id INTEGER NOT NULL REFERENCES categories (id),
    PRIMARY KEY (scheme_id, category_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX scheme_categories_category ON scheme_categories (category_id);

CREATE TABLE scheme_subcategories (
    scheme_id INTEGER NOT NULL REFERENCES schemes (id),
    subcategory_id INTEGER NOT NULL REFERENCES subcategories (id),
    PRIMARY KEY (scheme_id, subcategory_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX scheme_subcategories_subcategory ON scheme_subcategories (subcategory_id);

CREATE TABLE scheme_tags (
    scheme_id INTEGER NOT NULL REFERENCES schemes (id),
    tag_id INTEGER NOT NULL REFERENCES tags (id),
    PRIMARY KEY (scheme_id, tag_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX scheme_tags_tag ON scheme_tags (tag_id);

CREATE TABLE scheme_beneficiary_types (
    scheme_id INTEGER NOT NULL REFERENCES schemes (id),
    beneficiary_type TEXT NOT NULL REFERENCES beneficiary_types (code),
    PRIMARY KEY (scheme_id, beneficiary_type)
) STRICT, WITHOUT ROWID;
CREATE INDEX scheme_beneficiary_types_type ON scheme_beneficiary_types (beneficiary_type);

-- States whose residents can benefit, for schemes not available in all states
CREATE TABLE scheme_beneficiary_states (
    scheme_id INTEGER NOT NULL REFERENCES schemes (id),
    state_id INTEGER NOT NULL REFERENCES states (id),
    PRIMARY KEY (scheme_id, state_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX scheme_beneficiary_states_state ON scheme_beneficiary_states (state_id);

-- Bodies involved besides the nodal ministry/department
CREATE TABLE scheme_other_ministries (
    scheme_id INTEGER NOT NULL REFERENCES schemes (id),
    ministry_id INTEGER NOT NULL REFERENCES ministries (id),
    PRIMARY KEY (scheme_id, ministry_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE scheme_other_departments (
    scheme_id INTEGER NOT NULL REFERENCES schemes (id),
    department_id INTEGER NOT NULL REFERENCES departments (id),
    PRIMARY KEY (scheme_id, department_id)
) STRICT, WITHOUT ROWID;

-- Every value that is missing, was dropped, or was repaired by a guess
CREATE TABLE data_issues (
    id INTEGER PRIMARY KEY,
    scheme_id INTEGER REFERENCES schemes (id),        -- NULL for issues not tied to one scheme
    field TEXT NOT NULL,
    issue TEXT NOT NULL,
    original_value TEXT
) STRICT;
CREATE INDEX data_issues_scheme ON data_issues (scheme_id);
"""

# ---------------------------------------------------------------------------
# Text cleaning

# Only semicolon-terminated references: html.unescape() on a whole string would also decode
# HTML5's legacy names without a semicolon (e.g. "&notice" -> "¬ice")
ENTITY_RE = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")
BR_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
# Invisible characters with no meaning here. ZWNJ/ZWJ (U+200C/U+200D) are kept: Indic scripts use them.
INVISIBLE = dict.fromkeys(map(ord, "­​‎‏⁠﻿"))


def normalize_chars(s: str) -> str:
    """Decode entities (repeatedly: the source escapes some several times), drop invisible and control
    characters, and turn every kind of space into a plain one. Whitespace runs are left for the caller."""
    prev = None
    while prev != s:
        prev, s = s, ENTITY_RE.sub(lambda m: html.unescape(m.group(0)), s)
    s = BR_RE.sub("\n", s)
    s = unicodedata.normalize("NFC", s).translate(INVISIBLE)
    return "".join(
        c if c == "\n" else " " if c.isspace() or unicodedata.category(c) in ("Cc", "Zs") else c for c in s
    )


def clean_text(s: str | None) -> str | None:
    """A single-line value: normalized, whitespace collapsed, empty -> None."""
    if s is None:
        return None
    s = re.sub(r"\s+", " ", normalize_chars(str(s))).strip()
    return s or None


FILE_NAME_RE = re.compile(r"\.(?:pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|zip|txt)$", re.IGNORECASE)


def clean_label(s: str | None) -> str | None:
    """A tag or subcategory: clean_text, minus stray separators left at the end ("Financial Assistance,")."""
    s = clean_text(s)
    return clean_text(s.rstrip(",;:")) if s else None


def clean_url(raw: str | None) -> tuple[str | None, str | None]:
    """A usable http(s) URL, and a note when the value had to be repaired or was dropped."""
    s = clean_text(raw)
    if not s:
        return None, None
    notes = []
    s = s.strip("'\"")
    if s.lower().startswith("blob:"):
        return None, "a browser-local blob: address; dropped"
    s = re.sub(r"^(https?:/+)\s+", r"\1", s, flags=re.IGNORECASE)  # "http:/ /www.example.in"
    # e.g. "chrome-extension://efaidnhttps://cdn.example/a.pdf" (a URL copied from a PDF viewer)
    embedded = re.search(r"https?://", s[1:], re.IGNORECASE)
    if not re.match(r"https?://", s, re.IGNORECASE) and embedded:
        s = s[embedded.start() + 1 :]
        notes.append("took the address embedded in the value")
    fixed = re.sub(r"^(https?):?/{1,2}(?=[^/])", r"\1://", s, flags=re.IGNORECASE)
    if fixed != s:
        s = fixed
        notes.append("fixed a malformed http:// prefix")
    # "www.a.gov.in / www.b.in": keep the first address
    parts = re.split(r"\s+(?:/\s+)?(?=(?:https?://|www\.))", s)
    if len(parts) > 1:
        s = parts[0]
        notes.append("kept the first of several addresses")
    s = s.rstrip(".,;").replace(" ", "%20")
    host = re.split(r"[/?#]", s, maxsplit=1)[0]
    if (
        not re.match(r"[a-z][a-z0-9+.-]*:", s, re.IGNORECASE)
        and re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host, re.IGNORECASE)
        and not FILE_NAME_RE.search(host)
    ):
        s = "http://" + s
        notes.append("added http:// to a bare domain")
    parts = urlsplit(s)
    if parts.scheme.lower() not in ("http", "https") or not re.fullmatch(
        r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\.?(?::\d+)?", parts.netloc
    ):
        return None, "not a web address; dropped"
    return s, "; ".join(notes) or None


# ---------------------------------------------------------------------------
# Rich text (myScheme's editor node trees) -> GitHub-flavoured markdown

HEADINGS = {"heading_two": 2, "heading_three": 3, "heading_four": 4, "heading_five": 5}
CONTAINERS = {"align_justify", "align_left", "align_center"}  # alignment wrappers; markdown has no alignment
MARKS = ("bold", "italic")  # underline, superscript and subscript have no markdown form: their text stays plain
URL_IN_TEXT_RE = re.compile(r"(?:https?://|www\.)[^\s<>]+", re.IGNORECASE)
CLOSERS = {")": "(", "]": "[", "}": "{"}
BLOCK_START_RE = re.compile(r"^(?:[#>+=-]|\d{1,9}[.)])")


def link_target(node: dict) -> str:
    return node.get("link") or node.get("href") or node.get("url") or ""


# Link targets repaired or dropped by the last render_rich() call: original value -> note
_link_notes: dict[str, str] = {}


def link_url(target: str) -> str | None:
    url, note = clean_url(target)
    if note:
        _link_notes[target] = note
    return url


def md_escape(s: str, in_table: bool = False, in_label: bool = False) -> str:
    """Escape text so markdown shows it literally. Web addresses in it become links (except inside a link's text)."""
    out, pos = [], 0
    for m in URL_IN_TEXT_RE.finditer(s):
        url = _strip_trailing(m.group(0))
        if not re.match(r"(?:https?://|www\.)[^/?#]*\.[^/?#.]", url, re.IGNORECASE):
            continue  # not an address after all ("www." alone); escaped as text below
        out.append(_escape_chars(s[pos : m.start()], in_table))
        out.append(_address(url, in_table, in_label))
        pos = m.start() + len(url)
    out.append(_escape_chars(s[pos:], in_table))
    return "".join(out)


def _strip_trailing(url: str) -> str:
    """Like GFM, trailing punctuation and unbalanced closing brackets aren't part of an address."""
    end = len(url)
    while end:
        c = url[end - 1]
        if c in "?!.,:;*_~'\"" or (c in CLOSERS and url[:end].count(c) > url[:end].count(CLOSERS[c])):
            end -= 1
        else:
            break
    return url[:end]


def _address(url: str, in_table: bool, in_label: bool) -> str:
    """GFM's bare-URL links run to the next whitespace and ignore escapes, so they swallow whatever follows
    ("https://x.in]," or a link's closing "]("). Give every address an explicit end instead."""
    if in_label:
        # Inside a link's text the address is just text: break it up so it isn't linked a second time
        text = _escape_chars(url, in_table)
        return re.sub(r"^(https?):|^(www)\.", lambda m: f"{m.group(1)}\\:" if m.group(1) else "www\\.", text, flags=re.IGNORECASE)
    if url.lower().startswith("www."):
        label = "www\\." + _escape_chars(url[4:], in_table)
        return f"[{label}]({_encode_destination('http://' + url)})"  # GFM links www. addresses with http:// too
    return "<" + (url.replace("|", "\\|") if in_table else url) + ">"


def _escape_chars(s: str, in_table: bool) -> str:
    out = []
    for i, c in enumerate(s):
        if c in "\\`*[]~" or (c == "|" and in_table):
            out.append("\\" + c)
        elif c == "_" and not (0 < i < len(s) - 1 and s[i - 1].isalnum() and s[i + 1].isalnum()):
            out.append("\\_")  # intraword underscores never make emphasis in GFM
        elif c == "<" and i + 1 < len(s) and (s[i + 1].isalpha() or s[i + 1] in "/!?"):
            out.append("\\<")  # would otherwise start raw HTML, which the frontend's renderer drops
        else:
            out.append(c)
    return "".join(out)


def escape_block_start(s: str) -> str:
    """Stop a paragraph or list item that starts with "#", "-", "1." etc. from becoming another block."""
    m = BLOCK_START_RE.match(s)
    if not m:
        return s
    at = m.end() - 1 if m.group(0)[0].isdigit() else 0
    return s[:at] + "\\" + s[at:]


def _is_edge(c: str) -> bool:
    return c.isspace() or unicodedata.category(c)[0] in "PS"


def emphasize(text: str, marks: frozenset, in_table: bool, in_label: bool) -> str:
    """Wrap text in ** / * with edge whitespace and punctuation moved outside the markers:
    CommonMark won't close "**Step 1:**Apply" or "**Note: **"."""
    i, j = 0, len(text)
    while i < j and _is_edge(text[i]):
        i += 1
    while j > i and _is_edge(text[j - 1]):
        j -= 1
    if not marks or i == j:
        return md_escape(text, in_table, in_label)
    marker = "*" * (("bold" in marks) * 2 + ("italic" in marks))
    return (
        md_escape(text[:i], in_table, in_label) + marker + md_escape(text[i:j], in_table, in_label) + marker
        + md_escape(text[j:], in_table, in_label)
    )


def collect_runs(nodes: list, href: str | None = None, out: list | None = None) -> list:
    """Flatten inline nodes into (text, marks, link target) runs."""
    if out is None:
        out = []
    for n in nodes:
        if "type" not in n:
            if "text" in n:
                text = normalize_chars(n["text"]).replace("\n", " ")
                out.append((text, frozenset(m for m in MARKS if n.get(m)), href))
        elif n["type"] == "link":
            target = href or link_target(n)
            start = len(out)
            collect_runs(n.get("children", []), target, out)
            if not "".join(r[0] for r in out[start:]).strip():
                url = link_url(target)
                if url:
                    out.append((url, frozenset(), target))
        else:
            # A block inside inline content (malformed source): keep its words apart
            out.append((" ", frozenset(), href))
            collect_runs(n.get("children", []), href, out)
            out.append((" ", frozenset(), href))
    return out


def inline(nodes: list, in_table: bool = False) -> str:
    """Markdown for inline content, on one line."""
    pieces = []
    for href, group in _group(collect_runs(nodes), key=lambda r: r[2]):
        url = link_url(href) if href else None
        md, prev_marked = [], False
        for marks, runs in _group(group, key=lambda r: r[1]):
            text = "".join(r[0] for r in runs)
            plain = md_escape(text, in_table, in_label=bool(url))
            piece = emphasize(text, marks, in_table, in_label=bool(url))
            # Markers from two differently marked runs must not touch ("**a***b*")
            if prev_marked and piece.startswith("*") and md and md[-1].endswith("*"):
                piece = plain
            prev_marked = piece != plain
            md.append(piece)
        text_md = "".join(md)
        if url and text_md.strip():
            lead = text_md[: len(text_md) - len(text_md.lstrip())]
            trail = text_md[len(text_md.rstrip()) :]
            text_md = f"{lead}[{text_md.strip()}]({_encode_destination(url)}){trail}"
        pieces.append(text_md)
    return re.sub(r"\s+", " ", "".join(pieces)).strip()


def _group(items, key):
    groups = []
    for item in items:
        k = key(item)
        if groups and groups[-1][0] == k:
            groups[-1][1].append(item)
        else:
            groups.append((k, [item]))
    return groups


def _encode_destination(url: str) -> str:
    for c, code in ((" ", "%20"), ("(", "%28"), (")", "%29"), ("<", "%3C"), (">", "%3E"), ("|", "%7C"), ("\\", "%5C")):
        url = url.replace(c, code)
    return url


def _flatten(nodes: list):
    for n in nodes:
        if n.get("type") in CONTAINERS:
            yield from _flatten(n.get("children", []))
        else:
            yield n


def render_blocks(nodes: list) -> list[str]:
    out, inline_run, item_run = [], [], []

    def flush():
        if inline_run:
            out.append(escape_block_start(inline(inline_run)))
            inline_run.clear()
        if item_run:
            out.append(render_list(item_run, ordered=False))
            item_run.clear()

    for n in _flatten(nodes):
        t = n.get("type")
        if t is None or t == "link":  # inline content outside a block
            if item_run:
                flush()
            inline_run.append(n)
            continue
        if t == "list_item":  # an item outside a list: treat a run of them as a bulleted list
            if inline_run:
                flush()
            item_run.append(n)
            continue
        flush()
        children = n.get("children", [])
        if t in ("paragraph", "table_cell", "table_row"):
            out.append(escape_block_start(inline(children)))
        elif t in HEADINGS:
            text = inline(children)
            if text.endswith("#"):
                text = text[:-1] + "\\#"  # a trailing # would be read as a closing sequence
            out.append(f"{'#' * HEADINGS[t]} {text}" if text else "")
        elif t == "block_quote":
            text = inline(children)
            out.append(f"> {escape_block_start(text)}" if text else "")
        elif t in ("ol_list", "ul_list"):
            out.append(render_list(children, ordered=t == "ol_list"))
        elif t == "table":
            out.append(render_table(n))
        else:
            raise ValueError(f"unknown rich-text node type {t!r}")
    flush()
    return [b for b in out if b]


def render_list(nodes: list, ordered: bool) -> str:
    items = []  # [text, [(kind, block)]]
    leading = []  # nested lists/tables before the first item, e.g. a list that only wraps another list

    def attach(kind: str, block: str):
        """Nested lists and tables belong to the preceding item. Before any item, they are rendered in place:
        an empty item ("1." alone) can't interrupt a paragraph, so CommonMark would print it as text."""
        (items[-1][1] if items else leading).append((kind, block))

    for n in _flatten(nodes):
        t = n.get("type")
        if t in ("ol_list", "ul_list"):
            sub = render_list(n.get("children", []), t == "ol_list")
            if sub:
                attach("nested", sub)
        elif t == "table":
            table = render_table(n)
            if table:
                attach("block", table)
        else:  # list_item, or a paragraph/quote/heading/inline node standing in for one
            text = inline(n.get("children", []) if t not in (None, "link") else [n])
            if text:
                items.append([text, []])
    out = [(kind, block) for kind, block in leading]
    for number, (text, extras) in enumerate(items, 1):
        marker = f"{number}." if ordered else "-"
        pad = " " * (len(marker) + 1)
        item = f"{marker} {escape_block_start(text)}"
        for kind, block in extras:
            indented = "\n".join(pad + line if line else line for line in block.split("\n"))
            item += ("\n" if kind == "nested" else "\n\n") + indented
        out.append(("item", item))
    # Tables need blank lines around them; lists and items don't
    md = ""
    for i, (kind, block) in enumerate(out):
        if i:
            md += "\n\n" if "block" in (kind, out[i - 1][0]) else "\n"
        md += block
    return md


def render_table(node: dict) -> str:
    rows = []

    def add_rows(n):
        t = n.get("type")
        if t == "table":
            for child in n.get("children", []):
                add_rows(child)
        elif t == "table_row":
            # A nested table or row in a row stands in for one cell; GFM tables can't nest, so it becomes that cell's text
            rows.append([
                inline([c] if c.get("type") in ("table", "table_row", None) else c.get("children", []), in_table=True)
                for c in n.get("children", [])
            ])
        else:
            rows.append([inline(n.get("children", []) if t else [n], in_table=True)])

    add_rows(node)
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def render_rich(nodes) -> str | None:
    _link_notes.clear()
    if not isinstance(nodes, list):
        return None
    return "\n\n".join(render_blocks(nodes)) or None


# ---------------------------------------------------------------------------
# Building the database


class Issues:
    def __init__(self):
        self.rows = []

    def add(self, scheme_id, field, issue, original=None):
        if original is not None and not isinstance(original, str):
            original = json.dumps(original, ensure_ascii=False)
        self.rows.append((scheme_id, field, issue, original))


def canonical_spellings(names_by_scheme: list[list[str]]) -> dict[str, str]:
    """Case-insensitive dedupe: each lowercased name maps to its most common spelling."""
    counts = collections.Counter(n for names in names_by_scheme for n in names)
    best = {}
    for name, count in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        best.setdefault(name.casefold(), name)
    return best


def load_source(path: str):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        basic = [json.loads(r) for (r,) in con.execute("SELECT record_json FROM schemes ORDER BY row_index")]
        details = [json.loads(r) for (r,) in con.execute("SELECT doc_json FROM scheme_details ORDER BY export_index")]
    finally:
        con.close()
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    return basic, details, digest


def build(source_path: str, out_path: str):
    basic, details, source_sha = load_source(source_path)
    issues = Issues()

    # One record per myScheme id; the source repeats some records exactly
    records, seen = [], {}
    for rec in basic:
        if rec["id"] in seen:
            if seen[rec["id"]] != rec:
                raise ValueError(f"myScheme id {rec['id']} has two different records")
            continue
        seen[rec["id"]] = rec
        records.append(rec)
    duplicates_dropped = len(basic) - len(records)

    details_by_slug = {d["slug"]: d for d in details}
    by_slug = collections.defaultdict(list)
    for rec in records:
        by_slug[rec["fields"]["slug"]].append(rec)

    # --- lookups, gathered from every record and document
    states, ministries, categories = {}, {}, {}
    for d in details:
        bd = d["basicDetails"]
        if bd.get("state"):
            states[clean_text(bd["state"]["label"])] = bd["state"]["value"]
        for m in [bd.get("nodalMinistryName")] + (bd.get("otherMinistryName") or []):
            if m:
                ministries[clean_text(m["label"])] = m["value"]
        for c in bd.get("schemeCategory", []):
            categories[clean_text(c["label"])] = c["value"]
    if len(set(states.values())) != len(states) or len(set(ministries.values())) != len(ministries):
        raise ValueError("a state or ministry name maps to more than one myScheme id")

    department_labels = collections.defaultdict(collections.Counter)  # key -> label counts
    for d in details:
        bd = d["basicDetails"]
        for dept in [bd.get("nodalDepartmentName")] + (bd.get("otherDepartmentNames") or []):
            if dept:
                label = clean_text(dept["label"])
                department_labels[dept.get("value") or ("name", label)][label] += 1
    department_names = {}
    for key, labels in department_labels.items():
        name, _ = sorted(labels.items(), key=lambda x: (-x[1], x[0]))[0]
        department_names[key] = name
        for other in sorted(set(labels) - {name}):
            issues.add(None, "departments.name", f"myScheme department {key} also appears as this name; kept {name!r}", other)

    tag_spelling = canonical_spellings(
        [[clean_label(t) for t in r["fields"].get("tags", []) if clean_label(t)] for r in records]
    )
    subcategory_spelling = canonical_spellings(
        [[clean_label(s["label"]) for s in d["basicDetails"].get("schemeSubCategory", []) if clean_label(s["label"])] for d in details]
    )
    beneficiary_labels = collections.defaultdict(collections.Counter)
    for d in details:
        for b in d["basicDetails"].get("targetBeneficiaries", []):
            beneficiary_labels[b["value"]][clean_text(b["label"])] += 1
    beneficiary_types = {}
    for code, labels in beneficiary_labels.items():
        name, _ = sorted(labels.items(), key=lambda x: (-x[1], x[0]))[0]
        beneficiary_types[code] = name
        for other in sorted(set(labels) - {name}):
            issues.add(None, "beneficiary_types.name", f"beneficiary type {code!r} also appears as this name; kept {name!r}", other)

    state_ids = {name: i for i, name in enumerate(sorted(states, key=lambda n: states[n]), 1)}
    ministry_ids = {name: i for i, name in enumerate(sorted(ministries), 1)}
    category_ids = {name: i for i, name in enumerate(sorted(categories), 1)}
    department_ids = {key: i for i, key in enumerate(sorted(department_names, key=lambda k: (department_names[k], str(k))), 1)}
    tag_ids = {key: i for i, key in enumerate(sorted(tag_spelling, key=lambda k: tag_spelling[k].casefold()), 1)}
    subcategory_ids = {key: i for i, key in enumerate(sorted(subcategory_spelling, key=lambda k: subcategory_spelling[k].casefold()), 1)}

    # --- schemes
    schemes, content, channels, references, definitions = [], [], [], [], []
    links = collections.defaultdict(set)  # table -> {(scheme_id, other_id)}
    department_states = collections.defaultdict(set)
    department_ministries = collections.defaultdict(set)

    for scheme_id, rec in enumerate(records, 1):
        f = rec["fields"]
        slug = f["slug"]
        name = clean_text(f.get("schemeName"))
        doc = details_by_slug.get(slug)
        # When several myScheme records share a slug, the detailed document says which one owns it
        owns_slug = doc is not None and clean_text(doc["basicDetails"].get("schemeName")) == name
        if len(by_slug[slug]) > 1 and not owns_slug:
            issues.add(scheme_id, "slug", "myScheme lists this scheme under a slug that belongs to another scheme; its real slug is unknown", slug)
            slug, doc = None, None
        elif doc is None:
            issues.add(scheme_id, "scheme_content", "no detailed data was scraped for this scheme")

        bd = doc["basicDetails"] if doc else {}
        sc = doc["schemeContent"] if doc else {}

        level = (f.get("level") or "").strip().lower()
        scheme_for = {"individual": "individual", "family": "family", "infra": "infra"}.get((f.get("schemeFor") or "").strip().lower())
        beneficiary_states = f.get("beneficiaryState") or []
        all_states = beneficiary_states == ["All"]
        if not beneficiary_states:
            issues.add(scheme_id, "scheme_beneficiary_states", "the source lists no beneficiary states")
        for s in beneficiary_states:
            if s != "All":
                links["scheme_beneficiary_states"].add((scheme_id, state_ids[clean_text(s)]))

        state_id = state_ids[clean_text(bd["state"]["label"])] if bd.get("state") else None
        ministry = clean_text(f.get("nodalMinistryName"))
        ministry_id = ministry_ids[ministry] if ministry else None
        dept = bd.get("nodalDepartmentName")
        department_id = None
        if dept:
            key = dept.get("value") or ("name", clean_text(dept["label"]))
            department_id = department_ids[key]
            department_states[department_id].add(state_id)
            department_ministries[department_id].add(ministry_id)

        benefit_type = None
        if sc.get("benefitTypes"):
            benefit_type = {"cash": "cash", "in kind": "in_kind", "in-kind": "in_kind", "composite": "composite"}[
                sc["benefitTypes"]["label"].strip().lower()
            ]

        open_date = bd.get("schemeOpenDate")
        if open_date == "1900-01-01":
            issues.add(scheme_id, "open_date", "placeholder date; dropped", open_date)
            open_date = None
        close_date = bd.get("schemeCloseDate") if doc else f.get("schemeCloseDate")

        image_url, note = clean_url(sc.get("schemeImageUrl"))
        if note:
            issues.add(scheme_id, "image_url", note, sc.get("schemeImageUrl"))

        schemes.append((
            scheme_id, slug, rec["id"], name, clean_text(f.get("schemeShortTitle")),
            clean_text(f.get("briefDescription")), level, state_id, scheme_for, int(all_states), benefit_type,
            ministry_id, department_id, clean_text(bd.get("implementingAgency")),
            None if bd.get("dbtScheme") is None else int(bd["dbtScheme"]), open_date, close_date, image_url,
        ))

        for c in f.get("schemeCategory", []):
            links["scheme_categories"].add((scheme_id, category_ids[clean_text(c)]))
        for t in f.get("tags", []):
            if clean_label(t):
                links["scheme_tags"].add((scheme_id, tag_ids[clean_label(t).casefold()]))

        if not doc:
            continue

        for s in bd.get("schemeSubCategory", []):
            if clean_label(s["label"]):
                links["scheme_subcategories"].add((scheme_id, subcategory_ids[clean_label(s["label"]).casefold()]))
        for b in bd.get("targetBeneficiaries", []):
            links["scheme_beneficiary_types"].add((scheme_id, b["value"]))
        for m in bd.get("otherMinistryName") or []:
            links["scheme_other_ministries"].add((scheme_id, ministry_ids[clean_text(m["label"])]))
        for dpt in bd.get("otherDepartmentNames") or []:
            links["scheme_other_departments"].add((scheme_id, department_ids[dpt.get("value") or ("name", clean_text(dpt["label"]))]))

        eligibility = doc.get("eligibilityCriteria")
        if not isinstance(eligibility, dict):
            issues.add(scheme_id, "eligibility_md", "the section was lost when the data was loaded into MongoDB", eligibility)
            eligibility = {}
        def rich(field: str, nodes) -> str | None:
            md = render_rich(nodes)
            for original, note in _link_notes.items():
                issues.add(scheme_id, f"{field} link", note, original)
            return md

        content.append((
            scheme_id, rich("description_md", sc.get("detailedDescription")), rich("benefits_md", sc.get("benefits")),
            rich("eligibility_md", eligibility.get("eligibilityDescription")), rich("exclusions_md", sc.get("exclusions")),
        ))

        process = doc.get("applicationProcess")
        if not isinstance(process, list):
            issues.add(scheme_id, "application_channels", "the section was lost when the data was loaded into MongoDB", process)
            process = []
        seen_channels = []
        for channel in process:
            mode = {"online": "online", "offline": "offline", "online - via csc": "online_csc"}[channel["mode"].strip().lower()]
            url, note = clean_url(channel.get("url"))
            steps = render_rich(channel.get("process"))
            if (mode, url, steps) in seen_channels:
                continue  # the same channel listed twice
            for original, link_note in _link_notes.items():
                issues.add(scheme_id, "application_channels.steps_md link", link_note, original)
            if any(m == mode for m, _, _ in seen_channels):
                issues.add(scheme_id, "application_channels.mode", f"the source lists {mode} more than once, with different steps")
            seen_channels.append((mode, url, steps))
            if note:
                issues.add(scheme_id, "application_channels.url", note, channel.get("url"))
            channels.append((scheme_id, len(seen_channels), mode, url, steps))

        seen_refs = []
        for ref in sc.get("references", []):
            title = clean_text(ref.get("title"))
            url, note = clean_url(ref.get("url"))
            if (title, url) in seen_refs:
                continue  # the same reference listed twice
            seen_refs.append((title, url))
            if note:
                issues.add(scheme_id, "scheme_references.url", note, ref.get("url"))
            references.append((scheme_id, len(seen_refs), title, url))

        for position, definition in enumerate(doc.get("schemeDefinitions") or [], 1):
            definitions.append((
                scheme_id, position, clean_text(definition.get("name")),
                rich("scheme_definitions.definition_md", definition.get("definition")), clean_text(definition.get("source")),
            ))

    departments = []
    for key, dept_id in department_ids.items():
        dept_states = department_states.get(dept_id, set())
        dept_ministries = department_ministries.get(dept_id, set())
        departments.append((
            dept_id, key if isinstance(key, int) else None, department_names[key],
            next(iter(dept_states)) if len(dept_states) == 1 else None,
            next(iter(dept_ministries)) if len(dept_ministries) == 1 else None,
        ))

    # --- write
    tmp_path = out_path + ".tmp"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    try:
        con = sqlite3.connect(tmp_path)
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = DELETE")
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        con.executescript(SCHEMA)
        with con:
            con.executemany("INSERT INTO states VALUES (?, ?, ?)", [(i, states[n], n) for n, i in state_ids.items()])
            con.executemany("INSERT INTO ministries VALUES (?, ?, ?)", [(i, ministries[n], n) for n, i in ministry_ids.items()])
            con.executemany("INSERT INTO departments VALUES (?, ?, ?, ?, ?)", departments)
            con.executemany("INSERT INTO categories VALUES (?, ?, ?)", [(i, categories[n], n) for n, i in category_ids.items()])
            con.executemany("INSERT INTO subcategories VALUES (?, ?)", [(i, subcategory_spelling[k]) for k, i in subcategory_ids.items()])
            con.executemany("INSERT INTO tags VALUES (?, ?)", [(i, tag_spelling[k]) for k, i in tag_ids.items()])
            con.executemany("INSERT INTO beneficiary_types VALUES (?, ?)", sorted(beneficiary_types.items()))
            con.executemany(f"INSERT INTO schemes VALUES ({', '.join('?' * 18)})", schemes)
            con.executemany("INSERT INTO scheme_content VALUES (?, ?, ?, ?, ?)", content)
            con.executemany("INSERT INTO application_channels VALUES (?, ?, ?, ?, ?)", channels)
            con.executemany("INSERT INTO scheme_references VALUES (?, ?, ?, ?)", references)
            con.executemany("INSERT INTO scheme_definitions VALUES (?, ?, ?, ?, ?)", definitions)
            for table, rows in links.items():
                con.executemany(f"INSERT INTO {table} VALUES (?, ?)", sorted(rows))
            con.executemany("INSERT INTO data_issues (scheme_id, field, issue, original_value) VALUES (?, ?, ?, ?)", issues.rows)
            info = {
                "schema_version": SCHEMA_VERSION,
                "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": os.path.relpath(source_path, BACKEND_DIR),
                "source_sha256": source_sha,
                "source_records": len(basic),
                "duplicate_records_dropped": duplicates_dropped,
                "tag_spellings_merged": len({clean_label(t) for r in records for t in r["fields"].get("tags", [])} - {None})
                - len(tag_spelling),
            }
            con.executemany("INSERT INTO build_info VALUES (?, ?)", [(k, str(v)) for k, v in info.items()])

        check(con, records, details, links, content, channels, references, definitions)
        con.close()
        os.replace(tmp_path, out_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    print(f"✅ Wrote {out_path} ({os.path.getsize(out_path) / 1e6:.1f} MB)")
    print(f"   {len(schemes)} schemes ({duplicates_dropped} repeated records dropped), {len(content)} with content")
    by_issue = collections.Counter((field, issue) for _, field, issue, _ in issues.rows)
    print(f"   {len(issues.rows)} data issues:")
    for (field, issue), count in by_issue.most_common():
        print(f"     {count:5d}  {field}: {issue}")


def check(con, records, details, links, content, channels, references, definitions):
    def one(sql):
        return con.execute(sql).fetchone()[0]

    def expect(ok, what):
        if not ok:
            raise RuntimeError(f"Check failed: {what}")

    expect(one("PRAGMA integrity_check") == "ok", "integrity_check")
    expect(not con.execute("PRAGMA foreign_key_check").fetchall(), "foreign_key_check")
    expect(one("SELECT COUNT(*) FROM schemes") == len(records), "one scheme per distinct record")
    expect(one("SELECT COUNT(*) FROM scheme_content") == len(content), "content rows")
    for table, rows in links.items():
        expect(one(f"SELECT COUNT(*) FROM {table}") == len(rows), table)
    for table, rows in (("application_channels", channels), ("scheme_references", references), ("scheme_definitions", definitions)):
        expect(one(f"SELECT COUNT(*) FROM {table}") == len(rows), table)
    # No leftover junk in any text column (data_issues.original_value keeps source values as they were)
    text_columns = [
        (t, c) for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        for (_, c, typ, *_) in con.execute(f"PRAGMA table_info({t})")
        if typ == "TEXT" and (t, c) != ("data_issues", "original_value")
    ]
    for t, c in text_columns:
        bad = one(
            f"SELECT COUNT(*) FROM {t} WHERE {c} LIKE '%&amp;%' OR {c} LIKE '%&nbsp;%' OR {c} LIKE '%<br%' "
            f"OR instr({c}, char(160)) OR instr({c}, char(8203)) OR instr({c}, char(65279)) OR instr({c}, char(12)) "
            f"OR {c} = '' OR {c} != trim({c})"
        )
        expect(bad == 0, f"{bad} dirty values in {t}.{c}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the cleaned scheme database from the backup")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Backup database to read")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Database to write (replaced if it exists)")
    args = parser.parse_args()
    build(os.path.abspath(args.source), os.path.abspath(args.out))
