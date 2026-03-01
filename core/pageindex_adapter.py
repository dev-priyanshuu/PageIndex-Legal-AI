"""
Adapter that bridges the real VectifyAI/PageIndex engine to our LegalTree format.

Supports two tree-generation modes:
  - "pageindex" : Uses the real PageIndex library (LLM-powered via Gemini)
  - "local"     : Our regex/font-based fallback (no LLM needed)
"""
from __future__ import annotations

import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from core.pageindex_engine import LegalNode, LegalTree

VENDOR_DIR = os.path.join(os.path.dirname(__file__), "..", "vendor", "PageIndex")


def _ensure_vendor_path() -> None:
    if VENDOR_DIR not in sys.path:
        sys.path.insert(0, VENDOR_DIR)


def _flatten_pageindex_tree(
    nodes: list[dict[str, Any]],
    parent_id: str | None,
    level: int,
    doc_id: str,
    out_nodes: dict[str, LegalNode],
    out_children: dict[str, list[str]],
    out_root_ids: list[str],
) -> None:
    """Recursively convert PageIndex nested dicts → flat LegalNode maps."""
    for node in nodes:
        node_id = f"{doc_id}-pi{node.get('node_id', '0000')}"
        title = node.get("title", "Untitled")
        summary = node.get("summary", "") or node.get("prefix_summary", "")
        text = node.get("text", "")
        content = summary if summary else text

        legal_node = LegalNode(
            node_id=node_id,
            title=title,
            content=content,
            level=level,
            parent_id=parent_id,
            metadata={
                "start_index": str(node.get("start_index", "")),
                "end_index": str(node.get("end_index", "")),
                "source": "pageindex",
            },
        )
        out_nodes[node_id] = legal_node
        out_children[node_id] = []

        if parent_id:
            out_children[parent_id].append(node_id)
        else:
            out_root_ids.append(node_id)

        children = node.get("nodes", [])
        if children:
            _flatten_pageindex_tree(
                children, node_id, level + 1, doc_id, out_nodes, out_children, out_root_ids,
            )


def generate_tree_with_pageindex(
    pdf_bytes: bytes,
    document_id: str,
    model: str = "models/gemini-2.5-flash",
    add_summary: bool = True,
    add_text: bool = True,
) -> LegalTree:
    """
    Run the real PageIndex engine on raw PDF bytes and return our LegalTree.
    Requires GEMINI_API_KEY in the environment.
    """
    _ensure_vendor_path()
    from pageindex import page_index_main  # type: ignore
    from pageindex.utils import ConfigLoader  # type: ignore

    config_loader = ConfigLoader()
    opt = config_loader.load({
        "model": model,
        "if_add_node_id": "yes",
        "if_add_node_summary": "yes" if add_summary else "no",
        "if_add_node_text": "yes" if add_text else "no",
        "if_add_doc_description": "no",
    })

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    def _run_in_thread() -> dict[str, Any]:
        """Run page_index_main in a fresh thread so asyncio.run() gets its own event loop."""
        return page_index_main(tmp_path, opt)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(_run_in_thread).result()
    finally:
        os.unlink(tmp_path)

    structure = result.get("structure", [])
    if not isinstance(structure, list):
        structure = [structure]

    nodes: dict[str, LegalNode] = {}
    children: dict[str, list[str]] = {}
    root_ids: list[str] = []
    _flatten_pageindex_tree(structure, None, 1, document_id, nodes, children, root_ids)

    return LegalTree(document_id=document_id, nodes=nodes, children=children, root_ids=root_ids)


def is_pageindex_available() -> bool:
    """Check if real PageIndex can be used (vendor exists + Gemini key set)."""
    has_vendor = os.path.isdir(os.path.join(VENDOR_DIR, "pageindex"))
    has_key = bool(os.environ.get("GEMINI_API_KEY"))
    return has_vendor and has_key
