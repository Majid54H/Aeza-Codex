"""LLM response generation with retrieved context."""

from app.config import settings


async def generate(query: str, context: list[dict]) -> str:
    """Generate a response using retrieved context chunks."""
    context_text = "\n\n".join(c.get("text", "") for c in context)

    if not settings.openai_api_key:
        return f"[Dev mode] Received: {query}"

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {
                "role": "system",
                "content": "Answer based on the provided context. If unsure, say so.",
            },
            {
                "role": "user",
                "content": f"Context:\n{context_text}\n\nQuestion: {query}",
            },
        ],
    )
    return response.choices[0].message.content or ""
