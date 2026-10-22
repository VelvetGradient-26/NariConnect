from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pymongo.errors import PyMongoError
from app.routers import chat, admin, schemes
from app.db.mongo import close_database
from app.config import OLLAMA_HOST, OLLAMA_EMBED_HOST
from app.services.ollama_service import client as ollama_client, embed_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Server starting... Ollama host: {OLLAMA_HOST}, embeddings: {OLLAMA_EMBED_HOST}")
    for name, ollama in (("chat", ollama_client), ("embeddings", embed_client)):
        try:
            ollama.list()
            print(f"Connected to Ollama ({name}) successfully!")
        except Exception as e:
            print(f"Warning: Could not connect to Ollama ({name}): {e}")
    yield
    await close_database()
    print("Server shutting down...")


app = FastAPI(
    title="SheLeads Backend API",
    description="Backend for SheLeads PPT with Clerk Auth and Ollama RAG",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Allow frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PyMongoError)
async def mongo_unavailable(request: Request, exc: PyMongoError):
    return JSONResponse(status_code=503, content={"detail": "Scheme database is unavailable"})


app.include_router(chat.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(schemes.router, prefix="/api")


@app.get("/")
async def root():
    return {"status": "running", "message": "SheLeads Backend API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
