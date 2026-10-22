"""Build a self-contained, read-only SQLite backup of the scheme data, or restore the dataset files from it.

The backup holds:
  - the basic scheme list (myscheme_rag_dataset.json), byte for byte, plus one row per record
  - the detailed scheme documents from the MongoDB export (mongo_export/nariconnect/detailed_schemes.json)
  - the Qdrant embeddings and payloads, so the index can be rebuilt without re-embedding

Every table is checked against its source before the file is put in place, and the finished file is read-only.

Usage (from backend/):
  uv run python scripts/backup_data.py build [--compare-atlas]
  uv run python scripts/backup_data.py restore
"""
import argparse
import hashlib
import json
import os
import pickle
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version

from pydantic import ValidationError

# Add the parent directory to sys.path so we can import app
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.append(BACKEND_DIR)

from app.models.scheme_models import Scheme  # noqa: E402

DEFAULT_DB = os.path.join(BACKEND_DIR, "data", "nariconnect_data.sqlite")
DEFAULT_MONGO_EXPORT = os.path.join(
    os.path.dirname(BACKEND_DIR), "mongo_export", "nariconnect", "detailed_schemes.json"
)
DEFAULT_QDRANT = os.path.join(BACKEND_DIR, "qdrant_data")
# The basic list was committed once, in 0cd0f3d, and deleted from the repo in b39355f
BASIC_GIT_SOURCE = "0cd0f3d:backend/myscheme_rag_dataset.json"
BASIC_FILENAME = "myscheme_rag_dataset.json"
DETAILED_RESTORE_FILENAME = "detailed_schemes_from_mongo.json"
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE provenance (
    source TEXT PRIMARY KEY,         -- basic_list | detailed_schemes | embeddings
    origin TEXT NOT NULL,
    sha256 TEXT NOT NULL,            -- of the source bytes
    records INTEGER NOT NULL,
    known_issues TEXT,
    captured_at TEXT NOT NULL
);

-- Exact bytes of source files, so they can be restored byte for byte
CREATE TABLE raw_files (
    filename TEXT PRIMARY KEY,
    git_blob TEXT NOT NULL,          -- what `git hash-object` prints for the content
    sha256 TEXT NOT NULL,
    size INTEGER NOT NULL,
    content BLOB NOT NULL
);

-- One row per record of myscheme_rag_dataset.json, in file order (repeated records included)
CREATE TABLE schemes (
    row_index INTEGER PRIMARY KEY,   -- position in the file, which is also the Qdrant point id
    myscheme_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    scheme_name TEXT,
    short_title TEXT,
    level TEXT,
    scheme_for TEXT,
    ministry TEXT,
    brief_description TEXT,
    categories TEXT,                 -- JSON array
    tags TEXT,                       -- JSON array
    beneficiary_states TEXT,         -- JSON array
    record_json TEXT NOT NULL        -- the full record
);
CREATE INDEX schemes_slug ON schemes (slug);
CREATE VIEW unique_schemes AS
    SELECT * FROM schemes WHERE row_index IN (SELECT MIN(row_index) FROM schemes GROUP BY slug);

-- MongoDB nariconnect.detailed_schemes, in export order
CREATE TABLE scheme_details (
    slug TEXT PRIMARY KEY,
    export_index INTEGER NOT NULL UNIQUE,
    mongo_id TEXT NOT NULL,
    scheme_name TEXT,
    reseedable INTEGER NOT NULL,     -- 1 if seed_atlas.py would store this document unchanged
    issue TEXT,
    doc_json TEXT NOT NULL           -- the document without _id
);

-- Qdrant collection "schemes"
CREATE TABLE embeddings (
    point_id INTEGER PRIMARY KEY REFERENCES schemes (row_index),
    scheme_id TEXT NOT NULL,         -- payload scheme_id (the slug)
    vector BLOB NOT NULL,            -- little-endian float32
    payload_json TEXT NOT NULL
);
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_id(data: bytes) -> str:
    """The object id git gives this content, so a restored file can be checked with `git hash-object`."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def pack_vector(vector: list[float]) -> bytes:
    packed = struct.pack(f"<{len(vector)}f", *vector)
    if list(unpack_vector(packed)) != list(vector):
        raise ValueError("vector is not exactly representable as float32")
    return packed


def unpack_vector(blob: bytes) -> tuple[float, ...]:
    return struct.unpack(f"<{len(blob) // 4}f", blob)


def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def read_basic(basic_file: str | None) -> tuple[bytes, str]:
    if basic_file:
        with open(basic_file, "rb") as f:
            return f.read(), os.path.abspath(basic_file)

    def git(*args) -> bytes:
        return subprocess.run(["git", "-C", BACKEND_DIR, *args], capture_output=True, check=True).stdout

    rev, path = BASIC_GIT_SOURCE.split(":", 1)
    commit = git("rev-parse", rev).decode().strip()
    return git("cat-file", "blob", f"{commit}:{path}"), f"git {commit}:{path}"


def read_qdrant_points(qdrant_dir: str) -> tuple[list, bytes]:
    """Points of the "schemes" collection, sorted by id, plus the raw storage file.

    Qdrant's local mode keeps points as pickled qdrant_client objects in SQLite. They are read from a
    temporary copy, so the live index (and its lock) is never opened.
    """
    with tempfile.TemporaryDirectory() as tmp:
        copy = os.path.join(tmp, "qdrant_data")
        shutil.copytree(qdrant_dir, copy, ignore=shutil.ignore_patterns(".lock"))
        storage = os.path.join(copy, "collection", "schemes", "storage.sqlite")
        with open(storage, "rb") as f:
            storage_bytes = f.read()
        con = sqlite3.connect(f"file:{storage}?mode=ro", uri=True)
        try:
            points = [pickle.loads(blob) for (blob,) in con.execute("SELECT point FROM points")]
        finally:
            con.close()
    return sorted(points, key=lambda p: p.id), storage_bytes


def reseed_issue(doc: dict) -> str | None:
    """Why seed_atlas.py would not store this document unchanged, or None if it would."""
    lost = [k for k, v in doc.items() if isinstance(v, str) and v.startswith("<nested data")]
    if lost:
        return "; ".join(
            f"{k} was replaced by seed_atlas.py with {doc[k]!r}, so its content is lost" for k in lost
        )
    try:
        dumped = Scheme(**doc).model_dump(exclude_none=True)
    except ValidationError as e:
        return f"fails Scheme validation: {e.errors()[0]['loc']}"
    if dumped != doc:
        return "changes when re-validated through Scheme"
    return None


def compare_atlas(detailed: list[dict]) -> str:
    """Confirm the export still matches the live collection."""
    from bson import json_util
    from dotenv import load_dotenv
    from pymongo import MongoClient

    load_dotenv(os.path.join(BACKEND_DIR, ".env"))
    client = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=8000)
    try:
        live = {
            d["slug"]: json.loads(json_util.dumps(d))
            for d in client["nariconnect"]["detailed_schemes"].find({})
        }
    finally:
        client.close()
    exported = {d["slug"]: d for d in detailed}
    if live != exported:
        changed = sorted(s for s in set(live) | set(exported) if live.get(s) != exported.get(s))
        sys.exit(f"The export differs from Atlas for {len(changed)} schemes (e.g. {changed[:5]}); re-export first.")
    return f"identical to Atlas nariconnect.detailed_schemes on {datetime.now(timezone.utc):%Y-%m-%d}"


def describe_basic_issues(basic: list[dict]) -> str:
    seen, repeats, ids_by_slug = set(), 0, {}
    for rec in basic:
        key = to_json(rec)
        repeats += key in seen
        seen.add(key)
        ids_by_slug.setdefault(rec["fields"]["slug"], set()).add(rec["id"])
    multi = sorted(s for s, ids in ids_by_slug.items() if len(ids) > 1)
    return (
        f"{repeats} rows exactly repeat an earlier row; slugs with more than one myScheme id: {multi or 'none'}. "
        "All rows are kept in file order because row_index is the Qdrant point id; "
        "the unique_schemes view keeps the first row per slug."
    )


def describe_detailed_issues(basic: list[dict], detailed: list[dict], issues: dict[str, str]) -> str:
    missing = sorted({r["fields"]["slug"] for r in basic} - {d["slug"] for d in detailed})
    return (
        "A processed copy, not the raw scraper output (myscheme_deep_rag_dataset_v6.json, which no longer exists): "
        "seed_atlas.py validated each record through app.models.scheme_models.Scheme, which dropped fields the "
        "model doesn't define and null values. "
        f"Not reseedable: {issues or 'none'}. "
        f"Schemes in the basic list with no detailed document: {missing or 'none'}."
    )


def scheme_row(index: int, rec: dict) -> tuple:
    f = rec["fields"]
    return (
        index, rec["id"], f["slug"], f.get("schemeName"), f.get("schemeShortTitle"), f.get("level"),
        f.get("schemeFor"), f.get("nodalMinistryName"), f.get("briefDescription"),
        to_json(f.get("schemeCategory", [])), to_json(f.get("tags", [])),
        to_json(f.get("beneficiaryState", [])), to_json(rec),
    )


def detail_row(index: int, doc: dict, issue: str | None) -> tuple:
    basic_details = doc.get("basicDetails")
    name = basic_details.get("schemeName") if isinstance(basic_details, dict) else None
    body = {k: v for k, v in doc.items() if k != "_id"}
    return (doc["slug"], index, doc["_id"]["$oid"], name, int(issue is None), issue, to_json(body))


def build(args):
    db_path = os.path.abspath(args.db)
    if os.path.exists(db_path):
        sys.exit(f"Refusing to overwrite the existing backup {db_path}; move it aside first.")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print("Reading the basic scheme list...")
    basic_bytes, basic_origin = read_basic(args.basic_file)
    basic = json.loads(basic_bytes)

    print(f"Reading the MongoDB export {args.mongo_export}...")
    with open(args.mongo_export, "rb") as f:
        export_bytes = f.read()
    detailed = json.loads(export_bytes)
    detail_issues = {d["slug"]: reseed_issue({k: v for k, v in d.items() if k != "_id"}) for d in detailed}
    detail_issues = {slug: issue for slug, issue in detail_issues.items() if issue}
    atlas_note = compare_atlas(detailed) if args.compare_atlas else "not compared with Atlas"

    print(f"Reading Qdrant points from a copy of {args.qdrant}...")
    points, storage_bytes = read_qdrant_points(args.qdrant)

    # The index must have been built from this list: point i is record i
    if [p.id for p in points] != list(range(len(basic))):
        sys.exit(f"Qdrant point ids don't match the {len(basic)} records of the basic list.")
    for p, rec in zip(points, basic):
        if p.payload.get("slug") != rec["fields"]["slug"]:
            sys.exit(f"Qdrant point {p.id} is {p.payload.get('slug')!r}, but record {p.id} is {rec['fields']['slug']!r}.")
    dims = {len(p.vector) for p in points}
    embedding_notes = f"{'/'.join(map(str, dims))}-dim vectors from nomic-embed-text, stored as float32 (exact)."
    if not any("schemeShortTitle" in p.payload for p in points):
        embedding_notes += " Payloads predate the loader's schemeShortTitle field."

    tmp_path = db_path + ".tmp"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    try:
        print(f"Writing {tmp_path}...")
        con = sqlite3.connect(tmp_path)
        con.execute("PRAGMA journal_mode = DELETE")  # a single file, no -wal/-shm companions
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        con.executescript(SCHEMA)
        with con:
            con.executemany(
                "INSERT INTO provenance VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("basic_list", basic_origin, sha256(basic_bytes), len(basic),
                     describe_basic_issues(basic), captured_at),
                    ("detailed_schemes",
                     f"{os.path.relpath(args.mongo_export, os.path.dirname(BACKEND_DIR))} "
                     f"(dump of MongoDB nariconnect.detailed_schemes); {atlas_note}",
                     sha256(export_bytes), len(detailed),
                     describe_detailed_issues(basic, detailed, detail_issues), captured_at),
                    ("embeddings",
                     f"{os.path.relpath(args.qdrant, BACKEND_DIR)}/collection/schemes/storage.sqlite "
                     f"(qdrant_client {version('qdrant-client')})",
                     sha256(storage_bytes), len(points), embedding_notes, captured_at),
                ],
            )
            con.execute(
                "INSERT INTO raw_files VALUES (?, ?, ?, ?, ?)",
                (BASIC_FILENAME, git_blob_id(basic_bytes), sha256(basic_bytes), len(basic_bytes), basic_bytes),
            )
            con.executemany(
                "INSERT INTO schemes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [scheme_row(i, rec) for i, rec in enumerate(basic)],
            )
            con.executemany(
                "INSERT INTO scheme_details VALUES (?, ?, ?, ?, ?, ?, ?)",
                [detail_row(i, d, detail_issues.get(d["slug"])) for i, d in enumerate(detailed)],
            )
            con.executemany(
                "INSERT INTO embeddings VALUES (?, ?, ?, ?)",
                [(p.id, p.payload["scheme_id"], pack_vector(p.vector), to_json(p.payload)) for p in points],
            )
        con.close()

        print("Verifying the backup against the sources...")
        verify(tmp_path, basic_bytes, basic, detailed, points)

        os.link(tmp_path, db_path)  # unlike a rename, never replaces a file that appeared meanwhile
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    os.chmod(db_path, 0o444)
    with open(db_path, "rb") as f:
        digest = sha256(f.read())
    checksum_path = db_path + ".sha256"
    with open(checksum_path, "w") as f:
        f.write(f"{digest}  {os.path.basename(db_path)}\n")  # `shasum -a 256 -c` format
    os.chmod(checksum_path, 0o444)

    print(f"\n✅ Backup written to {db_path} (read-only, {os.path.getsize(db_path) / 1e6:.1f} MB)")
    print(f"   sha256 {digest}  (also in {os.path.basename(checksum_path)})")
    print(f"   {len(basic)} basic records, {len(detailed)} detailed documents, {len(points)} embeddings")
    if detail_issues:
        print(f"   Not reseedable: {', '.join(detail_issues)} (see scheme_details.issue)")


def verify(db_path: str, basic_bytes: bytes, basic: list[dict], detailed: list[dict], points: list):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        def check(ok: bool, what: str):
            if not ok:
                raise RuntimeError(f"Backup verification failed: {what}")

        check(con.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "integrity_check")
        check(not con.execute("PRAGMA foreign_key_check").fetchall(), "foreign_key_check")

        blob, git_blob, digest = con.execute(
            "SELECT content, git_blob, sha256 FROM raw_files WHERE filename = ?", (BASIC_FILENAME,)
        ).fetchone()
        check(blob == basic_bytes and git_blob == git_blob_id(blob) and digest == sha256(blob), "raw basic file")

        rows = con.execute("SELECT record_json FROM schemes ORDER BY row_index").fetchall()
        check([json.loads(r) for (r,) in rows] == basic, "schemes rows")

        rows = con.execute("SELECT mongo_id, doc_json FROM scheme_details ORDER BY export_index").fetchall()
        check([{"_id": {"$oid": oid}, **json.loads(doc)} for oid, doc in rows] == detailed, "scheme_details rows")

        rows = con.execute("SELECT point_id, vector, payload_json FROM embeddings ORDER BY point_id").fetchall()
        check(len(rows) == len(points), "embeddings count")
        for (point_id, vector, payload), p in zip(rows, points):
            check(
                point_id == p.id and list(unpack_vector(vector)) == list(p.vector) and json.loads(payload) == p.payload,
                f"embedding {p.id}",
            )
    finally:
        con.close()


def write_new_file(path: str, data: bytes):
    """Write data to path, leaving an existing file alone (and refusing if it differs)."""
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read() == data:
                print(f"{path} is already up to date.")
                return
        sys.exit(f"{path} exists and differs from the backup; move it aside first.")
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(data)
    os.replace(tmp_path, path)
    print(f"Wrote {path} ({len(data) / 1e6:.1f} MB)")


def restore(args):
    con = sqlite3.connect(f"file:{os.path.abspath(args.db)}?mode=ro", uri=True)
    try:
        content, git_blob = con.execute(
            "SELECT content, git_blob FROM raw_files WHERE filename = ?", (BASIC_FILENAME,)
        ).fetchone()
        if git_blob_id(content) != git_blob:
            sys.exit("The stored basic list doesn't match its recorded git blob id; the backup is damaged.")
        rows = con.execute("SELECT mongo_id, doc_json FROM scheme_details ORDER BY export_index").fetchall()
    finally:
        con.close()

    write_new_file(os.path.join(args.out_dir, BASIC_FILENAME), content)
    # The documents as exported from MongoDB (with `_id`), loadable with `seed_atlas.py -f`
    docs =[{"_id": {"$oid": oid}, **json.loads(doc)} for oid, doc in rows]
    write_new_file(
        os.path.join(args.out_dir, DETAILED_RESTORE_FILENAME),
        json.dumps(docs, ensure_ascii=False, indent=2).encode("utf-8"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Back up the scheme data to SQLite, or restore it")
    commands = parser.add_subparsers(dest="command", required=True)

    build_cmd = commands.add_parser("build", help="Create the backup (never overwrites an existing one)")
    build_cmd.add_argument("--db", default=DEFAULT_DB, help="Backup file to create")
    build_cmd.add_argument(
        "--basic-file", help=f"Basic scheme list to back up (default: {BASIC_GIT_SOURCE} from git)"
    )
    build_cmd.add_argument("--mongo-export", default=DEFAULT_MONGO_EXPORT, help="MongoDB export of detailed_schemes")
    build_cmd.add_argument("--qdrant", default=DEFAULT_QDRANT, help="Qdrant data directory")
    build_cmd.add_argument(
        "--compare-atlas", action="store_true", help="Check the export against Atlas (MONGO_URI) first"
    )

    restore_cmd = commands.add_parser("restore", help="Write the dataset files from the backup")
    restore_cmd.add_argument("--db", default=DEFAULT_DB, help="Backup file to read")
    restore_cmd.add_argument("--out-dir", default=BACKEND_DIR, help="Directory to write the files to")

    args = parser.parse_args()
    if args.command == "build":
        build(args)
    else:
        restore(args)
