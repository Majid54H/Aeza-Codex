"""Embedding generation."""

from openai import AsyncOpenAI

from app.config import settings


def _client() -> AsyncOpenAI:
    kwargs: dict = {
        "api_key": settings.openai_api_key,
        "timeout": settings.llm_timeout_seconds,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return AsyncOpenAI(**kwargs)


async def embed(texts: list[str], input_type: str = "query") -> list[list[float]]:
    """Generate embeddings for a list of texts.

    NVIDIA retrieval models expect ``passage`` for indexed documents and
    ``query`` for search questions.
    """
    if not texts:
        return []

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = _client()
    create_kwargs: dict = {
        "model": settings.embedding_model,
        "input": texts,
    }
    if "nvidia.com" in (settings.openai_base_url or ""):
        nvidia_input_type = input_type if input_type in {"query", "passage"} else "query"
        create_kwargs["encoding_format"] = "float"
        create_kwargs["extra_body"] = {"input_type": nvidia_input_type, "truncate": "NONE"}
    response = await client.embeddings.create(**create_kwargs)
    return [item.embedding for item in response.data]
