# Aeza Codex

A RAG-powered knowledge base chat application built with FastAPI, FAISS, and OpenAI.

## Project Structure

```
aeza-codex/
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── chat.py
│   │   ├── knowledge.py
│   │   └── admin.py
│   │
│   ├── services/
│   │   ├── chat.py
│   │   └── knowledge.py
│   │
│   ├── ingestion/
│   │   ├── loader.py
│   │   ├── chunker.py
│   │   └── pipeline.py
│   │
│   ├── rag/
│   │   ├── embeddings.py
│   │   ├── faiss.py
│   │   └── generator.py
│   │
│   ├── storage/
│   │   └── storage.py          ← persistent storage abstraction
│   │
│   ├── templates/
│   │   ├── admin.html
│   │   └── chat.html
│   │
│   └── static/
│       ├── css/
│       └── js/
│
├── data/                       ← local development only
│   ├── documents/
│   ├── indexes/
│   └── metadata/
│
├── .env.example
├── requirements.txt
├── vercel.json
├── README.md
└── LICENSE
```

## Quick Start

1. **Clone and install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key
   ```

3. **Run locally**

   ```bash
   uvicorn app.main:app --reload
   ```

4. **Open in browser**

   - Chat UI: `http://localhost:8000/api/admin/` (admin) or add a chat route
   - Health check: `http://localhost:8000/health`

## API Endpoints

| Method | Path                    | Description              |
|--------|-------------------------|--------------------------|
| POST   | `/api/chat/`            | Send a chat message      |
| POST   | `/api/knowledge/ingest` | Upload & index a document|
| GET    | `/api/knowledge/documents` | List indexed documents |
| GET    | `/api/admin/`           | Admin panel              |
| POST   | `/api/admin/reindex`    | Re-index knowledge base  |

## Deployment

Deploy to Vercel using the included `vercel.json` configuration.

## License

See [LICENSE](LICENSE).
