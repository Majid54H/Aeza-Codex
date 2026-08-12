"""Embedding generation."""

from app.config import settings


async def embed(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    if not texts:
        return []

    if not settings.openai_api_key:
        # Placeholder zero vectors for local dev without API key
        dim = 1536
        return [[0.0] * dim for _ in texts]

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]
