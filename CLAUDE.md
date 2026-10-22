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
uv run python scripts/backup_data.py restore   # write the dataset JSON files from the SQLite backup
uv run python scripts/backup_data.py build [--compare-atlas]   # create a new backup (refuses to overwrite one)
uv run python scripts/build_clean_db.py   # rebuild the cleaned database data/schemes.sqlite from the backup
uv run python scripts/verify_clean_db.py   # check its markdown with the frontend's remark parser (needs frontend/node_modules)
curl -X POST -H "Authorization: Bearer dev_test_123" "localhost:8000/api/admin/vectorize?force=true"  # rebuild the Qdrant index (needs AUTH_DEV_BYPASS=true, or a real Clerk session token)
ollama serve   # local Ollama for embeddings (`ollama pull nomic-embed-text`), and for chat unless OLLAMA_HOST points at Ollama Cloud
```

Run backend commands from `backend/`: imports are `app.*`, and relative paths such as `./qdrant_data` and the dataset JSON files resolve from there.

## Environment

- `frontend/.env`: `VITE_CLERK_PUBLISHABLE_KEY` (the app throws on startup without it), `VITE_API_URL` (the base URL *including* `/api`, e.g. `http://localhost:8000/api`).
- `backend/.env` (read in `app/config.py`):
  - `MONGO_URI`: the team's Atlas cluster (`nariconnect.detailed_schemes`). If MongoDB is unreachable, chat still works without deep details and `/api/schemes*` return 503.
  - `CLERK_PUBLISHABLE_KEY`: the backend derives the Clerk issuer (`https://<instance>.clerk.accounts.dev`) from it and fetches public JWKS from there; no secret key is needed. `CLERK_ISSUER` overrides the derivation; `CLERK_AUTHORIZED_PARTIES` (default `http://localhost:5173`) lists the frontend origins accepted in the token's `azp` claim.
  - `OLLAMA_HOST` + `OLLAMA_API_KEY` + `OLLAMA_MODEL`: the chat model. Currently Ollama Cloud (`https://ollama.com`, `gpt-oss:120b`).
  - `OLLAMA_EMBED_HOST` + `OLLAMA_EMBED_MODEL` (default `nomic-embed-text`): embeddings must come from the model that built the Qdrant index. Ollama Cloud has no embedding models, so this points at local Ollama.
  - `AUTH_DEV_BYPASS` (default off; when true, the bearer token `dev_test_123` authenticates as `dev_user_123` for curl/Swagger testing), `QDRANT_PATH` (default `./qdrant_data`), `SARVAM_API_KEY` (not used yet). `data_scraper.py` reads `MYSCHEME_API_KEY`.
- Dataset files are gitignored (`*.json`). `scripts/backup_data.py restore` writes them from the backup `backend/data/nariconnect_data.sqlite` (gitignored, read-only, checksum in `.sha256`):
  - `myscheme_rag_dataset.json`: the basic list used for vectorization, byte-identical to the copy committed in `0cd0f3d`. Its row order is the Qdrant point order, and it contains repeated records plus two different schemes sharing the slug `tufs`.
  - `detailed_schemes_from_mongo.json`: the Mongo documents (with `_id` as `{"$oid": …}`), for `seed_atlas.py -f FILE --no-clear`; `mongo_export/` holds the original dump. The raw scraper output `myscheme_deep_rag_dataset_v6.json` is lost. These documents already passed through the `Scheme` model, which dropped undeclared fields. `mdiis` and `mdscy` hold a `<nested data …>` placeholder in place of a whole section, so re-seeding with `seed_atlas.py` skips them (and its default clear would delete them). Four basic-list schemes (`gpyuk`, `pmmvy`, `sn2408`, `usp`) have no detailed document.
  - `data_scraper.py` re-fetches detailed data from the myscheme.gov.in API.
- The backup also holds the Qdrant vectors and payloads (`embeddings`) and a `provenance` table. Qdrant's own storage is pickled `qdrant_client` objects, which depend on the library version.
- `backend/data/schemes.sqlite` (gitignored, rebuilt by `build_clean_db.py`) is the cleaned, normalized copy; the app doesn't read it yet. It uses STRICT tables:
  - `schemes`: one row per distinct myScheme record. Long sections live in `scheme_content`.
  - Lookup tables (`states`, `ministries`, `departments`, `categories`, `subcategories`, `tags`, `beneficiary_types`) and `scheme_*` link tables. `application_channels`, `scheme_references` and `scheme_definitions` are ordered by `position`.
  - `data_issues` lists every value that is missing, was dropped, or was repaired by a guess (e.g. `http://` added to a bare domain).
  - All text is normalized and rich text is GFM markdown rendered from myScheme's node trees (not its `_md` fields). URLs in text become `<…>` autolinks.
  - After changing the renderer, run `verify_clean_db.py`. It parses every value as the frontend would and requires the same characters in the same order as the source (whitespace aside), no raw HTML or leftover markup, and the source's headings, quotes and tables.
  - Scheme ids are new; they don't match Qdrant point ids (the backup's `schemes.row_index`).

## Architecture

### Chat RAG pipeline (`app/routers/chat.py`, `POST /api/chat`)
1. `ollama_service.extract_user_info` asks the LLM for `{age, gender, occupation, state, income}` (with a `format=` JSON schema, which `gpt-oss` ignores; `parse_json_object` also handles fenced/wrapped JSON). The result is merged over the client's `user_profile` (see Backend conventions).
2. The profile, the last two user turns and the message are combined into a text query, so follow-ups ("which of those…") keep their topic. `vector_service.search_schemes` embeds it and returns the top 5 hits from Qdrant, filtered to schemes whose `states` payload is "All" or includes the user's state (matched case-insensitively to the payload's spelling).
3. The hit IDs are scheme **slugs**. They are used to fetch the full documents from MongoDB `nariconnect.detailed_schemes`, which are attached as `deep_details`.
4. `ollama_service.chat_with_context` sends the "Nari" persona system prompt (only schemes from the context or earlier in the conversation may be named), the prior `chat_history`, and the context, where each scheme is prefixed with `ID: <slug>`. The LLM must end its reply with `{"recommended_schemes": ["<slug>", ...]}`. That block is stripped, and `select_recommended` returns only those schemes as cards. `hide_scheme_ids` swaps any slug that leaks into the text for the scheme name, and `<br>` tags are converted to markdown breaks. If you change the prompt, keep this contract.
5. Chat calls retry transient Ollama errors (`_chat`); if the model or embeddings are unreachable the route returns 502, and a failed extraction just falls back to the client profile.

### Two data stores, joined by slug
- **Qdrant** (embedded, on-disk at `QDRANT_PATH`, collection `schemes`, 768-dim cosine, sized for `nomic-embed-text`). It is built from `myscheme_rag_dataset.json` by `vectorize_schemes()`. Point IDs are sequential ints, and the slug is stored in the payload as `scheme_id`. `search_schemes` automatically vectorizes when the collection is empty, so the first chat request can take a long time. Changing the embed model means changing the vector size and re-vectorizing with `force=true`. The embedded Qdrant takes a file lock (`qdrant_data/.lock`), so only one process can open it at a time.
- **MongoDB** `detailed_schemes`: documents are validated by `app/models/scheme_models.Scheme` and upserted by slug by `scripts/seed_atlas.py`. The script also creates a unique `slug` index and flattens overly deep nesting to avoid BSON depth errors.

### Backend conventions
- Auth: every `/api/*` route depends on `get_current_user` (`app/auth/clerk.py`), either per route or via `APIRouter(dependencies=[...])`. It verifies the Clerk session JWT (RS256) against `<CLERK_ISSUER>/.well-known/jwks.json`, validates `iss`, requires `exp` and `sub`, and checks `azp` against `CLERK_AUTHORIZED_PARTIES`. `/api/admin/vectorize` accepts any signed-in user; there is no admin role yet.
- MongoDB access goes through the async `motor` client from `app/db/mongo.get_database()`. The Ollama and embedded Qdrant clients are synchronous: call them via `asyncio.to_thread` inside `async def` routes, or make the route a plain `def`, so they don't block the event loop.
- `/api/chat` merges profiles: the client's `user_profile` is the base and values newly extracted from the message override it (`clean_profile` drops empty values and 0s). Only `user`/`assistant` turns from `chat_history` are forwarded to the LLM.
- Regex filters in `/api/schemes` escape user input with `re.escape`.
- CORS allows only `http://localhost:5173` (`main.py`).
- `backend/utils.py` and `backend/rag_engine.pymodels.py` are empty leftovers. `backend/plan.md` is early hackathon notes and does not describe the current code.

### Frontend
- `App.jsx` holds all routing. Clerk's `ClerkProvider` is inside `BrowserRouter`, and each protected route is wrapped in `<SignedIn>`/`<SignedOut><RedirectToSignIn/>`. Sign-up redirects to `/onboarding`.
- All backend calls go through `src/services/api.js`, which receives a token from Clerk's `useAuth().getToken()` in the calling component.
- The user profile from onboarding/profile is stored only in `localStorage` (`userProfile`); it is not persisted on the backend. `Chat.jsx` maps it to the backend profile shape (`age`, `state`, `occupation` ← `employmentStatus`, `income` ← `annualIncome`) as the starting profile.
- The chat conversation is kept in `sessionStorage` (`nariconnect.chat.<clerk user id>`) so it survives opening a scheme card and coming back. Scheme cards link to `/schemes/:slug`; the details page's Back button uses history when available.
- Scheme markdown from myScheme contains `<br>`/`&lt;br&gt;` and multiply-escaped entities (`&amp;amp;#39;`); `SchemeDetails.cleanMarkdown` normalizes them before rendering.
- Data-fetching effects use a `stale` flag in the cleanup function to drop out-of-order responses.
- ESLint uses core `no-unused-vars`, which can't see `<motion.div>` usage, so `motion` is allow-listed in `eslint.config.js`.
- The stack is Tailwind CSS v4 (via `@tailwindcss/postcss`) + `@tailwindcss/typography`, Framer Motion, and react-three-fiber (`NetworkAnimation`). Chat replies are rendered with `react-markdown` + `remark-gfm`.
