import time
import logfire
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings


BATCH_SIZE = 50
_GEMINI_DIM = 3072
_FALLBACK_DIM = 768

_active_model = None
_model_type: str | None = None
_model_dim: int | None = None


def _probe_gemini():
    """Try one embed call to verify Gemini is reachable. Returns model or None """
    try:
        model = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-2-preview",
            google_api_key=settings.GEMINI_API_KEY,
        )
        model.embed_query("probe")
        logfire.info("Gemini embedding ready (gemini-embedding-2-preview, 3072-dim).")
        return model
    except Exception as e:
        logfire.warning(f"Gemini embedding probe failed: {e}. Will use sentence- transformers fallback (768-dim).")
        return None

def _load_fallback():
    from sentence_transformers import SentenceTransformer
    logfire.info("Loading sentence-transformer fallback(all-mpnet-base-v2, 768-dim).")
    return SentenceTransformer("all-mpnet-base-v2")

def _init(expected_dim: int | None = None):
    global _active_model, _model_type, _model_dim
    if expected_dim not in (None, _GEMINI_DIM, _FALLBACK_DIM):
        raise ValueError(f"Unsupported embedding dimension: {expected_dim}")

    if _active_model is not None:
        if expected_dim is not None and _model_dim != expected_dim:
            raise ValueError(
                f"Active embedding model outputs {_model_dim} dimensions, "
                f"but the Qdrant collection expects {expected_dim}."
            )
        return

    if expected_dim == _FALLBACK_DIM:
        _active_model = _load_fallback()
        _model_type = "fallback"
        _model_dim = _FALLBACK_DIM
        return

    gemini = _probe_gemini()
    if gemini:
        _active_model = gemini
        _model_type = "gemini"
        _model_dim = _GEMINI_DIM
    elif expected_dim == _GEMINI_DIM:
        raise RuntimeError(
            "The Qdrant collection expects 3072-dimensional vectors, "
            "but the Gemini embedding model is unavailable."
        )
    else:
        _active_model = _load_fallback()
        _model_type = "fallback"
        _model_dim = _FALLBACK_DIM

def get_embedding_dim(expected_dim: int | None = None) -> int:
    """Return the active model dimension, optionally matching a Qdrant collection."""
    _init(expected_dim)
    return _model_dim

def _embed_batch(batch: list[str]) -> list[list[float]]:
    if _model_type == "gemini":
        # Exponential backoff: 1 s → 2 s → 4 s → 8 s (4 attempts total)
        for attempt in range(4):
            try:
                return _active_model.embed_documents(batch)
            except Exception as e:
                err = str(e).lower()
                is_rate_limit = any(x in err for x in ("429", "rate", "quota", "resource_exhausted"))
                if is_rate_limit and attempt < 3:
                    wait = 2 ** attempt
                    logfire.warning(
                        f"Gemini rate limit hit — retrying in {wait}s "
                        f"(attempt {attempt + 1}/4)."
                    )
                    time.sleep(wait)
                else:
                    logfire.error(f"Gemini embedding failed: {e}")
                    raise
        raise RuntimeError("Gemini rate limit persisted after 4 attempts.")
    else:
        return _active_model.encode(batch, show_progress_bar=False).tolist()

def embed_query(query: str, expected_dim: int | None = None) -> list[float]:
    if expected_dim not in (None, _GEMINI_DIM, _FALLBACK_DIM):
        raise ValueError(f"Unsupported embedding dimension: {expected_dim}")

    _init(expected_dim)

    if _model_type == "gemini":
        return _active_model.embed_query(query)
    return _active_model.encode([query])[0].tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    _init()
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        with logfire.span("Embed batch", model=_model_type, start=i, size=len(batch)):
            all_embeddings.extend(_embed_batch(batch))
    return all_embeddings