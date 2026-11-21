# Architecture Diagram

KubePilot is a document-question-answering application with a Streamlit client, a FastAPI and LangGraph backend, and a document ingestion pipeline. It uses Groq for language-model tasks, Qdrant for vector storage, and Gemini embeddings with a local fallback.

## Application Architecture

<!-- mermaid-checked: no \n, no em-dash/en-dash, no {} in labels, subgraphs are id["label"], arrows are -->|"label"|, all subgraphs closed by end, ids unique -->
```mermaid
flowchart TD
    subgraph ClientLayer["Client"]
        User["Kubernetes User"]
        UI["Streamlit Chat UI"]
    end
    subgraph ApplicationLayer["Application"]
        API["FastAPI API"]
        Rails["NeMo Guardrails"]
        Workflow["LangGraph Workflow"]
        Planner["Query Planner"]
        Retriever["Document Retriever"]
        Reranker["FlashRank Reranker"]
        Responder["Answer Generator"]
        Memory["In Memory Checkpointer"]
    end
    subgraph IngestionLayer["Ingestion"]
        SourceDocs["PDF, HTML, TXT, DOCX, PPTX"]
        Ingestion["Ingestion Pipeline"]
        Parser["Document Parsers"]
        Chunker["Text Chunker"]
        Embedding["Embedding Service"]
    end
    subgraph DataLayer["Data Store"]
        Qdrant[("Qdrant Collection")]
    end
    subgraph ExternalLayer["External Services"]
        Groq["Groq Language Model"]
        Gemini["Gemini Embeddings"]
        Logfire["Logfire Tracing"]
    end
    subgraph LocalModelLayer["Local Model"]
        SentenceModel["Sentence Transformers"]
    end

    User -->|"ask a question"| UI
    UI -->|"POST query"| API
    API -->|"check request"| Rails
    Rails -->|"allowed request"| Workflow
    Rails -->|"blocked reply"| API
    Workflow -->|"plan request"| Planner
    Planner -->|"conversational route"| Responder
    Planner -->|"technical search"| Retriever
    Workflow -->|"save thread state"| Memory
    Retriever -->|"embed query"| Embedding
    Embedding -->|"primary embedding"| Gemini
    Embedding -.->|"fallback embedding"| SentenceModel
    Gemini -->|"query vector"| Qdrant
    SentenceModel -->|"query vector"| Qdrant
    Qdrant -->|"matching chunks"| Retriever
    Retriever -->|"candidate chunks"| Reranker
    Reranker -->|"ranked context"| Responder
    SourceDocs -->|"documents to index"| Ingestion
    Ingestion -->|"extract text"| Parser
    Parser -->|"plain text"| Chunker
    Chunker -->|"document chunks"| Embedding
    Gemini -->|"document vectors"| Qdrant
    SentenceModel -->|"document vectors"| Qdrant
    Planner -->|"classification prompt"| Groq
    Rails -->|"safety check"| Groq
    Responder -->|"answer prompt"| Groq
    Groq -->|"generated answer"| Responder
    Responder -->|"final answer"| API
    API -->|"answer and sources"| UI
    API -.->|"telemetry"| Logfire
    Ingestion -.->|"telemetry"| Logfire
```

### Technology Stack Summary

| Layer | Technology | Version | Purpose |
| --- | --- | --- | --- |
| Presentation | Streamlit | Not pinned | Chat interface and source display |
| API | FastAPI and Uvicorn | Not pinned | HTTP endpoints for queries and graph |
| Orchestration | LangGraph | Not pinned | Conditional planner, retrieval, and response flow |
| Guardrails | NeMo Guardrails | Not pinned | Checks requests before retrieval |
| Language model | Groq | `GROQ_MODEL`, default `openai/gpt-oss-120b` | Planning, guardrails, and answer generation |
| Embeddings | Gemini embedding model | `gemini-embedding-2-preview` | Primary document and query vectors |
| Embeddings fallback | Sentence Transformers | `all-mpnet-base-v2` | Local 768-dimension fallback |
| Vector storage | Qdrant | Endpoint configured by environment | Stores and searches document vectors |
| Reranking | FlashRank | Not pinned | Locally reranks candidate chunks |
| Observability | Logfire | Not pinned | Application and ingestion tracing |
| Document parsing | pypdf, BeautifulSoup, python-docx, python-pptx | Not pinned | Extracts supported document formats |

Dependency versions are not pinned in `requirements.txt` unless a minimum is specified.

### Data Storage and External Services

Qdrant stores document vectors and payloads in the `enterprise_rag` collection. The ingestion pipeline also writes parsed chunk metadata as JSON under local `processed_data/`. LangGraph uses an in-memory checkpointer, so conversation state is not durable across backend restarts. Groq handles model requests; Gemini provides embeddings, with a local Sentence Transformers fallback. Logfire captures traces when configured.

### Key Architectural Decisions

- A conditional LangGraph workflow skips document retrieval for conversational turns and retrieves context for technical questions.
- FlashRank reranks Qdrant candidates locally before answer generation.
- The Qdrant collection's vector dimension is checked against the selected embedding model to avoid incompatible vectors.
- Conversation state is held in memory; persistent conversation storage is not configured.

## Component Relationships

<!-- mermaid-checked: no \n, no em-dash/en-dash, no {} in labels, subgraphs are id["label"], arrows are -->|"label"|, all subgraphs closed by end, ids unique -->
```mermaid
flowchart LR
    subgraph cPresentation["Presentation"]
        cUser["User"]
        cUI["Streamlit UI"]
        cAPI["FastAPI API"]
    end
    subgraph cOrchestration["Orchestration"]
        cRails["NeMo Guardrails"]
        cGraph["LangGraph Workflow"]
        cPlanner["Planner"]
        cRetriever["Retriever"]
        cReranker["FlashRank Reranker"]
        cResponder["Responder"]
        cMemory["MemorySaver"]
    end
    subgraph cIngestion["Ingestion"]
        cPipeline["Ingestion Pipeline"]
        cParser["Document Parsers"]
        cChunker["Chunker"]
    end
    subgraph cData["Data and Embeddings"]
        cEmbedding["Embedding Service"]
        cQdrant[("Qdrant Collection")]
    end
    subgraph cExternal["External Services"]
        cGroq["Groq"]
        cGemini["Gemini"]
        cLogfire["Logfire"]
    end
    subgraph cLocalModel["Local Model"]
        cSentence["Sentence Transformers"]
    end

    cUser -->|"asks"| cUI
    cUI -->|"HTTP query"| cAPI
    cAPI -->|"validates request"| cRails
    cRails -->|"allowed query"| cGraph
    cRails -->|"uses"| cGroq
    cGraph -->|"invokes"| cPlanner
    cPlanner -->|"classifies with"| cGroq
    cPlanner -->|"technical query"| cRetriever
    cPlanner -->|"conversation"| cResponder
    cGraph -->|"persists thread in"| cMemory
    cRetriever -->|"embeds query with"| cEmbedding
    cEmbedding -->|"primary provider"| cGemini
    cEmbedding -.->|"fallback provider"| cSentence
    cGemini -->|"query vector"| cQdrant
    cSentence -->|"query vector"| cQdrant
    cQdrant -->|"candidate chunks"| cRetriever
    cRetriever -->|"candidate text"| cReranker
    cReranker -->|"ranked context"| cResponder
    cPipeline -->|"reads"| cParser
    cParser -->|"extracted text"| cChunker
    cChunker -->|"document chunks"| cEmbedding
    cGemini -->|"document vectors"| cQdrant
    cSentence -->|"document vectors"| cQdrant
    cResponder -->|"generates with"| cGroq
    cResponder -->|"answer and sources"| cAPI
    cAPI -.->|"traces"| cLogfire
    cPipeline -.->|"traces"| cLogfire
```

### Component Inventory

| Component | Layer | Type | Responsibility |
| --- | --- | --- | --- |
| Streamlit UI | Presentation | Web client | Sends chat requests and displays answers and sources |
| FastAPI API | Presentation | HTTP API | Exposes health, graph, and query endpoints |
| NeMo Guardrails | Orchestration | Request policy | Allows or blocks a user query before retrieval |
| LangGraph Workflow | Orchestration | State graph | Routes requests through planning, retrieval, and response |
| Planner | Orchestration | Agent node | Chooses conversational handling or technical search |
| Retriever | Orchestration | Agent node | Embeds a query and fetches candidate chunks from Qdrant |
| FlashRank Reranker | Orchestration | Ranking service | Orders candidate chunks by semantic relevance |
| Responder | Orchestration | Agent node | Produces the final answer using history and retrieved context |
| MemorySaver | Orchestration | In-memory checkpointer | Retains thread state during the backend process lifetime |
| Ingestion Pipeline | Ingestion | CLI workflow | Processes files and indexes their chunks |
| Document Parsers | Ingestion | File loaders | Extracts text from supported file formats |
| Chunker | Ingestion | Text processor | Splits extracted text into searchable chunks |
| Embedding Service | Data and embeddings | Model adapter | Uses Gemini or the local fallback to create vectors |
| Qdrant Collection | Data and embeddings | Vector store | Stores and searches chunk vectors and payloads |
| Groq | External service | LLM provider | Supports planning, guardrails, and answer generation |
| Gemini | External service | Embedding provider | Creates primary document and query vectors |
| Sentence Transformers | Local model | Embedding model | Provides fallback vectors when Gemini is unavailable |
| Logfire | External service | Observability | Receives application and ingestion traces |
