"""Embedding generation."""

from app.config import settings


async def embed(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    if not texts:
        return []

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    from openai import AsyncOpenAI

    kwargs: dict = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    client = AsyncOpenAI(**kwargs)
    create_kwargs: dict = {
        "model": settings.embedding_model,
        "input": texts,
    }
    if "nvidia.com" in (settings.openai_base_url or ""):
        create_kwargs["encoding_format"] = "float"
        create_kwargs["extra_body"] = {"input_type": "query", "truncate": "NONE"}
    response = await client.embeddings.create(**create_kwargs)
    return [item.embedding for item in response.data]
