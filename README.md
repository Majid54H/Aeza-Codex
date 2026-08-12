# Aeza Codex

Self-hostable RAG chatbot for a business knowledge base. FastAPI backend, vanilla HTML/CSS/JS admin and chat UIs, OpenAI embeddings + chat, and FAISS over local disk storage.

## Features

- Customer chat at `/chat` with grounded answers from indexed documents and website pages
- Admin dashboard at `/admin` (HTTP Basic auth) for uploads, URL ingest, branding, and reindex
- PDF / DOCX / TXT upload and single-page website ingest (no crawl)
- FAISS vector index persisted under `data/` via `LocalStorage`

## Requirements

- Python 3.11+
- OpenAI API key
- Single-process deployment (do **not** run multiple uvicorn workers — FAISS is in-memory per process)

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY and ADMIN_PASSWORD
```

## Run

From the repo root:

```bash
uvicorn app.main:app --reload
```

Then open:

- Chat: http://localhost:8000/chat
- Admin: http://localhost:8000/admin (browser will prompt for Basic auth)
- Health: http://localhost:8000/health

## Environment variables

| Variable | Required | Default | Notes |
|----------|----------|---------|--------|
| `OPENAI_API_KEY` | Yes (prod) | — | Required for embeddings and chat; production startup fails if missing |
| `ADMIN_PASSWORD` | Yes for admin | — | Empty → admin routes return 503 |
| `ADMIN_USERNAME` | No | `admin` | HTTP Basic username |
| `ENVIRONMENT` | No | `development` | Use `production` to enforce API key at startup |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | |
| `CHAT_MODEL` | No | `gpt-4o-mini` | |
| `DATA_DIR` | No | `data` | Local documents, metadata, FAISS bytes |
| `MAX_UPLOAD_SIZE_MB` | No | `10` | |
| `RAG_TOP_K` | No | `5` | |
| `RAG_MIN_SCORE` | No | `0.25` | Minimum similarity for retrieved chunks |
| `WEB_FETCH_TIMEOUT_SECONDS` | No | `15` | |
| `WEB_FETCH_MAX_BYTES` | No | `2000000` | Max HTML body size for URL ingest |

## Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | Public | Liveness |
| GET | `/chat` | Public | Customer chat UI |
| GET | `/admin` | Basic | Admin UI |
| POST | `/api/chat` | Public | Send a chat message |
| GET | `/api/admin/settings` | Public | Branding for chat UI |
| PUT | `/api/admin/settings` | Basic | Update branding |
| POST | `/api/admin/reindex` | Basic | Rebuild FAISS from stored docs |
| POST | `/api/knowledge/upload` | Basic | Upload & index a document |
| POST | `/api/knowledge/ingest` | Basic | Alias of `/upload` |
| POST | `/api/knowledge/url` | Basic | Fetch & index one public page |
| GET | `/api/knowledge/documents` | Public | List indexed sources |

## Architecture (V1)

```
app/api → app/services → app/ingestion | app/rag → app/storage (LocalStorage)
templates/ + static/ (vanilla JS)
data/{documents,indexes,metadata}
```

Persistent V1 uses **local disk only**. Serverless platforms (including Vercel) are **not supported** for durable knowledge — there is no `vercel.json`.

## Operational notes

- Run a **single** uvicorn process; multi-worker would duplicate/desync the in-memory FAISS index.
- Website ingest validates DNS/IP (blocks private/loopback/link-local) and does not auto-follow redirects without re-checking each hop.
- Admin password and OpenAI key must be set for a usable production-like setup.

## License

See [LICENSE](LICENSE).
