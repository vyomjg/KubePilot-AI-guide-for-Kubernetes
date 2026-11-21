# KubePilot: AI Guide for Kubernetes

KubePilot is a document-question-answering application built with retrieval-augmented generation (RAG). It ingests documents, creates embeddings, stores them in Qdrant, and answers questions through a Streamlit chat interface.

## How it works

1. The ingestion pipeline extracts text from PDF, HTML, TXT, DOCX, and PPTX files.
2. Text is split into chunks and embedded using Gemini.
3. Chunks and their source names are indexed in the `enterprise_rag` Qdrant collection.
4. The FastAPI backend uses a LangGraph planner, retriever, and responder to answer questions. NeMo Guardrails handles requests before retrieval.
5. The Streamlit UI sends questions to the backend and displays answers and retrieved context.

Conversation state is held in memory by the backend and keyed by a thread ID.

## Requirements

- Python with support for the packages listed in `requirements.txt`
- A Gemini API key for embeddings
- A Groq API key for language-model responses
- A Qdrant URL and API key
- A Logfire token for tracing (optional)

## Setup (Windows PowerShell)

Run these commands from the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set the service credentials:

```dotenv
GEMINI_API_KEY=your-gemini-api-key
GROQ_API_KEY=your-groq-api-key
GROQ_FALLBACK_API_KEY=
QDRANT_API_KEY=your-qdrant-api-key
QDRANT_CLUSTER_ENDPOINT=https://your-qdrant-endpoint
BACKEND_URL=http://localhost:8000
LOGFIRE_TOKEN=
```

Keep `.env` private; it is excluded from Git.

## Run locally

Open two terminals in the project root. Start the API in the first:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Start the chat UI in the second:

```powershell
.\.venv\Scripts\streamlit.exe run ui\app.py --server.port 8501
```

Open <http://localhost:8501> in a browser. The API is available at <http://localhost:8000>; interactive API documentation is at <http://localhost:8000/docs>.

## Ingest documents

Put documents in `DATA/`. The ingestion pipeline supports PDF, HTML, TXT, DOCX, and PPTX files. Subfolders are used as source types; folders containing `true` or `noisy` in their names are labeled accordingly.

Ingest the contents of `DATA/` from the project root:

```powershell
.\.venv\Scripts\python.exe -m app.ingestion.processor DATA
```

To ingest one folder with an explicit source type:

```powershell
.\.venv\Scripts\python.exe -m app.ingestion.processor DATA\true_data true
```

The optional `--wipe` flag deletes and recreates the configured Qdrant collection before ingestion. Use it only when you intend to replace the indexed data.

## API

- `GET /` — health message
- `GET /graph` — agent workflow diagram
- `POST /query` — ask a question

Example request:

```json
{
  "q": "How does the documented Kubernetes workload work?",
  "thread_id": "my-session"
}
```

## Project layout

```text
app/
  agents/       LangGraph planner, retriever, and responder
  guardrails/   Request guardrails
  ingestion/    Document parsing, chunking, and indexing
  services/     Embeddings, Qdrant retrieval, and ranking
  main.py       FastAPI application
ui/
  app.py        Streamlit chat interface
DATA/           Input documents for ingestion
requirements.txt
```

Generated `processed_data/`, local environments, logs, and local dataset additions are excluded by `.gitignore`.
