"""Document and web page loaders."""

import io
import re
from pathlib import Path

from app.config import settings

_STRIP_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside", "form")
_USER_AGENT = "AezaCodex/1.0 (+https://github.com/Majid54H/Aeza-Codex)"


def normalize_text(text: str) -> str:
    """Clean and normalize extracted text."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _load_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _load_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _load_docx(content: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def load_text(content: bytes, filename: str) -> str:
    """Extract and normalize text from supported document formats."""
    suffix = Path(filename).suffix.lower()

    if suffix == ".txt":
        raw = _load_txt(content)
    elif suffix == ".pdf":
        raw = _load_pdf(content)
    elif suffix == ".docx":
        raw = _load_docx(content)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    text = normalize_text(raw)
    if not text:
        raise ValueError("No extractable text found in document")

    return text


def _extract_html_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    return root.get_text(separator="\n", strip=True)


async def load_web_page(url: str) -> str:
    """Fetch a single HTML page and extract cleaned visible text."""
    import httpx

    timeout = httpx.Timeout(settings.web_fetch_timeout_seconds)
    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ValueError("Timed out while fetching the page") from exc
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"Page returned HTTP {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise ValueError("Could not fetch the page") from exc

    content_type = (response.headers.get("content-type") or "").lower()
    if "html" not in content_type and "text/plain" not in content_type:
        raise ValueError("URL did not return an HTML page")

    if not response.text.strip():
        raise ValueError("Page was empty")

    if "text/plain" in content_type:
        text = normalize_text(response.text)
    else:
        text = normalize_text(_extract_html_text(response.text))

    if not text:
        raise ValueError("No extractable text found on the page")

    return text
