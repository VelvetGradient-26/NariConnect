from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGO_URI

_client = None
_db = None


async def get_database():
    global _client, _db
    if _client is None:
        # Fail fast when MongoDB is unreachable instead of the 30s driver default
        _client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        _db = _client["nariconnect"]
    return _db


async def close_database():
    global _client
    if _client:
        _client.close()
        _client = None
