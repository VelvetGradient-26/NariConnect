# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

NariConnect (SheLeads 2.0 hackathon project) matches Indian women to government financial schemes. It has a React + Vite frontend (`frontend/`) and a FastAPI RAG backend (`backend/`) using Ollama (LLM + embeddings), a local embedded Qdrant store, and MongoDB. There is no test suite.

## Commands

Frontend (run from `frontend/`):
```bash
npm install
npm run dev       # http://localhost:5173
npm run build
npm run lint      # eslint
```

Backend (run from `backend/`; `pyproject.toml` + `uv.lock` is the source of truth, and `backend/requirements.txt` mirrors it for pip users, so keep both in sync when adding deps):
```bash
uv sync
uv run uvicorn main:app --reload             # http://localhost:8000, Swagger at /docs
uv run python scripts/seed_atlas.py [-f FILE] [--no-clear]   # load detailed scheme JSON into MongoDB
curl -X POST -H "Authorization: Bearer dev_test_123" "localhost:8000/api/admin/vectorize?force=true"  # rebuild the Qdrant index (needs AUTH_DEV_BYPASS=true, or a real Clerk session token)
ollama serve   # needs the models named in OLLAMA_MODEL and OLLAMA_EMBED_MODEL pulled
```

Run backend commands from `backend/`: imports are `app.*`, and relative paths such as `./qdrant_data` and the dataset JSON files resolve from there.

## Environment

- `frontend/.env`: `VITE_CLERK_PUBLISHABLE_KEY` (the app throws on startup without it), `VITE_API_URL` (the base URL *including* `/api`, e.g. `http://localhost:8000/api`).
- `backend/.env` (read in `app/config.py`): `MONGO_URI`, `OLLAMA_HOST`, `OLLAMA_MODEL` (default `llama3:8b`), `OLLAMA_EMBED_MODEL` (default `nomic-embed-text`), `QDRANT_PATH` (default `./qdrant_data`), `CLERK_SECRET_KEY` (required for auth: used to fetch Clerk's JWKS), `AUTH_DEV_BYPASS` (default off; when true, the bearer token `dev_test_123` authenticates as `dev_user_123` for curl/Swagger testing), `SARVAM_API_KEY` (not used yet). `data_scraper.py` reads `MYSCHEME_API_KEY`. Ollama is often run on another machine; point `OLLAMA_HOST` at it.
- The dataset files `backend/myscheme_rag_dataset.json` (the basic list, used for vectorization) and `backend/myscheme_deep_rag_dataset_v6.json` (the detailed data, used for Mongo) are gitignored (`*.json`), so they must be obtained separately. `data_scraper.py` builds the detailed file from the basic one using the myscheme.gov.in API.

## Architecture

### Chat RAG pipeline (`app/routers/chat.py`, `POST /api/chat`)
1. `ollama_service.extract_user_info` uses Ollama structured output (`format=` a JSON schema) to extract `{age, gender, occupation, state, income}` from the message. If the request's `user_profile` has any non-empty values, it is used instead.
2. The profile and the message are combined into a text query. `vector_service.search_schemes` embeds it and returns the top 5 hits from Qdrant.
3. The hit IDs are scheme **slugs**. They are used to fetch the full documents from MongoDB `nariconnect.detailed_schemes`, which are attached as `deep_details`.
4. `ollama_service.chat_with_context` sends the "Nari" persona system prompt, the prior `chat_history`, and the retrieved context. The LLM must end its reply with `{"recommended_schemes": true|false}`. That block is removed from the reply with a regex, and the flag decides whether the response includes `schemes`. If you change the prompt, keep this contract.

### Two data stores, joined by slug
- **Qdrant** (embedded, on-disk at `QDRANT_PATH`, collection `schemes`, 768-dim cosine, sized for `nomic-embed-text`). It is built from `myscheme_rag_dataset.json` by `vectorize_schemes()`. Point IDs are sequential ints, and the slug is stored in the payload as `scheme_id`. `search_schemes` automatically vectorizes when the collection is empty, so the first chat request can take a long time. Changing the embed model means changing the vector size and re-vectorizing with `force=true`. The embedded Qdrant takes a file lock (`qdrant_data/.lock`), so only one process can open it at a time.
- **MongoDB** `detailed_schemes`: documents are validated by `app/models/scheme_models.Scheme` and upserted by slug by `scripts/seed_atlas.py`. The script also creates a unique `slug` index and flattens overly deep nesting to avoid BSON depth errors.

### Backend conventions
- Auth: every `/api/*` route depends on `get_current_user` (`app/auth/clerk.py`), either per route or via `APIRouter(dependencies=[...])`. It verifies the Clerk session JWT (RS256) against keys from `https://api.clerk.com/v1/jwks`, and requires `exp` and `sub`. `/api/admin/vectorize` accepts any signed-in user; there is no admin role yet.
- MongoDB access goes through the async `motor` client from `app/db/mongo.get_database()`. The Ollama and embedded Qdrant clients are synchronous: call them via `asyncio.to_thread` inside `async def` routes, or make the route a plain `def`, so they don't block the event loop.
- `/api/chat` merges profiles: the client's `user_profile` is the base and values newly extracted from the message override it (`clean_profile` drops empty values and 0s). Only `user`/`assistant` turns from `chat_history` are forwarded to the LLM.
- Regex filters in `/api/schemes` escape user input with `re.escape`.
- CORS allows only `http://localhost:5173` (`main.py`).
- `backend/utils.py` and `backend/rag_engine.pymodels.py` are empty leftovers. `backend/plan.md` is early hackathon notes and does not describe the current code.

### Frontend
- `App.jsx` holds all routing. Clerk's `ClerkProvider` is inside `BrowserRouter`, and each protected route is wrapped in `<SignedIn>`/`<SignedOut><RedirectToSignIn/>`. Sign-up redirects to `/onboarding`.
- All backend calls go through `src/services/api.js`, which receives a token from Clerk's `useAuth().getToken()` in the calling component.
- The user profile from onboarding/profile is stored only in `localStorage` (`userProfile`). It is not persisted on the backend, and `Chat.jsx` doesn't send it (chat starts with an empty profile and echoes back whatever the backend returns).
- Data-fetching effects use a `stale` flag in the cleanup function to drop out-of-order responses.
- ESLint uses core `no-unused-vars`, which can't see `<motion.div>` usage, so `motion` is allow-listed in `eslint.config.js`.
- The stack is Tailwind CSS v4 (via `@tailwindcss/postcss`) + `@tailwindcss/typography`, Framer Motion, and react-three-fiber (`NetworkAnimation`). Chat replies are rendered with `react-markdown` + `remark-gfm`.
