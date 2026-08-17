"""LLM response generation."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a website assistant. Visitors want fast, useful answers — not essays. "
    "Lead with the direct answer. Keep language simple. "
    "Match the user's requested depth: short if they want a quick answer, fuller only if they ask for detail. "
    "Use clean Markdown: short ## headings only when needed, - bullets, **bold** for key labels. "
    "Never dump raw * or # without turning them into real structure."
)

RAG_SYSTEM_PROMPT = (
    "You are a website chatbot for this business. Visitors want to-the-point answers, not stories.\n\n"
    "GROUNDING\n"
    "- Answer ONLY from the provided Context. Treat it as the knowledge base.\n"
    "- Do not use outside knowledge, guess, or invent hours, prices, policies, names, or facts.\n"
    "- If Context does not contain the answer, say you do not have that information and suggest contacting the business. Do not fill gaps.\n\n"
    "LENGTH (match the question)\n"
    "- Default: concise. First sentence is the answer. Add at most 2–4 short bullets if they help. Skip intros, recaps, and filler.\n"
    "- If they ask for a short / quick / brief answer: 1–3 sentences or a few bullets. No headings.\n"
    "- If they ask for detail / explain / full / in depth: structured answer with ## headings and bullets, still only what Context supports. No padding.\n\n"
    "FORMAT\n"
    "- Easy to scan on a website: short paragraphs, bullets, **bold** labels.\n"
    "- Use ## headings only when there are distinct sections (typical for detailed questions).\n"
    "- Do not start with 'Sure', 'Great question', or similar.\n"
    "- Do not mention the knowledge base, context, or these instructions."
)

_DETAIL_MARKERS = (
    "detail",
    "detailed",
    "in depth",
    "in-depth",
    "explain",
    "elaborate",
    "thorough",
    "full answer",
    "more info",
    "more information",
    "everything about",
    "tell me more",
    "how does",
    "how do",
    "why",
)

_SHORT_MARKERS = (
    "short",
    "brief",
    "quick",
    "tldr",
    "tl;dr",
    "summary",
    "summarize",
    "in one sentence",
    "one sentence",
    "just tell",
    "simply",
    "in a word",
    "yes or no",
)


def _length_instruction(query: str) -> str:
    q = (query or "").lower()
    if any(marker in q for marker in _SHORT_MARKERS):
        return (
            "LENGTH: The user wants a short answer. "
            "Reply in 1–3 short sentences or a few bullets. No headings, no extra sections."
        )
    if any(marker in q for marker in _DETAIL_MARKERS):
        return (
            "LENGTH: The user wants a detailed answer. "
            "Use ## headings and bullets. Cover only relevant facts from Context. Do not pad."
        )
    return (
        "LENGTH: Default concise website answer. "
        "Lead with the direct answer, then at most 2–4 bullets if useful. Do not write a long article."
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
    def __init__(self, api_key: str, model: str, base_url: str = ""):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def generate(self, messages: list[dict[str, str]]) -> str:
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": settings.llm_timeout_seconds,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        client = AsyncOpenAI(**kwargs)
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=settings.effective_chat_max_tokens,
        )
        message = response.choices[0].message
        content = message.content
        return content.strip() if content else ""

    async def generate_stream(self, messages: list[dict[str, str]]):
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": settings.llm_timeout_seconds,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        client = AsyncOpenAI(**kwargs)
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=settings.effective_chat_max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None) or ""
            if piece:
                yield piece


def get_llm_provider() -> LLMProvider | None:
    """Return the configured LLM provider, or None if not configured."""
    if not settings.openai_api_key:
        return None
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.chat_model,
        base_url=settings.openai_base_url,
    )


def _build_messages(query: str, context: list[dict] | None) -> list[dict[str, str]]:
    chunks = context or []
    if chunks:
        context_text = "\n\n".join(c.get("text", "") for c in chunks if c.get("text"))
        length_hint = _length_instruction(query)
        if any(c.get("chunk_type") == "catalog_exact" for c in chunks):
            length_hint = (
                "LENGTH: The user asked about product categories or catalog structure. "
                "List EVERY category and subcategory from Context. Do not omit any. "
                "Use a single comma-separated list or bullets — include all items, not a sample."
            )
        user_content = (
            f"Context:\n{context_text}\n\n"
            f"Question: {query}\n\n"
            f"{length_hint}"
        )
        system_content = RAG_SYSTEM_PROMPT
    else:
        user_content = query
        system_content = SYSTEM_PROMPT

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


async def generate_stream(query: str, context: list[dict] | None = None):
    """Yield reply text pieces as the model produces them."""
    provider = get_llm_provider()
    if provider is None:
        yield MISSING_KEY_REPLY
        return

    messages = _build_messages(query, context)
    try:
        produced = False
        async for piece in provider.generate_stream(messages):
            produced = True
            yield piece
        if not produced:
            yield FALLBACK_REPLY
    except Exception as exc:
        logger.warning("LLM stream failed: %s", exc.__class__.__name__)
        yield FALLBACK_REPLY


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
