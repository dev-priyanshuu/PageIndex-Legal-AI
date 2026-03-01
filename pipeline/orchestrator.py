from __future__ import annotations

from infra.config import SETTINGS
from agents.understanding import LegalUnderstandingAgent
from agents.risk_detection import RiskDetectionAgent
from agents.party_analysis import PartyAnalysisAgent
from agents.validation import ValidationAgent
from agents.verification import VerificationAgent
from agents.drafting import DraftingAgent
from agents.explainability import ExplainabilityAgent
from agents.memory import MemoryAgent
from pipeline.graph_flow import GraphExecutor
from infra.llm import get_llm_client
from infra.persistence import get_repository
from core.retrieval import RetrievalHit, TreeRetriever, VectorRetriever
from knowledge.jurisdiction import JurisdictionEngine
from knowledge.risk_simulation import RiskSimulationAgent, _extract_purchase_price
from api.schemas import AskResponse, Evidence, JurisdictionInfo, PartyAnalysis
from infra.store import SESSIONS, SessionMemory


class LegalOrchestrator:
    def __init__(self) -> None:
        self.repo = get_repository()
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
        self.memory = MemoryAgent()
        self.graph = GraphExecutor()

    def _answer_from_hits(self, hits: list[RetrievalHit]) -> str:
        if not hits:
            return "I could not find enough legal evidence in the document."
        top = hits[0]
        summary = top.node.content.strip()[:420] or "Relevant clause heading matched but clause body is empty."
        return f"Most relevant clause: {top.heading_path}. Evidence: {summary}"

    def ask(
        self,
        document_id: str,
        question: str,
        retriever_mode: str,
        execution_mode: str,
        top_k: int,
        session_id: str,
        llm_provider: str,
        llm_model: str | None,
    ) -> AskResponse:
        doc = self.repo.get(document_id)
        if doc is None:
            raise ValueError(f"Document not found: {document_id}")

        clause_tensions = []
        risk_score = 0.0
        risk_scenarios = []
        portfolio_risk: dict = {}
        jurisdiction_info = None

        if execution_mode == "graph":
            result = self.graph.run(
                doc=doc,
                question=question,
                retriever_mode=retriever_mode,
                top_k=top_k,
                llm_provider=llm_provider,
                llm_model=llm_model,
            )
            answer = result.answer
            risks = result.risks
            suggestions = result.suggestions
            party_analysis = result.party_analysis
            clause_tensions = result.clause_tensions
            risk_score = result.risk_score
            risk_scenarios = result.risk_scenarios
            portfolio_risk = result.portfolio_risk
            jurisdiction_info = result.jurisdiction_info
            trace = result.trace
            confidence = result.confidence
            hits = result.hits
        else:
            legal_ctx = self.understanding.analyze(doc.source_text)
            section_titles = legal_ctx.section_titles or [
                n.title for n in doc.tree.nodes.values()
            ]
            if retriever_mode == "tree":
                hits = self.tree.retrieve(doc.tree, question, top_k=top_k)
            else:
                hits = self.vector.retrieve(doc.tree, question, top_k=top_k)
            answer = self._answer_from_hits(hits)
            llm = get_llm_client(llm_provider)
            if hits:
                answer = f"{answer}\n{llm.generate(question, model=llm_model)}"
            raw_risks = self.risk.analyze(hits, full_text=doc.source_text)
            risks = self.verification.verify_risks(raw_risks, section_titles, doc.source_text)
            party_analysis = self.party.analyze(hits, full_text=doc.source_text)
            contradictions = self.validation.validate(hits, full_text=doc.source_text)
            clause_tensions, risk_score = self.validation.validate_with_graph(doc.source_text)
            suggestions = self.drafting.suggest(risks)
            metadata_jurisdiction = doc.metadata.get("jurisdiction", "")
            jur_analysis = self.jurisdiction.analyze(doc.source_text, metadata_jurisdiction)
            purchase_price = _extract_purchase_price(doc.source_text)
            risk_scenarios = self.simulation.simulate(risks, doc.source_text, purchase_price)
            portfolio_risk = self.simulation.compute_portfolio_risk(
                risk_scenarios, purchase_price or 100_000.0
            )
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
                question, retriever_mode, hits,
                total_sections=total_sections,
                verified_count=len(risks),
                contradiction_count=len(contradictions),
                tension_count=len(clause_tensions),
                risk_score=risk_score,
                present_clause_count=len(legal_ctx.present_clauses),
            )
            trace.extend(contradictions)
            confidence = 0.85 if retriever_mode == "tree" and hits else 0.72 if hits else 0.25

        session = SESSIONS.setdefault(session_id, SessionMemory(session_id=session_id))
        self.memory.update(session.questions, session.answers, question, answer)

        evidences = [
            Evidence(
                node_id=h.node.node_id,
                heading_path=h.heading_path,
                excerpt=h.node.content[:240],
                score=round(float(h.score), 4),
            )
            for h in hits
        ]
        llm_model_used = llm_model or (SETTINGS.gemini_model if llm_provider == "gemini" else "default")
        return AskResponse(
            answer=answer,
            confidence=confidence,
            reasoning_trace=trace,
            evidences=evidences,
            risks=risks,
            suggestions=suggestions,
            party_analysis=party_analysis,
            clause_tensions=clause_tensions,
            risk_score=risk_score,
            risk_scenarios=[s.__dict__ for s in risk_scenarios],
            portfolio_risk=portfolio_risk,
            jurisdiction_info=jurisdiction_info,
            execution_mode=execution_mode,
            llm_provider=llm_provider,
            llm_model_used=llm_model_used,
        )
