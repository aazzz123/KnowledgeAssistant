from retrieval.search_service import search_knowledge


def vector_search(user_query: str) -> str:
    """Search private knowledge base chunks related to the user query."""
    return search_knowledge(user_query).rendered_context
