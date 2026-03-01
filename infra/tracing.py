"""
LangSmith observability layer — compatible with langsmith>=0.2.0 (tested on 0.7.x).

Uses langsmith.trace() context manager and langsmith.traceable decorator.
Tracing is a strict no-op when disabled — never raises, never crashes the app.

Environment variables
---------------------
LANGCHAIN_TRACING_V2   = true                          # master on/off switch
LANGSMITH_API_KEY      = lsv2_pt_...                   # your API key
LANGSMITH_PROJECT      = pageindex-legal-ai            # project name in UI
LANGCHAIN_ENDPOINT     = https://api.smith.langchain.com  # (optional)
"""
from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from typing import Any, Callable, Generator

# ── Bootstrap: push config into env before langsmith reads it ────────────────
from infra.config import SETTINGS

if SETTINGS.langsmith_api_key:
    os.environ.setdefault("LANGSMITH_API_KEY", SETTINGS.langsmith_api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", SETTINGS.langsmith_project)
    os.environ.setdefault("LANGCHAIN_PROJECT", SETTINGS.langsmith_project)

if SETTINGS.langsmith_tracing:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"


def _is_enabled() -> bool:
    return (
        os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        and bool(os.getenv("LANGSMITH_API_KEY"))
    )


@contextmanager
def trace_run(
    name: str,
    run_type: str = "chain",
    inputs: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """
    Context manager that wraps a block in a LangSmith run.

    Usage:
        with trace_run("risk-detection", run_type="tool", inputs={"q": q}) as run:
            result = agent.analyze(hits)
            run["outputs"] = {"count": len(result)}
    """
    run_ctx: dict[str, Any] = {}

    if not _is_enabled():
        yield run_ctx
        return

    try:
        import langsmith  # type: ignore
        with langsmith.trace(
            name=name,
            run_type=run_type,
            inputs=inputs or {},
            tags=(tags or []) + ["pageindex-legal-ai"],
            metadata=metadata or {},
            project_name=SETTINGS.langsmith_project,
        ) as run_tree:
            yield run_ctx
            # Push outputs back into the run tree after the block
            if run_ctx.get("outputs"):
                run_tree.outputs = run_ctx["outputs"]
    except Exception:
        # Never let tracing crash the main flow
        yield run_ctx


def traceable(
    name: str | None = None,
    run_type: str = "chain",
    tags: list[str] | None = None,
) -> Callable:
    """
    Decorator that wraps a function in a LangSmith run.

    Usage:
        @traceable(name="gemini-generate", run_type="llm")
        def generate(self, prompt: str, model: str | None = None) -> str:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _is_enabled():
                return fn(*args, **kwargs)
            try:
                import langsmith  # type: ignore
                run_name = name or fn.__qualname__

                # Build safe inputs (skip self, skip large strings)
                safe_inputs: dict[str, Any] = {}
                for i, a in enumerate(args[1:], 1):
                    if isinstance(a, str) and len(a) > 2000:
                        safe_inputs[f"arg_{i}"] = a[:500] + "…"
                    elif isinstance(a, (str, int, float, bool)):
                        safe_inputs[f"arg_{i}"] = a
                for k, v in kwargs.items():
                    if isinstance(v, str) and len(v) > 2000:
                        safe_inputs[k] = v[:500] + "…"
                    elif isinstance(v, (str, int, float, bool)):
                        safe_inputs[k] = v

                with langsmith.trace(
                    name=run_name,
                    run_type=run_type,
                    inputs=safe_inputs,
                    tags=(tags or []) + ["pageindex-legal-ai"],
                    project_name=SETTINGS.langsmith_project,
                ) as run_tree:
                    result = fn(*args, **kwargs)
                    if isinstance(result, str):
                        run_tree.outputs = {"result": result[:2000] + ("…" if len(result) > 2000 else "")}
                    return result
            except Exception:
                return fn(*args, **kwargs)
        return wrapper
    return decorator


def trace_llm_call(
    prompt: str,
    response: str,
    model: str,
    provider: str = "gemini",
    latency_ms: float = 0.0,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log a completed LLM call as a LangSmith run."""
    if not _is_enabled():
        return
    try:
        import langsmith  # type: ignore
        with langsmith.trace(
            name=f"llm/{provider}/{model}",
            run_type="llm",
            inputs={"prompt": prompt[:3000]},
            tags=["pageindex-legal-ai", provider, model],
            metadata={"latency_ms": latency_ms, **(extra or {})},
            project_name=SETTINGS.langsmith_project,
        ) as run_tree:
            run_tree.outputs = {"response": response[:3000]}
    except Exception:
        pass


def trace_retrieval(
    question: str,
    mode: str,
    hits: list[Any],
    document_id: str,
) -> None:
    """Log a retrieval step as a LangSmith run."""
    if not _is_enabled():
        return
    try:
        import langsmith  # type: ignore
        with langsmith.trace(
            name=f"retrieval/{mode}",
            run_type="retriever",
            inputs={"question": question, "document_id": document_id, "mode": mode},
            tags=["pageindex-legal-ai", "retrieval", mode],
            project_name=SETTINGS.langsmith_project,
        ) as run_tree:
            run_tree.outputs = {
                "hit_count": len(hits),
                "top_scores": [round(float(h.score), 4) for h in hits[:5]],
                "top_paths": [h.heading_path for h in hits[:5]],
            }
    except Exception:
        pass
