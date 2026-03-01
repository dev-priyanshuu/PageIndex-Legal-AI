from __future__ import annotations

from knowledge.legal_ontology import ClauseDependencyGraph
from core.retrieval import RetrievalHit
from api.schemas import ClauseTension, RiskItem


class ValidationAgent:
    """
    Detects contradictions and structural tensions using the clause dependency
    graph and pattern-based heuristics.
    """

    def __init__(self) -> None:
        self._dep_graph = ClauseDependencyGraph()

    def validate(self, hits: list[RetrievalHit], full_text: str = "") -> list[str]:
        evidence = " ".join(h.node.content.lower() for h in hits)
        text = (evidence + " " + full_text).lower()
        findings: list[str] = []

        if "exclusive remedy" in text and ("all remedies" in text or "cumulative" in text):
            findings.append("Contradiction: exclusive-remedy language conflicts with cumulative-remedies language.")

        if "as-is" in text and "warrant" in text and ("seller hereby" in text or "seller represent" in text):
            findings.append("Contradiction: AS-IS disclaimer may conflict with express warranties in same agreement.")

        if "shall not be liable" in text and "indemnif" in text:
            findings.append("Tension: liability exclusion coexists with indemnification obligation — indemnity may be illusory.")

        if "terminat" in text and "cure" not in text and "notice" in text:
            findings.append("Gap: termination rights exist but no cure period gives non-breaching party unilateral power.")

        if "force majeure" in text:
            fm_split = text.split("force majeure")
            if len(fm_split) > 1 and "notice" not in fm_split[1][:200]:
                findings.append("Gap: force majeure clause lacks notification requirement.")

        if "attorney" in text and "fees" in text:
            if "seller" in text and "prevailing" in text:
                atty_idx = text.find("attorney")
                preceding = text[max(0, atty_idx - 100):atty_idx]
                if "buyer" not in preceding:
                    findings.append("Imbalance: attorney's fees clause is one-sided — only Seller recovers if prevailing.")

        return findings

    def validate_with_graph(self, full_text: str) -> tuple[list[ClauseTension], float]:
        """Use the clause dependency graph to detect structural tensions."""
        present = self._dep_graph.detect_present_clauses(full_text)
        raw_tensions = self._dep_graph.detect_tensions(present)
        risk_score = self._dep_graph.get_risk_score(raw_tensions)

        tensions = [
            ClauseTension(
                tension_type=t["type"],
                source_clause=t["source"],
                target_clause=t["target"],
                description=t["description"],
                severity=t["severity"],
            )
            for t in raw_tensions
        ]
        return tensions, risk_score
