import asyncio
from fastapi import APIRouter, Depends
from app.auth.clerk import get_current_user
from app.models.schemas import UserInput, ChatResponse, ExtractedInfo, SchemeResult
from app.services.ollama_service import extract_user_info, chat_with_context
from app.services.vector_service import search_schemes
from app.db.mongo import get_database

router = APIRouter()

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


async def fetch_deep_details(scheme_ids: list[str]) -> dict:
    """Fetch full scheme details from MongoDB for given scheme slugs."""
    if not scheme_ids:
        return {}

    db = await get_database()
    deep_details = {}

    cursor = db.detailed_schemes.find({"slug": {"$in": scheme_ids}})
    async for doc in cursor:
        # Remove MongoDB's internal _id field for JSON serialization
        doc.pop("_id", None)
        deep_details[doc["slug"]] = doc

    return deep_details


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: UserInput,
    user_id: str = Depends(get_current_user),
):
    # Ollama and embedded Qdrant clients are synchronous; run them off the event loop.
    extracted_profile = await asyncio.to_thread(extract_user_info, data.message)

    # Start from the profile the client already knows, and let anything newly stated in this message override it
    final_user_profile = ExtractedInfo(
        **{**clean_profile(data.user_profile), **clean_profile(extracted_profile)}
    ).model_dump()

    search_query = f"""
    Age: {final_user_profile.get("age")}
    Gender: {final_user_profile.get("gender")}
    Occupation: {final_user_profile.get("occupation")}
    State: {final_user_profile.get("state")}
    Income: {final_user_profile.get("income")}
    Query: {data.message}
    """

    schemes = await asyncio.to_thread(search_schemes, search_query, 5)

    # Fetch deep details from MongoDB for the returned schemes
    scheme_ids = [s["id"] for s in schemes]
    deep_details = await fetch_deep_details(scheme_ids)

    # Add deep details to each scheme result
    for scheme in schemes:
        slug = scheme["id"]
        if slug in deep_details:
            scheme["deep_details"] = deep_details[slug]

    context = "\n\n".join([s["text"] for s in schemes])

    # Only replay user/assistant turns; a client must not be able to inject system prompts
    chat_history = [
        {"role": m["role"], "content": m["content"]}
        for m in data.chat_history
        if m.get("role") in HISTORY_ROLES and isinstance(m.get("content"), str)
    ]

    response_text, should_show_schemes = await asyncio.to_thread(
        chat_with_context,
        data.message,
        context,
        final_user_profile,
        chat_history,
    )

    return ChatResponse(
        status="success",
        user_profile=ExtractedInfo(**final_user_profile),
        schemes=[SchemeResult(**s) for s in schemes] if should_show_schemes else [],
        response=response_text,
    )
