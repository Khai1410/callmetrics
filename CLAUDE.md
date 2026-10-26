# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

CallMetrics is an internal QA tool for scoring Vietnamese call-center recordings (customer service, sales). Users upload audio or paste a recording URL. The backend transcribes it locally with faster-whisper, then scores every criterion in a criteria set (rubric) with Claude, or with keyword rules as a fallback. QA reviews and edits the scores, then copies them into the company portal. The UI text, README, user-facing error messages and LLM prompts are in Vietnamese. Keep new user-facing strings in Vietnamese.

## Commands

There are no tests, no linter config, and no migration tool in this repo.

- Full stack (Postgres + backend + frontend): `docker compose up -d --build` (same as `deploy.sh` / `deploy.bat`). The app runs at http://localhost:8081 (`FRONTEND_PORT` in `.env`). Stop with `docker compose down`.
- Rebuild a single service after code changes: `docker compose up -d --build backend` (or `frontend`). Neither container has a source bind mount, so every code change needs a rebuild.
- Backend logs: `docker compose logs -f backend`
- Frontend dev server: `cd frontend && npm install && npm run dev` (Vite on :5173, proxies `/api` to `localhost:8000`). Backend port 8000 is not published by default; uncomment the `ports:` block in `docker-compose.yml`, or run uvicorn locally with `DATABASE_URL` pointing at a reachable Postgres.
- Frontend build: `npm run build` (runs `vite build` only, with no `tsc` type-check step; run `npx tsc --noEmit` to type-check).
- Backend locally: `cd backend && uvicorn app.main:app --reload` (needs `DATABASE_URL`, `STORAGE_DIR`, and ffmpeg on PATH for whisper).

Configuration comes from env vars passed through `docker-compose.yml` from `.env` (see `.env.example`): `WHISPER_MODEL_SIZE` (default `medium`), `WHISPER_INITIAL_PROMPT`, `LLM_PROVIDER` (`anthropic` | `ollama`), `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `OLLAMA_MODEL`, `OLLAMA_NUM_CTX`, `OLLAMA_TIMEOUT`.

Local LLM: the `ollama` and one-shot `ollama-pull` services only start under the `ollama` compose profile (`COMPOSE_PROFILES=ollama` in `.env`). Models persist in the `ollama_models` volume. To try another model: `docker compose exec ollama ollama pull <model>`, then set `OLLAMA_MODEL` and rebuild the backend. Check backend logs for `AI scoring failed`, because failures silently fall back to keyword scoring.

## Architecture

**Request path:** browser → nginx (`frontend/nginx.conf`: serves the static SPA, proxies `/api/` to `backend:8000`, `client_max_body_size 300m`) → FastAPI. Every backend route is under the `/api` prefix. The frontend calls go through the single axios client in `frontend/src/api/client.ts`. Its TS types in `frontend/src/api/types.ts` mirror `backend/app/schemas.py` by hand, so keep the two in sync when you change a schema.

**Schema management:** there are no migrations. `main.py` runs `Base.metadata.create_all` on startup, so it creates new tables but **never alters existing ones**. Adding a column to a model in `models.py` needs a manual `ALTER TABLE` against the `db_data` volume, or a volume reset (`docker compose down -v`, which wipes all data).

**Seeding:** on startup, `seed/run_seed.py` loads `seed/seed_data.json`: the CALL IN / CALL OUT criteria sets, converted from `KHUNG CHẤM ĐIỂM.xlsx`. It inserts a set only if no set with that `code` exists yet, so editing the JSON doesn't change a DB that is already seeded. `scripts/read_xlsx.py` dumps the xlsx to `scripts/out.txt` to help with regenerating the seed.

**Record lifecycle** (`routers/records.py`): status goes `uploaded`/`fetching` → `transcribing` → `transcribed` | `failed`. Transcription runs as a FastAPI `BackgroundTasks` job in the backend process, with no queue. Background jobs open their own `SessionLocal()` rather than using the request's `get_db` session. The Whisper model is a lazily loaded, lock-guarded singleton in `transcription.py`, with Vietnamese hard-coded. Audio files go to `STORAGE_DIR` (bind-mounted to `./storage/audio`).
- `POST /api/records/from-url`: `_resolve_audio_url` handles recording portals that return a *player page* (e.g. `player.php?src=...`) instead of the audio file. It tries common query params first, then scrapes `<audio>`/`<source>` tags. `_assert_safe_url` is a basic SSRF guard (http/https only, rejects private/loopback IPs). Downloads are capped at 300MB to match nginx.

**Scoring** (`routers/scoring.py`): creating a scoring session snapshots the record's active criteria into `ScoreItem` rows, with `auto_score`/`auto_evidence` and `final_score` initialized to `auto_score`.
1. If the LLM provider is configured, `llm_scoring.score_with_ai` makes **one** LLM call for the whole criteria set. That is Claude via `output_config` json_schema, or Ollama `/api/chat` with `format` = the same schema. Both share the prompt, schema and post-processing. The call is synchronous inside the request, which is why nginx `proxy_read_timeout` is high for slow CPU inference. The schema `enum`-constrains `criterion_id`. The call also proposes `call_content_type`, `failed_point_tags`, and `overall_comment`. Returned scores are snapped to the nearest configured `score_options` value. AI evidence is prefixed `[AI]`, and the frontend uses that prefix to show the "Chấm bởi AI" badge.
2. If AI is off or fails (it returns `None` on any error and never raises into the request), or misses a criterion, `scoring_engine.auto_score_criterion` applies keyword rules. This only covers criteria with `check_type == "keyword"` and a `check_config` of `groups[{name, keywords, required}]` plus `score_full`/`score_partial`/`score_none`. Other criteria stay unscored for manual QA.
3. `POST /scoring-sessions/{id}/complete` computes the weighted total (`compute_total`, which only counts criteria with `include_in_total` and a weight, and errors if any are unscored). It then maps the total to a label via the criteria set's `thresholds` (`classify`).

**Data model notes:** IDs are string UUIDs. Rubric structure (`score_options`, `thresholds`, `call_content_types`, `failed_point_tags`, `check_config`) is stored in JSON columns rather than tables. A record's `criteria_set_id` can be changed with `PATCH /records/{id}`. Deleting a record also deletes its audio file and cascades to its transcript and sessions.

**Frontend:** React 18 + react-router, three pages (`RecordsListPage`, `RecordScorePage`, `CriteriaPage`), plain CSS in `styles.css`, no state library.
