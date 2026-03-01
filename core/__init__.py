from __future__ import annotations

from core.ingestion import extract_text_from_pdf_bytes, extract_text_from_text_bytes, ExtractedDocument
from core.pageindex_engine import LegalNode, LegalTree, build_tree_from_markdown
from core.pageindex_adapter import generate_tree_with_pageindex, is_pageindex_available
from core.retrieval import RetrievalHit, TreeRetriever, VectorRetriever

__all__ = [
    "ExtractedDocument",
    "extract_text_from_pdf_bytes",
    "extract_text_from_text_bytes",
    "LegalNode",
    "LegalTree",
    "build_tree_from_markdown",
    "generate_tree_with_pageindex",
    "is_pageindex_available",
    "RetrievalHit",
    "TreeRetriever",
    "VectorRetriever",
]
