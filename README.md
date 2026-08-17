# Aeza Codex

Self-hostable RAG chatbot for a business knowledge base. FastAPI backend, vanilla HTML/CSS/JS admin and chat UIs, OpenAI embeddings + chat, and FAISS over local disk storage.

## Features

- Customer chat at `/chat` with grounded answers from indexed documents and website pages
- Admin dashboard at `/admin` (custom login) for uploads, URL ingest, branding, and reindex
- PDF / DOCX / TXT upload and single-page website ingest (no crawl)
- FAISS vector index persisted via `LocalStorage` (local) or `BlobStorage` (Vercel)

## Requirements

- Python 3.11+
- LLM API key (NVIDIA NIM or OpenAI-compatible)
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
# Edit .env — at minimum set OPENAI_API_KEY, OPENAI_BASE_URL, and ADMIN_PASSWORD
```

## Run

From the repo root:

```bash
uvicorn app.main:app --reload
```

Then open:

- Chat: http://localhost:8000/chat
- Admin: http://localhost:8000/admin
- Health: http://localhost:8000/health

## Environment variables

| Variable | Required | Default | Notes |
|----------|----------|---------|--------|
| `OPENAI_API_KEY` | Yes (prod) | — | NVIDIA or OpenAI key; production startup fails if missing |
| `OPENAI_BASE_URL` | For NVIDIA | — | e.g. `https://integrate.api.nvidia.com/v1` |
| `ADMIN_PASSWORD` | Yes for admin | — | Empty → admin routes return 503 |
| `ADMIN_USERNAME` | No | `admin` | HTTP Basic username |
| `ENVIRONMENT` | No | `development` | Use `production` to enforce API key at startup |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | NVIDIA: `nvidia/nv-embedqa-e5-v5` |
| `CHAT_MODEL` | No | `gpt-4o-mini` | NVIDIA: `openai/gpt-oss-120b` |
| `CHAT_MAX_TOKENS` | No | `4096` | Completion budget (needed for reasoning models) |
| `DATA_DIR` | No | `data` | Local documents, metadata, FAISS bytes |
| `MAX_UPLOAD_SIZE_MB` | No | `10` | |
| `RAG_TOP_K` | No | `5` | |
| `RAG_MIN_SCORE` | No | `0.25` | Minimum similarity for retrieved chunks |
| `WEB_FETCH_TIMEOUT_SECONDS` | No | `15` | |
| `WEB_FETCH_MAX_BYTES` | No | `2000000` | Max HTML body size for URL ingest |
| `STORAGE_BACKEND` | No | `local` (auto `blob` on Vercel) | `local` or `blob` |
| `BLOB_PREFIX` | No | `aeza-codex` | Root folder inside Vercel Blob store |

## Deploy on Vercel (with Vercel Blob)

Aeza Codex can run on Vercel using **Vercel Blob** for durable storage (documents, FAISS index, catalogs, admin data). FAISS still loads in memory per function instance; cold starts reload the index from Blob (first request may be slower).

### 1. Create Blob store

In the Vercel project: **Storage → Create → Blob**, connect it to the project. This adds `BLOB_READ_WRITE_TOKEN` automatically.

### 2. Environment variables

Set these in the Vercel dashboard (names must use only letters, digits, and underscores):

| Name | Example value |
|------|----------------|
| `ENVIRONMENT` | `production` |
| `OPENAI_API_KEY` | your API key |
| `OPENAI_BASE_URL` | `https://integrate.api.nvidia.com/v1` |
| `ADMIN_PASSWORD` | strong password |
| `ADMIN_USERNAME` | `admin` |
| `EMBEDDING_MODEL` | `nvidia/nv-embedqa-e5-v5` |
| `CHAT_MODEL` | `openai/gpt-oss-120b` |
| `STORAGE_BACKEND` | `blob` |

Model paths go in the **value** of `EMBEDDING_MODEL` / `CHAT_MODEL`, not as separate variable names.

### 3. Deploy

Push to GitHub and import the repo on Vercel, or run `vercel --prod`. The repo includes [`vercel.json`](vercel.json) and [`pyproject.toml`](pyproject.toml) for Python 3.12.

### 4. Verify

- `GET /health` → `{ "status": "ok", "storage_backend": "blob", "ready": true }`
- `/admin` and `/chat` load without 500 errors
- Upload a document in admin; it should appear under `aeza-codex/` in your Blob store

### Local dev with Blob (optional)

```bash
vercel env pull .env.local
# Add STORAGE_BACKEND=blob to .env.local
uvicorn app.main:app --reload
```

## Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | Public | Liveness |
| GET | `/chat` | Public | Customer chat UI |
| GET | `/admin` | Public UI | Admin UI (login required for API) |
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
app/api → app/services → app/ingestion | app/rag → app/storage (LocalStorage or BlobStorage)
templates/ + static/ (vanilla JS)
data/ (local) or Vercel Blob (serverless)
```

Local development uses **local disk** by default. On Vercel (`VERCEL=1`), storage auto-selects **Blob** unless `STORAGE_BACKEND=local` is set.

## Operational notes

- Run a **single** uvicorn process; multi-worker would duplicate/desync the in-memory FAISS index.
- Website ingest validates DNS/IP (blocks private/loopback/link-local) and does not auto-follow redirects without re-checking each hop.
- Admin password and OpenAI key must be set for a usable production-like setup.

## License

See [LICENSE](LICENSE).
