from fastapi import APIRouter, Depends, Query
from app.auth.clerk import get_current_user
from app.models.schemas import VectorizeResponse
from app.services.vector_service import vectorize_schemes

router = APIRouter(dependencies=[Depends(get_current_user)])


# Sync handler: FastAPI runs it in a worker thread, so the long embedding job
# doesn't block the event loop.
@router.post("/admin/vectorize", response_model=VectorizeResponse)
def vectorize(force: bool = Query(False, description="Force re-vectorization")):
    result = vectorize_schemes(force=force)
    return VectorizeResponse(**result)
