"""LLM response generation."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You are a helpful business assistant. Answer clearly and concisely."

RAG_SYSTEM_PROMPT = (
    "You are a business assistant. Answer ONLY using the provided context. "
    "Do not use outside knowledge or invent business details. "
    "If the context does not contain enough information to answer, "
    "say you do not know and suggest contacting the business directly."
)

NO_CONTEXT_REPLY = (
    "I don't have enough information in the knowledge base to answer that question. "
    "Please contact the business directly or ask about topics covered in uploaded documents."
)

FALLBACK_REPLY = (
    "Sorry, I'm unable to respond right now. Please try again in a moment."
)
MISSING_KEY_REPLY = (
    "The assistant is not configured yet. Set OPENAI_API_KEY in your environment."
)


class LLMProvider(ABC):
    """Swappable LLM provider interface."""

    @abstractmethod
    async def generate(self, messages: list[dict[str, str]]) -> str:
        ...


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate(self, messages: list[dict[str, str]]) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""


def get_llm_provider() -> LLMProvider | None:
    """Return the configured LLM provider, or None if not configured."""
    if not settings.openai_api_key:
        return None
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
    )


def _build_messages(query: str, context: list[dict] | None) -> list[dict[str, str]]:
    chunks = context or []
    if chunks:
        context_text = "\n\n".join(c.get("text", "") for c in chunks if c.get("text"))
        user_content = f"Context:\n{context_text}\n\nQuestion: {query}"
        system_content = RAG_SYSTEM_PROMPT
    else:
        user_content = query
        system_content = SYSTEM_PROMPT

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


async def generate(query: str, context: list[dict] | None = None) -> str:
    """Generate a response from the configured LLM provider."""
    provider = get_llm_provider()
    if provider is None:
        return MISSING_KEY_REPLY

    messages = _build_messages(query, context)

    try:
        reply = await provider.generate(messages)
        if not reply:
            return FALLBACK_REPLY
        return reply
    except Exception as exc:
        logger.warning("LLM generation failed: %s", exc.__class__.__name__)
        return FALLBACK_REPLY
