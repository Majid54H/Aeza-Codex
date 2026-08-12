"""Document loaders for various file formats."""

from pathlib import Path


def load_text(content: bytes, filename: str) -> str:
    """Load plain text or decode bytes from uploaded file."""
    suffix = Path(filename).suffix.lower()

    if suffix in (".txt", ".md"):
        return content.decode("utf-8", errors="replace")

    # Extend with PDF, DOCX loaders as needed
    return content.decode("utf-8", errors="replace")
