import os
import json
import sys
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

# Add the parent directory to sys.path so we can import app
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from app.models.scheme_models import Scheme

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("Warning: MONGO_URI is missing from your .env file! Using localhost for now.")
    MONGO_URI = "mongodb://localhost:27017"

# Connect to MongoDB Atlas
print("Connecting to MongoDB Atlas...")
try:
    client = MongoClient(MONGO_URI)
    # Ping to check connection
    client.admin.command("ping")
    print("Connected successfully!")
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)

db = client["nariconnect"]
collection = db["detailed_schemes"]


def get_depth(obj, depth=0):
    """Calculate nesting depth of a dict/list structure."""
    if isinstance(obj, dict):
        return max((get_depth(v, depth + 1) for v in obj.values()), default=depth)
    elif isinstance(obj, list):
        return max((get_depth(item, depth + 1) for item in obj), default=depth)
    return depth


def simplify_nested_fields(item, max_depth=40):
    """Recursively simplify deeply nested structures."""
    if get_depth(item) <= max_depth:
        return item

    if isinstance(item, dict):
        result = {}
        for k, v in item.items():
            if get_depth(v) > max_depth:
                # Convert to simplified string representation
                result[k] = f"<nested data: depth {get_depth(v)}>"
            else:
                result[k] = simplify_nested_fields(v, max_depth)
        return result
    elif isinstance(item, list):
        return [simplify_nested_fields(x, max_depth) for x in item]
    return item


def seed_database(json_filepath: str, clear_collection: bool = True):
    if not os.path.exists(json_filepath):
        print(f"Error: File not found at {json_filepath}")
        return

    print(f"Loading {json_filepath} into MongoDB Atlas...")
    with open(json_filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    valid_schemes = []
    skipped = 0
    for i, item in enumerate(data):
        try:
            # Validate against our Pydantic schema
            scheme = Scheme(**item)
            # Convert back to dict for MongoDB insertion
            scheme_dict = scheme.model_dump(exclude_none=True)
            # Simplify deeply nested structures to avoid BSON depth errors
            scheme_dict = simplify_nested_fields(scheme_dict)
            valid_schemes.append(scheme_dict)
        except Exception as e:
            skipped += 1
            # Only print first few errors to avoid spamming the console
            if skipped <= 5:
                print(
                    f"Skipping invalid scheme ({item.get('slug', 'unknown')}): {str(e)[:80]}"
                )

    if valid_schemes:
        if clear_collection:
            print("Clearing old records...")
            collection.delete_many({})
        else:
            print(f"Adding {len(valid_schemes)} new records without clearing...")

        print(f"Inserting {len(valid_schemes)} new records (this may take a minute)...")

        # Use bulk upsert to handle duplicates
        operations = []
        for scheme in valid_schemes:
            operations.append(
                UpdateOne({"slug": scheme.get("slug")}, {"$set": scheme}, upsert=True)
            )

        # Execute in batches
        batch_size = 1000
        for i in range(0, len(operations), batch_size):
            batch = operations[i : i + batch_size]
            collection.bulk_write(batch, ordered=False)
            print(f"Inserted/Updated {i + len(batch)}/{len(valid_schemes)}")

        # Create an index on the slug for O(1) lightning-fast lookups
        collection.create_index("slug", unique=True)
        print(
            f"✅ Successfully processed {len(valid_schemes)} schemes in MongoDB Atlas!"
        )
    else:
        print("No valid schemes found to insert.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed MongoDB with scheme data")
    parser.add_argument(
        "--file",
        "-f",
        default="myscheme_deep_rag_dataset_v6.json",
        help="JSON file to load (default: myscheme_deep_rag_dataset_v6.json)",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear existing collection before inserting",
    )
    args = parser.parse_args()

    # Look in the parent directory (backend folder)
    json_path = os.path.join(os.path.dirname(SCRIPT_DIR), args.file)

    print(f"Looking for dataset at: {json_path}")
    seed_database(json_path, clear_collection=not args.no_clear)
