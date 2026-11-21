import logfire
from app.agents.state import AgentState
from app.gateway import portkey_client, extract_cache_status


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    marker = "\n[truncated]"
    return text[:max(0, max_chars - len(marker))] + marker[:max_chars]


def _format_history(messages: list[dict], max_chars: int) -> str:
    history = [
        f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
        for msg in messages
    ]
    result = ""
    for entry in reversed(history):
        separator = "\n"
        remaining = max_chars - len(result) - len(separator)
        if remaining <= 0:
            break
        if len(entry) > remaining:
            result = entry[-remaining:] + result
            break
        result = entry + separator + result
    return result.strip()


def _format_context(documents: list[str], max_chars: int) -> str:
    parts = []
    remaining = max_chars
    for doc in documents:
        if remaining <= 0:
            break
        separator = "\n\n" if parts else ""
        available = remaining - len(separator)
        if available <= 0:
            break
        parts.append(separator + _truncate(doc, available))
        remaining -= len(parts[-1])
        if len(doc) > available:
            break
    return "".join(parts)


def generate_node(state: AgentState):
    """
    Synthesizes a response using both Documentation Context AND Conversation History.
    Uses the native Portkey client (not LangChain) so we can read the
    x-portkey-cache-status response header and surface Cache: Hit in the UI.
    """
    query = state["current_query"]

    user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    if query == "CONVERSATIONAL":
        logfire.info("Generating conversational response using memory.")
        history_str = _format_history(state["messages"][:-1], max_chars=3000)
        user_msg = _truncate(user_msg, max_chars=1500)
        prompt = f"""
        You are a friendly and helpful Enterprise AI Assistant.
        Answer the user's latest message using the CONVERSATION HISTORY below.

        CONVERSATION HISTORY:
        {history_str}

        LATEST MESSAGE:
        "{user_msg}"
        """
    else:
        logfire.info("Generating technical RAG response.")
        max_context_chars = 4000
        full_context = _format_context(state["documents"], max_context_chars)
        history_str = _format_history(state["messages"][:-1], max_chars=800)
        user_msg = _truncate(user_msg, max_chars=1000)
        logfire.info(
            "Prepared bounded LLM input "
            f"(context={len(full_context)}, history={len(history_str)}, "
            f"question={len(user_msg)} chars)."
        )

        prompt = f"""
        You are a Senior Technical Architect.
        Answer the question using the TECHNICAL CONTEXT provided.

        TECHNICAL CONTEXT:
        {full_context}

        CONVERSATION HISTORY:
        {history_str}

        USER QUESTION:
        "{user_msg}"
        """

    with logfire.span("✍️ LLM Synthesis"):
        try:
            response = portkey_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            content = response.choices[0].message.content
            cache_status = extract_cache_status(response)
            is_cache_hit = cache_status == "HIT"

            if is_cache_hit:
                logfire.info("⚡ Gateway Cache Hit — response served from Portkey cache.")
                plan_update = state["plan"] + ["Cache: Hit ⚡"]
                status = "Cache hit — instant response."
            else:
                logfire.info("✅ Response synthesised via LLM.")
                plan_update = state["plan"]
                status = "Response generated."

            return {
                "final_answer": content,
                "status": status,
                "plan": plan_update,
                "messages": [{"role": "assistant", "content": content}]
            }

        except Exception as e:
            logfire.error(f"LLM Generation failed: {e}")
            raise e
