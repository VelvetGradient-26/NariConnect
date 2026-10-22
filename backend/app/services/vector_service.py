import json
import os
import threading
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchText,
    MatchValue,
)
from app.config import QDRANT_PATH
from app.services.ollama_service import get_embedding

# backend/ — where data_scraper.py and scripts/seed_atlas.py also keep the datasets
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.makedirs(QDRANT_PATH, exist_ok=True)
client = QdrantClient(path=QDRANT_PATH)
COLLECTION_NAME = "schemes"

# Callers run in worker threads; serialize access so a concurrent (re)vectorization
# can't race with another one or delete the collection mid-search.
_lock = threading.RLock()
# lowercase state name -> canonical spelling used in the "states" payload; rebuilt after vectorization
_known_states: dict[str, str] | None = None


def load_schemes_from_json(filepath: str) -> list[dict]:
    if not os.path.isabs(filepath):
        filepath = os.path.join(BASE_DIR, filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    schemes = []
    for item in data:
        fields = item.get("fields", {})
        scheme_id = item.get("id", "")

        text = f"""
Scheme: {fields.get("schemeName", "")}
Category: {", ".join(fields.get("schemeCategory", []))}
For: {fields.get("schemeFor", "")}
Level: {fields.get("level", "")}
Ministry: {fields.get("nodalMinistryName", "")}
Description: {fields.get("briefDescription", "")}
Tags: {", ".join(fields.get("tags", []))}
States: {", ".join(fields.get("beneficiaryState", []))}
"""

        metadata = {
            "schemeName": fields.get("schemeName", ""),
            "schemeFor": fields.get("schemeFor", ""),
            "level": fields.get("level", ""),
            "ministry": fields.get("nodalMinistryName", ""),
            "description": fields.get("briefDescription", ""),
            "categories": ", ".join(fields.get("schemeCategory", [])),
            "tags": ", ".join(fields.get("tags", [])),
            "states": ", ".join(fields.get("beneficiaryState", [])),
            "slug": fields.get("slug", ""),
            "schemeShortTitle": fields.get("schemeShortTitle", ""),
        }

        schemes.append({"id": scheme_id, "text": text.strip(), "metadata": metadata})

    return schemes


def initialize_collection():
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if COLLECTION_NAME not in collection_names:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )
        print(f"Created collection: {COLLECTION_NAME}")

    return COLLECTION_NAME


def vectorize_schemes(filepath: str = "myscheme_rag_dataset.json", force: bool = False):
    with _lock:
        initialize_collection()

        existing = client.count(collection_name=COLLECTION_NAME).count
        if existing > 0 and not force:
            print(f"Collection already has {existing} schemes. Skipping vectorization.")
            return {"status": "already_exists", "count": existing}

        if force:
            client.delete_collection(collection_name=COLLECTION_NAME)
            initialize_collection()
            print("Re-vectorizing all schemes...")

        print("Loading schemes from JSON...")
        schemes = load_schemes_from_json(filepath)
        print(f"Loaded {len(schemes)} schemes. Generating embeddings...")

        points = []
        for i, scheme in enumerate(schemes):
            if i % 100 == 0:
                print(f"Processing scheme {i}/{len(schemes)}...")

            embedding = get_embedding(scheme["text"])

            # Use slug as the ID if available in metadata, otherwise use the provided ID
            slug = scheme["metadata"].get("slug") or scheme["id"]

            points.append(
                PointStruct(
                    id=i,
                    vector=embedding,
                    payload={
                        "scheme_id": slug,
                        "text": scheme["text"],
                        **scheme["metadata"],
                    },
                )
            )

        batch_size = 256
        for start in range(0, len(points), batch_size):
            client.upsert(
                collection_name=COLLECTION_NAME, points=points[start : start + batch_size]
            )

        global _known_states
        _known_states = None
        print(f"Successfully vectorized {len(schemes)} schemes.")
        return {"status": "success", "count": len(schemes)}


def _canonical_state(state: str | None) -> str | None:
    """Map a user-supplied state onto the exact spelling stored in scheme payloads (case-insensitive)."""
    global _known_states
    if not state:
        return None
    if _known_states is None:
        _known_states = {}
        offset = None
        while True:
            points, offset = client.scroll(
                COLLECTION_NAME, limit=1000, offset=offset, with_payload=["states"]
            )
            for point in points:
                for name in point.payload.get("states", "").split(","):
                    name = name.strip()
                    if name and name != "All":
                        _known_states[name.lower()] = name
            if offset is None:
                break
    return _known_states.get(state.strip().lower())


def _state_filter(state: str) -> Filter:
    """Schemes open to every state, or listing this state among their beneficiary states."""
    return Filter(
        should=[
            FieldCondition(key="states", match=MatchValue(value="All")),
            FieldCondition(key="states", match=MatchText(text=state)),
        ]
    )


def search_schemes(query: str, n_results: int = 5, state: str | None = None) -> list[dict]:
    with _lock:
        initialize_collection()

        count = client.count(collection_name=COLLECTION_NAME).count
        if count == 0:
            # Auto-vectorize if empty
            print("Database empty. Auto-triggering vectorization...")
            vectorize_schemes()
            count = client.count(collection_name=COLLECTION_NAME).count
            if count == 0:
                raise ValueError("Failed to vectorize schemes.")

        query_embedding = get_embedding(query)

        canonical_state = _canonical_state(state)
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            query_filter=_state_filter(canonical_state) if canonical_state else None,
            limit=n_results,
        )

        if hasattr(results, "result"):
            points = results.result
        elif hasattr(results, "points"):
            points = results.points
        else:
            points = list(results)

        schemes = []
        for point in points:
            if hasattr(point, "payload"):
                payload = point.payload
            else:
                payload = point[1] if isinstance(point, tuple) else {}

            schemes.append(
                {
                    "id": payload.get(
                        "scheme_id", str(point.id) if hasattr(point, "id") else ""
                    ),
                    "text": payload.get("text", ""),
                    "metadata": {
                        "schemeName": payload.get("schemeName", ""),
                        "schemeFor": payload.get("schemeFor", ""),
                        "level": payload.get("level", ""),
                        "ministry": payload.get("ministry", ""),
                        "description": payload.get("description", ""),
                        "categories": payload.get("categories", ""),
                        "tags": payload.get("tags", ""),
                        "states": payload.get("states", ""),
                        "schemeShortTitle": payload.get("schemeShortTitle", ""),
                    },
                }
            )

        return schemes
