from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from infra.audit import AUDIT_LOG, log_event
from infra.benchmark import build_markdown_report, run_benchmark
from infra.config import SETTINGS
from core.ingestion import extract_text_from_pdf_bytes, extract_text_from_text_bytes
from pipeline.orchestrator import LegalOrchestrator
from core.pageindex_adapter import generate_tree_with_pageindex, is_pageindex_available
from core.pageindex_engine import build_tree_from_markdown
from infra.persistence import get_repository
from infra.sample_docs import SAMPLE_SPA_V1
from api.schemas import (
    AskRequest,
    AskResponse,
    BenchmarkRequest,
    BenchmarkResponse,
    DocumentTreeResponse,
    EvaluationReportResponse,
    IngestRequest,
    IngestPdfResponse,
    IngestResponse,
    TreeGenMode,
    TreeNodeResponse,
)
from infra.store import StoredDocument

app = FastAPI(title="Legal Agentic PageIndex RAG", version="1.0.0")
orchestrator = LegalOrchestrator()
repo = get_repository()

# ── Bootstrap LangSmith tracing on startup ────────────────────────────────────
from infra import tracing as _tracing  # noqa: E402, F401  — side-effect import


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "pageindex_available": str(is_pageindex_available()),
        "tree_generation_mode": SETTINGS.tree_generation_mode,
    }


def _resolve_tree_mode(requested: TreeGenMode) -> str:
    if requested == "pageindex":
        if not is_pageindex_available():
            raise HTTPException(
                status_code=400,
                detail="PageIndex mode requested but GEMINI_API_KEY is not set or vendor/PageIndex is missing.",
            )
        return "pageindex"
    if requested == "local":
        return "local"
    return "pageindex" if is_pageindex_available() else "local"


@app.post("/documents/ingest", response_model=IngestResponse)
def ingest_document(req: IngestRequest) -> IngestResponse:
    tree = build_tree_from_markdown(req.document_id, req.text, req.metadata)
    repo.save(
        StoredDocument(
            document_id=req.document_id,
            title=req.title,
            metadata=req.metadata,
            source_text=req.text,
            tree=tree,
        )
    )
    log_event("document_ingested", actor="api_user", document_id=req.document_id, details={"title": req.title})
    return IngestResponse(
        document_id=req.document_id,
        node_count=len(tree.nodes),
        message="Document ingested and indexed into legal tree.",
    )


@app.post("/documents/ingest_file", response_model=IngestPdfResponse)
async def ingest_file(
    document_id: str = Form(...),
    title: str = Form(...),
    jurisdiction: str = Form(default="unknown"),
    deal_type: str = Form(default="unknown"),
    tree_mode: str = Form(default="auto"),
    file: UploadFile = File(...),
) -> IngestPdfResponse:
    content = await file.read()
    filename = (file.filename or "").lower()

    resolved_mode = _resolve_tree_mode(tree_mode)  # type: ignore[arg-type]
    metadata = {
        "jurisdiction": jurisdiction,
        "deal_type": deal_type,
        "source_file": file.filename or "unknown",
        "tree_generation_mode": resolved_mode,
    }

    from infra.tracing import trace_run

    with trace_run(
        "document-ingest",
        run_type="chain",
        inputs={
            "document_id": document_id,
            "filename": file.filename or "unknown",
            "tree_mode": resolved_mode,
        },
        tags=["ingest"],
    ) as ingest_run:
        if resolved_mode == "pageindex" and filename.endswith(".pdf"):
            tree = generate_tree_with_pageindex(
                pdf_bytes=content,
                document_id=document_id,
                model=SETTINGS.pageindex_model,
            )
            extracted_chars = sum(len(n.content) for n in tree.nodes.values())
            source_text = "\n".join(f"# {n.title}\n{n.content}" for n in tree.nodes.values() if n.content)
        else:
            if filename.endswith(".pdf"):
                extracted = extract_text_from_pdf_bytes(content)
            else:
                extracted = extract_text_from_text_bytes(content)
            source_text = extracted.text
            extracted_chars = extracted.char_count
            tree = build_tree_from_markdown(document_id, source_text, metadata)
            resolved_mode = "local"

        ingest_run["outputs"] = {
            "node_count": len(tree.nodes),
            "extracted_chars": extracted_chars,
            "tree_mode": resolved_mode,
        }

    repo.save(
        StoredDocument(
            document_id=document_id,
            title=title,
            metadata=metadata,
            source_text=source_text,
            tree=tree,
        )
    )
    log_event(
        "document_ingested_file",
        actor="api_user",
        document_id=document_id,
        details={
            "filename": file.filename or "unknown",
            "tree_mode": resolved_mode,
            "node_count": str(len(tree.nodes)),
        },
    )
    return IngestPdfResponse(
        document_id=document_id,
        extracted_chars=extracted_chars,
        node_count=len(tree.nodes),
        tree_generation_mode=resolved_mode,
        message=f"File ingested using {resolved_mode} tree generation. {len(tree.nodes)} nodes indexed.",
    )


@app.post("/documents/ingest_sample", response_model=IngestResponse)
def ingest_sample() -> IngestResponse:
    req = IngestRequest(
        document_id="sample-spa-v1",
        title="Sample SPA v1",
        text=SAMPLE_SPA_V1,
        metadata={"jurisdiction": "India", "deal_type": "M&A"},
    )
    return ingest_document(req)


@app.get("/documents/tree", response_model=DocumentTreeResponse)
def get_document_tree(document_id: str) -> DocumentTreeResponse:
    """Return the full hierarchical tree for a document, ready for frontend visualisation."""
    doc = repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    tree = doc.tree

    def _heading_path(node_id: str) -> str:
        path: list[str] = []
        current_id: str | None = node_id
        while current_id is not None:
            node = tree.nodes.get(current_id)
            if node is None:
                break
            path.append(node.title)
            current_id = node.parent_id
        return " > ".join(reversed(path))

    def _max_depth(node_id: str, depth: int = 0) -> int:
        children = tree.children.get(node_id, [])
        if not children:
            return depth
        return max(_max_depth(c, depth + 1) for c in children)

    max_depth = max((_max_depth(r) for r in tree.root_ids), default=0)

    nodes_out: dict[str, TreeNodeResponse] = {}
    for node_id, node in tree.nodes.items():
        nodes_out[node_id] = TreeNodeResponse(
            node_id=node_id,
            title=node.title,
            level=node.level,
            parent_id=node.parent_id,
            content_preview=node.content[:300] if node.content else "",
            content_length=len(node.content),
            children=tree.children.get(node_id, []),
            heading_path=_heading_path(node_id),
            metadata=node.metadata,
        )

    return DocumentTreeResponse(
        document_id=document_id,
        title=doc.title,
        node_count=len(tree.nodes),
        max_depth=max_depth,
        root_ids=tree.root_ids,
        nodes=nodes_out,
        metadata=doc.metadata,
    )


@app.post("/qa/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    try:
        response = orchestrator.ask(
            document_id=req.document_id,
            question=req.question,
            retriever_mode=req.retriever_mode,
            execution_mode=req.execution_mode,
            top_k=req.top_k,
            session_id=req.session_id,
            llm_provider=req.llm_provider,
            llm_model=req.llm_model,
        )
        log_event(
            "question_answered",
            actor=req.session_id,
            document_id=req.document_id,
            details={
                "retriever_mode": req.retriever_mode,
                "execution_mode": req.execution_mode,
                "llm_provider": req.llm_provider,
                "llm_model": req.llm_model or "",
            },
        )
        return response
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/benchmark/run", response_model=BenchmarkResponse)
def benchmark(req: BenchmarkRequest) -> BenchmarkResponse:
    try:
        tree_metrics, vector_metrics, coverage = run_benchmark(document_id=req.document_id, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    tree_total = tree_metrics.recall_at_k + tree_metrics.citation_path_accuracy + tree_metrics.risk_detection_accuracy
    vector_total = (
        vector_metrics.recall_at_k + vector_metrics.citation_path_accuracy + vector_metrics.risk_detection_accuracy
    )
    winner = "tree" if tree_total >= vector_total else "vector"
    if coverage == 0:
        summary = (
            "Could not generate eval cases for this document — tree may be empty or unstructured. "
            "Try re-ingesting with a cleaner PDF."
        )
    elif coverage == 1.0 and tree_metrics.recall_at_k == 0 and vector_metrics.recall_at_k == 0:
        summary = (
            f"{winner.upper()} retriever selected. Eval cases were auto-generated from this document's tree. "
            "Re-ingest the document if tree paths look noisy."
        )
    else:
        summary = (
            f"{winner.upper()} retriever performs better. "
            "Tree mode wins when legal heading hierarchy and clause dependencies matter."
        )
    return BenchmarkResponse(
        document_id=req.document_id,
        tree=tree_metrics,
        vector=vector_metrics,
        eval_case_coverage=coverage,
        winner=winner,
        summary=summary,
    )


@app.post("/benchmark/report", response_model=EvaluationReportResponse)
def benchmark_report(req: BenchmarkRequest) -> EvaluationReportResponse:
    try:
        report = build_markdown_report(document_id=req.document_id, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EvaluationReportResponse(document_id=req.document_id, markdown_report=report)


@app.get("/audit/events")
def get_audit_events() -> dict[str, list[dict[str, str]]]:
    return {
        "events": [
            {
                "timestamp": e.timestamp,
                "event_type": e.event_type,
                "actor": e.actor,
                "document_id": e.document_id or "",
                "details": str(e.details),
            }
            for e in AUDIT_LOG
        ]
    }


@app.get("/system/info")
def system_info() -> dict[str, str | bool]:
    return {
        "pageindex_available": is_pageindex_available(),
        "tree_generation_mode": SETTINGS.tree_generation_mode,
        "pageindex_model": SETTINGS.pageindex_model,
        "llm_provider": SETTINGS.llm_default_provider,
        "gemini_model": SETTINGS.gemini_model,
    }
