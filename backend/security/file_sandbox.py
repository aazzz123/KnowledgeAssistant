from pathlib import Path

from config import FILE_SANDBOX_ROOT


SUPPORTED_DOCUMENT_SUFFIXES = {".pdf", ".txt", ".md"}


def resolve_sandbox_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(FILE_SANDBOX_ROOT)
    except ValueError as exc:
        raise ValueError(
            f"Document access denied outside sandbox: {resolved}. "
            f"Allowed root: {FILE_SANDBOX_ROOT}"
        ) from exc

    if resolved.suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES:
        raise ValueError(f"Unsupported document type: {resolved.suffix}")
    return resolved
