import logfire
from groq import Groq
from langchain_groq import ChatGroq

from app.config import settings

# Initialize Groq clients
groq_client = Groq(api_key=settings.GROQ_API_KEY)
fallback_client = Groq(api_key=settings.GROQ_FALLBACK_API_KEY) if settings.GROQ_FALLBACK_API_KEY else None


class GroqCompletionWrapper:
    """Provides a chat.completions.create interface using Groq with automatic fallback."""
    def create(self, *args, **kwargs):
        if "model" not in kwargs:
            kwargs["model"] = settings.GROQ_MODEL
        try:
            return groq_client.chat.completions.create(*args, **kwargs)
        except Exception as e:
            if fallback_client:
                logfire.warning(f"Primary Groq client failed ({e}). Trying fallback Groq key...")
                return fallback_client.chat.completions.create(*args, **kwargs)
            raise e


class GroqClientFacade:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": GroqCompletionWrapper()})()


# Drop-in replacement for the previous portkey_client
portkey_client = GroqClientFacade()


def get_langchain_llm(feature: str = "rag") -> ChatGroq:
    """
    Returns a direct Groq LLM instance (ChatGroq) for LangChain and LangGraph nodes.
    Supports automatic fallback to GROQ_FALLBACK_API_KEY if configured.
    """
    primary = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL,
        temperature=0
    )
    if settings.GROQ_FALLBACK_API_KEY:
        fallback = ChatGroq(
            api_key=settings.GROQ_FALLBACK_API_KEY,
            model=settings.GROQ_MODEL,
            temperature=0
        )
        return primary.with_fallbacks([fallback])
    return primary


def extract_cache_status(response) -> str:
    """Cache status helper (returns 'LIVE' for direct Groq responses)."""
    return "LIVE"