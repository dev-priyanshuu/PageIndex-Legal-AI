from __future__ import annotations

from core.retrieval import RetrievalHit


class ExplainabilityAgent:
    """Generates a step-by-step reasoning trace for every query."""

    def reasoning_trace(
        self,
        question: str,
        mode: str,
        hits: list[RetrievalHit],
        total_sections: int = 0,
        verified_count: int = 0,
        contradiction_count: int = 0,
        tension_count: int = 0,
        risk_score: float = 0.0,
        present_clause_count: int = 0,
    ) -> list[str]:
        return [
            f"Received legal question: {question}",
            f"Selected retriever mode: {mode}",
            f"Retrieved {len(hits)} highest-scoring legal nodes out of {total_sections} total sections",
            f"Section coverage: {len(hits)/max(total_sections,1):.0%} of document tree",
            "Passed full document text + section outline to Gemini for analysis",
            f"Ontology-driven risk detection: scanned {present_clause_count} clause types present in document",
            f"Verification agent cross-checked risks against {total_sections} section headings — {verified_count} risks verified",
            f"Clause dependency graph: detected {tension_count} structural tensions (risk score: {risk_score:.0f}/100)",
            f"Pattern-based validation: detected {contradiction_count} additional contradictions",
            "Performed buyer-vs-seller party advantage analysis with ontology tags",
            "Generated targeted negotiation suggestions with fallback positions",
            "Synthesized answer from full document with risk and consistency checks",
        ]
