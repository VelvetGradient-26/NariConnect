import base64
from dotenv import load_dotenv
from os import getenv

load_dotenv()


def _clerk_issuer_from_publishable_key(key: str) -> str:
    """pk_test_/pk_live_ keys are base64 of the instance's Frontend API domain plus a trailing '$'."""
    try:
        encoded = key.split("_", 2)[2]
        domain = base64.b64decode(encoded + "=" * (-len(encoded) % 4)).decode().rstrip("$")
    except (IndexError, ValueError):
        return ""
    return f"https://{domain}" if domain else ""


MONGO_URI = getenv("MONGO_URI", "mongodb://localhost:27017")

CLERK_PUBLISHABLE_KEY = getenv("CLERK_PUBLISHABLE_KEY", "")
# Tokens must be issued by this Clerk instance; its public signing keys are served at <issuer>/.well-known/jwks.json
CLERK_ISSUER = getenv("CLERK_ISSUER") or _clerk_issuer_from_publishable_key(CLERK_PUBLISHABLE_KEY)
# Origins allowed in the token's `azp` claim (the frontend URLs)
CLERK_AUTHORIZED_PARTIES = [
    p.strip() for p in getenv("CLERK_AUTHORIZED_PARTIES", "http://localhost:5173").split(",") if p.strip()
]
# Accept the "dev_test_123" bearer token without Clerk. Never enable in production.
AUTH_DEV_BYPASS = getenv("AUTH_DEV_BYPASS", "false").lower() in ("1", "true", "yes")

# Chat model host: a local/remote Ollama server, or Ollama Cloud (https://ollama.com + OLLAMA_API_KEY)
OLLAMA_HOST = getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_API_KEY = getenv("OLLAMA_API_KEY", "")
OLLAMA_MODEL = getenv("OLLAMA_MODEL", "llama3:8b")
# Embeddings must come from the same model that built the Qdrant index (nomic-embed-text, 768-dim).
# Ollama Cloud doesn't serve embedding models, so point this at a local Ollama when chat uses the cloud.
OLLAMA_EMBED_HOST = getenv("OLLAMA_EMBED_HOST", OLLAMA_HOST)
OLLAMA_EMBED_MODEL = getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
QDRANT_PATH = getenv("QDRANT_PATH", "./qdrant_data")
SARVAM_API_KEY = getenv("SARVAM_API_KEY", "")
