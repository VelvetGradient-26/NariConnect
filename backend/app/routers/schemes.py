import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.clerk import get_current_user
from app.db.mongo import get_database

router = APIRouter(dependencies=[Depends(get_current_user)])


def _contains(text: str) -> dict:
    """Case-insensitive substring match; user input is escaped so it is never treated as a regex."""
    return {"$regex": re.escape(text), "$options": "i"}


@router.get("/schemes")
async def get_schemes(
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=50),
        search: Optional[str] = None,
        sector: Optional[str] = None,
        state: Optional[str] = None,
        level: Optional[str] = None
):
    query = {}

    if search:
        query["$or"] = [
            {"basicDetails.schemeName": _contains(search)},
            {"schemeContent.briefDescription": _contains(search)}
        ]

    if sector:
        # Assuming sector maps to schemeCategory
        query["basicDetails.schemeCategory.label"] = _contains(sector)

    if state:
        query["basicDetails.state"] = _contains(state)

    if level:
        query["basicDetails.level.label"] = _contains(level)

    db = await get_database()
    schemes_collection = db.detailed_schemes

    total_count = await schemes_collection.count_documents(query)
    skip = (page - 1) * limit

    cursor = schemes_collection.find(query).skip(skip).limit(limit)
    schemes = await cursor.to_list(length=limit)

    for scheme in schemes:
        if "_id" in scheme:
            scheme["_id"] = str(scheme["_id"])

    return {
        "data": schemes,
        "page": page,
        "limit": limit,
        "total": total_count,
        "total_pages": (total_count + limit - 1) // limit
    }


@router.get("/schemes/{slug}")
async def get_scheme_details(slug: str):
    db = await get_database()
    scheme = await db.detailed_schemes.find_one({"slug": slug})
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    if "_id" in scheme:
        scheme["_id"] = str(scheme["_id"])

    return scheme
