import logfire
from qdrant_client import QdrantClient
from app.config import settings
from app.services.retrieval.embeddings import embed_query


# Initialize Qdrant Client
client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY
)

def search_enterprise_knowledge(query: str, limit: int = 8):
    """
    Performs a high-precision search in the enterprise knowledge base.
    Uses the modern query_points interface.
    """
    try:
        collection = client.get_collection(settings.QDRANT_COLLECTION)
        vectors_config = collection.config.params.vectors
        if isinstance(vectors_config, dict):
            raise ValueError(
                "Named Qdrant vectors require an explicit embedding-vector configuration."
            )

        vector_size = vectors_config.size
        query_vector = embed_query(query, expected_dim=vector_size)

        # Using query_points - the modern standard for Qdrant
        response = client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=query_vector,
            limit=limit,
            with_payload=True # JSON
        )

        results = []
        for res in response.points:
            results.append({
                "content": res.payload.get("text", ""),
                "source": res.payload.get("source", "Unknown"),
                "score": res.score
            })
        
        return results
    except Exception as e:
        logfire.error(f"❌ Qdrant Search Failed: {e}")
        return []
