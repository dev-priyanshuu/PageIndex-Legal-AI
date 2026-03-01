from __future__ import annotations

import time
from dataclasses import dataclass, field

from agents.understanding import LegalUnderstandingAgent
from agents.risk_detection import RiskDetectionAgent
from agents.party_analysis import PartyAnalysisAgent
from agents.validation import ValidationAgent
from agents.verification import VerificationAgent
from agents.drafting import DraftingAgent
from agents.explainability import ExplainabilityAgent
from knowledge.jurisdiction import JurisdictionEngine
from knowledge.risk_simulation import RiskSimulationAgent, _extract_purchase_price
from infra.llm import get_llm_client
from core.pageindex_engine import LegalTree
from core.retrieval import RetrievalHit, TreeRetriever, VectorRetriever
from api.schemas import (
    ClauseTension,
    JurisdictionInfo,
    NegotiationPoint,
    PartyAnalysis,
    RiskItem,
    RiskScenario,
)
from infra.store import StoredDocument

MAX_FULL_TEXT_CHARS = 120_000


@dataclass
class GraphResult:
    answer: str
    confidence: float
    trace: list[str]
    hits: list[RetrievalHit]
    risks: list[RiskItem]
    suggestions: list[NegotiationPoint]
    clause_tensions: list[ClauseTension] = field(default_factory=list)
    risk_score: float = 0.0
    risk_scenarios: list[RiskScenario] = field(default_factory=list)
    portfolio_risk: dict = field(default_factory=dict)
    jurisdiction_info: JurisdictionInfo | None = None
    party_analysis: PartyAnalysis = field(default_factory=lambda: PartyAnalysis(
        advantage="unclear", buyer_protections=[], seller_protections=[], summary="N/A",
    ))


def _build_section_outline(tree: LegalTree) -> str:
    lines: list[str] = []
    counter = 0

    def _walk(node_id: str, depth: int) -> None:
        nonlocal counter
        node = tree.nodes[node_id]
        counter += 1
        indent = "  " * depth
        lines.append(f"{indent}{counter}. {node.title}")
        for child_id in tree.children.get(node_id, []):
            _walk(child_id, depth + 1)

    for root_id in tree.root_ids:
        _walk(root_id, 0)
    return "\n".join(lines)


def _build_expanded_evidence(hits: list[RetrievalHit], tree: LegalTree, top_k: int) -> str:
    seen_ids: set[str] = set()
    blocks: list[str] = []

    for h in hits[:top_k]:
        node = h.node
        if node.node_id in seen_ids:
            continue
        seen_ids.add(node.node_id)

        parent_ctx = ""
        if node.parent_id and node.parent_id in tree.nodes:
            parent = tree.nodes[node.parent_id]
            parent_ctx = f"  Parent section: {parent.title}\n"
            siblings = tree.children.get(node.parent_id, [])
            sibling_titles = [tree.nodes[s].title for s in siblings if s != node.node_id and s in tree.nodes]
            if sibling_titles:
                parent_ctx += f"  Sibling sections: {', '.join(sibling_titles)}\n"

        blocks.append(
            f"[Section: {h.heading_path}] (score: {h.score:.3f})\n"
            f"{parent_ctx}"
            f"{node.content[:1200]}"
        )

    return "\n\n---\n\n".join(blocks)


class GraphExecutor:
    """
    LangGraph-ready orchestration shim.
    Runs the full agent pipeline: retrieve → understand → risk → party → draft → explain.
    """

    def __init__(self) -> None:
        self.tree = TreeRetriever()
        self.vector = VectorRetriever()
        self.understanding = LegalUnderstandingAgent()
        self.risk = RiskDetectionAgent()
        self.party = PartyAnalysisAgent()
        self.validation = ValidationAgent()
        self.verification = VerificationAgent()
        self.drafting = DraftingAgent()
        self.explain = ExplainabilityAgent()
        self.jurisdiction = JurisdictionEngine()
        self.simulation = RiskSimulationAgent()

    def run(
        self,
        doc: StoredDocument,
        question: str,
        retriever_mode: str,
        top_k: int,
        llm_provider: str,
        llm_model: str | None,
    ) -> GraphResult:
        from infra.tracing import trace_retrieval, trace_run

        # ── Step 1: Retrieval ─────────────────────────────────────────────────
        t0 = time.time()
        hits = (
            self.tree.retrieve(doc.tree, question, top_k=top_k)
            if retriever_mode == "tree"
            else self.vector.retrieve(doc.tree, question, top_k=top_k)
        )
        trace_retrieval(
            question=question,
            mode=retriever_mode,
            hits=hits,
            document_id=doc.document_id,
        )

        llm = get_llm_client(llm_provider)

        # ── Step 2: Jurisdiction detection ───────────────────────────────────
        metadata_jurisdiction = doc.metadata.get("jurisdiction", "")
        with trace_run(
            "jurisdiction-detection",
            run_type="tool",
            inputs={"document_id": doc.document_id, "metadata_jurisdiction": metadata_jurisdiction},
        ) as jur_run:
            jur_analysis = self.jurisdiction.analyze(doc.source_text, metadata_jurisdiction)
            jur_run["outputs"] = {
                "detected": jur_analysis.detected_jurisdiction,
                "jurisdiction_risks": len(jur_analysis.jurisdiction_risks),
            }

        jur_block = (
            f"GOVERNING JURISDICTION: {jur_analysis.detected_jurisdiction}\n"
            + "\n".join(f"  - {n}" for n in jur_analysis.jurisdiction_notes[:4])
        )

        section_outline = _build_section_outline(doc.tree)
        evidence_block = _build_expanded_evidence(hits, doc.tree, top_k)

        full_text = doc.source_text
        if len(full_text) > MAX_FULL_TEXT_CHARS:
            full_text = full_text[:MAX_FULL_TEXT_CHARS] + "\n\n[... document truncated ...]"

        prompt = (
            "You are a senior legal counsel with 20+ years of M&A and commercial "
            "contract experience. You have been given the FULL DOCUMENT TEXT and a "
            "list of PRIORITY SECTIONS identified by the retrieval system.\n\n"
            "Your task: Answer the question using the full document. The priority "
            "sections indicate where the retrieval system thinks the most relevant "
            "clauses are, but you MUST also review the full document to find any "
            "additional relevant provisions. Do NOT claim a clause is 'missing' "
            "unless you have verified it does not exist anywhere in the full text.\n\n"
            f"QUESTION: {question}\n\n"
            f"{jur_block}\n\n"
            f"DOCUMENT SECTION OUTLINE ({len(doc.tree.nodes)} sections):\n"
            f"{section_outline}\n\n"
            f"PRIORITY SECTIONS (highest retrieval scores):\n{evidence_block}\n\n"
            f"FULL DOCUMENT TEXT:\n{full_text}\n\n"
            "RESPONSE FORMAT:\n\n"
            "## Key Legal Risks\n"
            "For each risk, provide:\n"
            "- Risk name (Severity: Critical/High/Medium/Low for Buyer/Seller)\n"
            "- Exact section number and clause reference\n"
            "- Quote the specific problematic language\n"
            "- Explain why it is a risk and for which party\n"
            "- Note any jurisdiction-specific implications\n\n"
            "## Buyer vs Seller Analysis\n"
            "- Count and list protections for each party with section references\n"
            "- State which party is more protected and why\n\n"
            "## Recommended Amendments\n"
            "For each amendment:\n"
            "- Current clause (with section number)\n"
            "- Proposed amendment language\n"
            "- Fallback position if the other party rejects\n"
            "- Jurisdiction-specific requirement if applicable\n\n"
            "## Contradictions & Gaps\n"
            "- Cross-reference clauses that conflict with each other\n"
            "- List genuinely missing provisions (verify against full text first)\n"
            "- Flag any provisions required by governing law that are absent\n\n"
            "CRITICAL RULES:\n"
            "1. Always cite the exact section number (e.g., Section 8.2, Section 12.5)\n"
            "2. Quote actual clause language in double quotes\n"
            "3. Do NOT claim a provision is missing if it exists in the full document\n"
            "4. Analyze clause interdependencies (e.g., how limitation of liability "
            "in Section 8 interacts with warranty in Section 6 and IP indemnity in Section 7)\n"
            f"5. Apply {jur_analysis.detected_jurisdiction} law standards throughout your analysis\n"
        )
        # ── Step 3: LLM answer (traced inside GeminiLlmClient.generate) ─────
        answer = llm.generate(prompt, model=llm_model)

        # ── Step 4: Understanding + risk agents ──────────────────────────────
        with trace_run(
            "legal-understanding",
            run_type="tool",
            inputs={"document_id": doc.document_id},
        ) as und_run:
            legal_ctx = self.understanding.analyze(doc.source_text)
            und_run["outputs"] = {
                "section_count": len(legal_ctx.section_titles),
                "present_clauses": len(legal_ctx.present_clauses),
            }

        section_titles = legal_ctx.section_titles or [
            n.title for n in doc.tree.nodes.values()
        ]

        with trace_run(
            "risk-detection",
            run_type="tool",
            inputs={"document_id": doc.document_id, "hit_count": len(hits)},
        ) as risk_run:
            raw_risks = self.risk.analyze(hits, full_text=doc.source_text)
            risk_run["outputs"] = {"raw_risk_count": len(raw_risks)}

        for jr in jur_analysis.jurisdiction_risks:
            raw_risks.append(RiskItem(
                category=jr["category"],
                severity=jr["severity"],
                description=jr["description"],
                clause_reference=jr.get("clause_reference", ""),
                affected_party=jr.get("affected_party", "both"),
            ))

        with trace_run(
            "risk-verification",
            run_type="tool",
            inputs={"raw_risk_count": len(raw_risks)},
        ) as ver_run:
            risks = self.verification.verify_risks(raw_risks, section_titles, doc.source_text)
            ver_run["outputs"] = {"verified_risk_count": len(risks)}

        sev_map = {
            adj["category"]: adj["adjusted_severity"]
            for adj in jur_analysis.severity_adjustments
        }
        adjusted_risks: list[RiskItem] = []
        for risk in risks:
            if risk.category in sev_map:
                adjusted_risks.append(RiskItem(
                    category=risk.category,
                    severity=sev_map[risk.category],
                    description=risk.description,
                    clause_reference=risk.clause_reference,
                    affected_party=risk.affected_party,
                    interacts_with=risk.interacts_with,
                ))
            else:
                adjusted_risks.append(risk)
        risks = adjusted_risks

        with trace_run(
            "party-analysis",
            run_type="tool",
            inputs={"document_id": doc.document_id},
        ) as pa_run:
            party_analysis = self.party.analyze(hits, full_text=doc.source_text)
            pa_run["outputs"] = {"advantage": party_analysis.advantage}

        with trace_run(
            "drafting-suggestions",
            run_type="tool",
            inputs={"risk_count": len(risks)},
        ) as draft_run:
            suggestions = self.drafting.suggest(risks)
            draft_run["outputs"] = {"suggestion_count": len(suggestions)}

        with trace_run(
            "validation",
            run_type="tool",
            inputs={"document_id": doc.document_id},
        ) as val_run:
            contradictions = self.validation.validate(hits, full_text=doc.source_text)
            clause_tensions, risk_score = self.validation.validate_with_graph(doc.source_text)
            val_run["outputs"] = {
                "contradiction_count": len(contradictions),
                "tension_count": len(clause_tensions),
                "risk_score": round(risk_score, 2),
            }

        with trace_run(
            "risk-simulation",
            run_type="tool",
            inputs={"risk_count": len(risks)},
        ) as sim_run:
            purchase_price = _extract_purchase_price(doc.source_text)
            risk_scenarios = self.simulation.simulate(risks, doc.source_text, purchase_price)
            portfolio_risk = self.simulation.compute_portfolio_risk(
                risk_scenarios, purchase_price or 100_000.0
            )
            sim_run["outputs"] = {
                "scenario_count": len(risk_scenarios),
                "expected_loss": portfolio_risk.get("expected_loss", 0),
                "worst_case": portfolio_risk.get("worst_case_exposure", 0),
            }

        jurisdiction_info = JurisdictionInfo(
            detected_jurisdiction=jur_analysis.detected_jurisdiction,
            profile_name=jur_analysis.profile_name,
            jurisdiction_notes=jur_analysis.jurisdiction_notes,
            severity_adjustments=jur_analysis.severity_adjustments,
            missing_mandatory_provisions=jur_analysis.missing_mandatory_provisions,
            jurisdiction_risks=list(jur_analysis.jurisdiction_risks),
            cure_period_gap=jur_analysis.cure_period_gap,
            termination_notice_gap=jur_analysis.termination_notice_gap,
        )

        total_sections = len(doc.tree.nodes)
        trace = self.explain.reasoning_trace(
            question,
            retriever_mode,
            hits,
            total_sections=total_sections,
            verified_count=len(risks),
            contradiction_count=len(contradictions),
            tension_count=len(clause_tensions),
            risk_score=risk_score,
            present_clause_count=len(legal_ctx.present_clauses),
        )
        trace.append(
            f"Jurisdiction: {jur_analysis.detected_jurisdiction} — "
            f"{len(jur_analysis.jurisdiction_risks)} jurisdiction-specific risks added"
        )
        trace.append(
            f"Risk simulation: {len(risk_scenarios)} scenarios | "
            f"Expected loss: ${portfolio_risk.get('expected_loss', 0):,.0f} | "
            f"Worst-case exposure: ${portfolio_risk.get('worst_case_exposure', 0):,.0f}"
        )
        trace.extend(contradictions)

        retrieval_coverage = len(hits) / max(total_sections, 1)
        if retriever_mode == "tree" and hits:
            confidence = min(0.80 + retrieval_coverage * 0.15, 0.95)
        elif hits:
            confidence = min(0.65 + retrieval_coverage * 0.15, 0.85)
        else:
            confidence = 0.20

        return GraphResult(
            answer=answer,
            confidence=confidence,
            trace=trace,
            hits=hits,
            risks=risks,
            suggestions=suggestions,
            clause_tensions=clause_tensions,
            risk_score=risk_score,
            risk_scenarios=risk_scenarios,
            portfolio_risk=portfolio_risk,
            jurisdiction_info=jurisdiction_info,
            party_analysis=party_analysis,
        )
