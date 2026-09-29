"""API package: HTTP boundary over the Phase 1-5 document engine (Phase 6)."""

from app.api.service import (
    ApiError,
    analyze_document_bytes,
    build_download_filename,
    generate_document_bytes,
)

__all__ = [
    "ApiError",
    "analyze_document_bytes",
    "build_download_filename",
    "generate_document_bytes",
]
