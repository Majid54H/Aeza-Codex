"""Document loaders for PDF, DOCX, and TXT."""

import io
import re
from pathlib import Path


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
