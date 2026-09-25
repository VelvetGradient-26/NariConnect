from dotenv import load_dotenv
from os import getenv

load_dotenv()

MONGO_URI = getenv("MONGO_URI", "mongodb://localhost:27017")
CLERK_SECRET_KEY = getenv("CLERK_SECRET_KEY", "")
# Accept the "dev_test_123" bearer token without Clerk. Never enable in production.
AUTH_DEV_BYPASS = getenv("AUTH_DEV_BYPASS", "false").lower() in ("1", "true", "yes")
OLLAMA_HOST = getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = getenv("OLLAMA_MODEL", "llama3:8b")
OLLAMA_EMBED_MODEL = getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
QDRANT_PATH = getenv("QDRANT_PATH", "./qdrant_data")
SARVAM_API_KEY = getenv("SARVAM_API_KEY", "")
