import asyncio
import logging
import re
from pymongo.errors import PyMongoError
from fastapi import APIRouter, Depends, HTTPException
from app.auth.clerk import get_current_user
from app.models.schemas import UserInput, ChatResponse, ExtractedInfo, SchemeResult
from app.services.ollama_service import (
    LLM_UNAVAILABLE_ERRORS,
    extract_user_info,
    chat_with_context,
)
from app.services.vector_service import search_schemes
from app.db.mongo import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

INT_PROFILE_FIELDS = {"age", "income"}
HISTORY_ROLES = {"user", "assistant"}


def clean_profile(raw: dict | None) -> dict:
    """Keep only known profile fields with meaningful values, coerced to the right types.

    The LLM extraction schema can't express null for integers, so 0 / "" mean "unknown".
    """
    cleaned = {}
    for field in ExtractedInfo.model_fields:
        value = (raw or {}).get(field)
        if value is None or value == "" or value == 0:
            continue
        if field in INT_PROFILE_FIELDS:
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue
        else:
            value = str(value).strip()
            if not value or value.lower() in ("null", "none", "unknown"):
                continue
        cleaned[field] = value
    return cleaned


def select_recommended(schemes: list[dict], recommended: list[str] | bool) -> list[dict]:
    """Keep only the retrieved schemes the model actually recommended (matched by ID, or by name as a fallback)."""
    if recommended is True:
        return schemes
    if not recommended:
        return []
    wanted = {r.strip().lower() for r in recommended}
    return [
        s
        for s in schemes
        if s["id"].lower() in wanted
        or s["metadata"].get("schemeName", "").strip().lower() in wanted
    ]


def hide_scheme_ids(text: str, schemes: list[dict]) -> str:
    """Scheme IDs are for the recommendation list only; swap any that leak into the reply for scheme names."""
    text = re.sub(r"\s*\((?:scheme\s+)?ID:?\s*[\w-]+\)", "", text, flags=re.IGNORECASE)
    for s in schemes:
        name = s["metadata"].get("schemeName", "").strip()
        if name:
            text = re.sub(rf"(?<![\w/-]){re.escape(s['id'])}(?![\w/-])", name, text)
    return text


async def fetch_deep_details(scheme_ids: list[str]) -> dict:
    """Fetch full scheme details from MongoDB for given scheme slugs."""
    if not scheme_ids:
        return {}

    db = await get_database()
    deep_details = {}

    # Deep details only enrich the answer; keep chatting on vector-search results if MongoDB is down
    try:
        cursor = db.detailed_schemes.find({"slug": {"$in": scheme_ids}})
        async for doc in cursor:
            # Remove MongoDB's internal _id field for JSON serialization
            doc.pop("_id", None)
            deep_details[doc["slug"]] = doc
    except PyMongoError as e:
        logger.warning("MongoDB unavailable, skipping deep scheme details: %s", e)

    return deep_details


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: UserInput,
    user_id: str = Depends(get_current_user),
):
    # Ollama and embedded Qdrant clients are synchronous; run them off the event loop.
    try:
        extracted_profile = await asyncio.to_thread(extract_user_info, data.message)
    except LLM_UNAVAILABLE_ERRORS as e:
        # Extraction only refines the profile; carry on with what the client sent
        logger.warning("Profile extraction failed: %s", e)
        extracted_profile = {}

    # Start from the profile the client already knows, and let anything newly stated in this message override it
    final_user_profile = ExtractedInfo(
        **{**clean_profile(data.user_profile), **clean_profile(extracted_profile)}
    ).model_dump()

    # Only replay user/assistant turns; a client must not be able to inject system prompts
    chat_history = [
        {"role": m["role"], "content": m["content"]}
        for m in data.chat_history
        if m.get("role") in HISTORY_ROLES and isinstance(m.get("content"), str)
    ]

    # Follow-ups ("which of those...") carry little topic on their own, so search with recent user turns too
    recent_user_turns = [m["content"] for m in chat_history if m["role"] == "user"][-2:]
    search_query = f"""
    Age: {final_user_profile.get("age")}
    Gender: {final_user_profile.get("gender")}
    Occupation: {final_user_profile.get("occupation")}
    State: {final_user_profile.get("state")}
    Income: {final_user_profile.get("income")}
    Earlier messages: {" | ".join(recent_user_turns)}
    Query: {data.message}
    """

    # Restrict to schemes available in the user's state (or nationwide) when we know it
    try:
        schemes = await asyncio.to_thread(
            search_schemes, search_query, 5, final_user_profile.get("state")
        )
    except LLM_UNAVAILABLE_ERRORS as e:
        logger.error("Embedding/search failed: %s", e)
        raise HTTPException(status_code=502, detail="Scheme search is temporarily unavailable")

    # Fetch deep details from MongoDB for the returned schemes
    scheme_ids = [s["id"] for s in schemes]
    deep_details = await fetch_deep_details(scheme_ids)

    # Add deep details to each scheme result
    for scheme in schemes:
        slug = scheme["id"]
        if slug in deep_details:
            scheme["deep_details"] = deep_details[slug]

    context = "\n\n".join(f"ID: {s['id']}\n{s['text']}" for s in schemes)

    try:
        response_text, recommended = await asyncio.to_thread(
            chat_with_context,
            data.message,
            context,
            final_user_profile,
            chat_history,
        )
    except LLM_UNAVAILABLE_ERRORS as e:
        logger.error("Chat model failed: %s", e)
        raise HTTPException(status_code=502, detail="The assistant is temporarily unavailable")

    return ChatResponse(
        status="success",
        user_profile=ExtractedInfo(**final_user_profile),
        schemes=[SchemeResult(**s) for s in select_recommended(schemes, recommended)],
        response=hide_scheme_ids(response_text, schemes),
    )
