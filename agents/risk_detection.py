from __future__ import annotations

import re

from knowledge.legal_ontology import (
    CLAUSE_DEPENDENCIES,
    ONTOLOGY_BY_CLAUSE,
    ClauseDependencyGraph,
    ClauseType,
)
from core.retrieval import RetrievalHit
from api.schemas import RiskItem


class RiskDetectionAgent:
    """
    Ontology-driven legal risk detector.
    Detects which clause types are present in the document first,
    then runs only the relevant checks — no false positives for absent clauses.
    """

    def __init__(self) -> None:
        self._dep_graph = ClauseDependencyGraph()

    def _find_interacting_clauses(self, clause_type: ClauseType) -> list[str]:
        related: list[str] = []
        for dep in CLAUSE_DEPENDENCIES:
            if dep.source == clause_type and dep.target in ONTOLOGY_BY_CLAUSE:
                related.append(ONTOLOGY_BY_CLAUSE[dep.target].category)
            elif dep.target == clause_type and dep.source in ONTOLOGY_BY_CLAUSE:
                related.append(ONTOLOGY_BY_CLAUSE[dep.source].category)
        return related

    def analyze(self, hits: list[RetrievalHit], full_text: str = "") -> list[RiskItem]:
        evidence = " ".join((h.heading_path + " " + h.node.content).lower() for h in hits)
        full = (evidence + " " + full_text).lower()
        risks: list[RiskItem] = []

        present = self._dep_graph.detect_present_clauses(full_text or evidence)

        if ClauseType.LIABILITY_CAP in present:
            if "purchase price" in full or "aggregate" in full or "not exceed" in full:
                risks.append(RiskItem(
                    category="Liability Cap", severity="critical", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.LIABILITY_CAP),
                    description="Seller's liability capped at Purchase Price. Buyer exposed to losses exceeding cap.",
                    clause_reference="Limitation of Liability section",
                ))
            elif "limit" not in full and "cap" not in full:
                risks.append(RiskItem(
                    category="Liability Cap", severity="critical", affected_party="both",
                    description="No clear liability limitation found — creates open-ended exposure for both parties.",
                    clause_reference="",
                ))

        if ClauseType.RISK_OF_LOSS in present or ClauseType.TITLE_OWNERSHIP in present:
            if "risk of loss" in full or ("delivery" in full and "buyer" in full):
                risks.append(RiskItem(
                    category="Risk of Loss", severity="high", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.RISK_OF_LOSS),
                    description="Buyer bears risk of loss after delivery, even if defects exist or installation incomplete.",
                    clause_reference="Title/Risk of Loss section",
                ))

        if ClauseType.WARRANTY in present:
            if re.search(r"warrant\w*.*?\b(1|one)\s*(year|yr)", full):
                risks.append(RiskItem(
                    category="Warranty Duration", severity="medium", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.WARRANTY),
                    description="Warranty period of only 1 year. Industrial products typically warrant 2-5 years.",
                    clause_reference="Warranty / Service Plan section",
                ))

        if ClauseType.WARRANTY_DISCLAIMER in present:
            risks.append(RiskItem(
                category="AS-IS Disclaimer", severity="high", affected_party="buyer",
                interacts_with=self._find_interacting_clauses(ClauseType.WARRANTY_DISCLAIMER),
                description="AS-IS disclaimer may conflict with express warranties and IP indemnity elsewhere.",
                clause_reference="Warranty disclaimer section",
            ))

        if ClauseType.TERMINATION in present:
            seller_terminate = "seller may terminate" in full or "seller can terminate" in full
            buyer_terminate = "buyer may terminate" in full or "buyer can terminate" in full
            if seller_terminate and not buyer_terminate:
                risks.append(RiskItem(
                    category="Termination Imbalance", severity="high", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.TERMINATION),
                    description="Only Seller has explicit termination rights. Buyer lacks reciprocal termination provisions.",
                    clause_reference="Termination section",
                ))
            if "cure" not in full:
                risks.append(RiskItem(
                    category="Missing Cure Period", severity="medium", affected_party="buyer",
                    description="Termination may occur without adequate cure period for the breaching party.",
                    clause_reference="Termination section",
                ))

        if ClauseType.PAYMENT in present:
            if re.search(r"(50%|half|one.half).*before.*deliver", full) or re.search(r"pay.*before.*delivery", full):
                risks.append(RiskItem(
                    category="Payment Risk", severity="high", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.PAYMENT),
                    description="Buyer pays significant portion before delivery with no escrow or performance security.",
                    clause_reference="Payment Terms section",
                ))
            elif re.search(r"within.*days.*execution", full) and "escrow" not in full:
                risks.append(RiskItem(
                    category="Payment Risk", severity="medium", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.PAYMENT),
                    description="Payment due shortly after execution without escrow or delivery-linked milestone.",
                    clause_reference="Payment Terms section",
                ))

        if ClauseType.INDEMNIFICATION in present:
            if "buyer" not in re.findall(r"indemnif\w*\s+(?:the\s+)?(\w+)", full):
                risks.append(RiskItem(
                    category="Buyer Indemnity Gap", severity="high", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.INDEMNIFICATION),
                    description="No clear indemnification of Buyer for third-party claims or product liability.",
                    clause_reference="Indemnification section",
                ))
        else:
            risks.append(RiskItem(
                category="Missing Indemnification", severity="critical", affected_party="buyer",
                interacts_with=self._find_interacting_clauses(ClauseType.INDEMNIFICATION),
                description="No indemnification clause found. Both parties lack protection against third-party claims.",
                clause_reference="",
            ))

        if ClauseType.INSURANCE in present:
            if "certificate" not in full and "proof" not in full:
                risks.append(RiskItem(
                    category="Insurance Verification", severity="medium", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.INSURANCE),
                    description="Insurance required but no mandatory certificate or proof of coverage provision.",
                    clause_reference="Insurance section",
                ))
        else:
            risks.append(RiskItem(
                category="Missing Insurance", severity="high", affected_party="buyer",
                description="No insurance provisions found in the agreement.",
                clause_reference="",
            ))

        if ClauseType.ACCEPTANCE_TESTING not in present:
            if "deliver" in full or "install" in full:
                risks.append(RiskItem(
                    category="No Acceptance Testing", severity="medium", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.ACCEPTANCE_TESTING),
                    description="No formal acceptance testing or rejection mechanism for delivered product.",
                    clause_reference="Delivery/Installation section",
                ))

        if ClauseType.FORCE_MAJEURE in present:
            fm_matches = re.findall(r"force majeure.*?(?:\.|$)", full)
            fm_words = len(fm_matches[0].split()) if fm_matches else 0
            if fm_words > 40:
                risks.append(RiskItem(
                    category="Broad Force Majeure", severity="medium", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.FORCE_MAJEURE),
                    description="Force majeure definition is very broad — Seller can escape obligations under wide conditions.",
                    clause_reference="Force Majeure section",
                ))

        if ClauseType.IP_RIGHTS in present:
            if ClauseType.INDEMNIFICATION not in present:
                risks.append(RiskItem(
                    category="IP Indemnification Gap", severity="high", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.IP_RIGHTS),
                    description="IP infringement discussed but no clear indemnification obligation for IP claims.",
                    clause_reference="IP Rights section",
                ))

        if ClauseType.CONFIDENTIALITY in present and ClauseType.DATA_PROTECTION not in present:
            risks.append(RiskItem(
                category="Data Protection Gap", severity="low", affected_party="both",
                description="Confidentiality clause exists but lacks explicit data protection obligations.",
                clause_reference="Confidentiality section",
            ))

        if ClauseType.CONSEQUENTIAL_DAMAGES in present:
            if "indirect" in full and "consequential" in full:
                risks.append(RiskItem(
                    category="Consequential Damages Exclusion", severity="high", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.CONSEQUENTIAL_DAMAGES),
                    description="Broad exclusion of indirect/consequential damages limits Buyer's remedy for real losses.",
                    clause_reference="Limitation of Liability section",
                ))

        if ClauseType.TITLE_OWNERSHIP in present:
            if "repossess" in full or ("retain" in full and "title" in full):
                risks.append(RiskItem(
                    category="Title Retention Risk", severity="high", affected_party="buyer",
                    interacts_with=self._find_interacting_clauses(ClauseType.TITLE_OWNERSHIP),
                    description="Seller retains title until full payment. Buyer risks repossession and loss of investment.",
                    clause_reference="Title/Ownership section",
                ))

        if ClauseType.ASSIGNMENT in present:
            seller_assign = "seller may assign" in full or "seller shall have the right to assign" in full
            buyer_restrict = "buyer may not assign" in full or "buyer shall not assign" in full
            if seller_assign and buyer_restrict:
                risks.append(RiskItem(
                    category="Assignment Imbalance", severity="medium", affected_party="buyer",
                    description="Seller can freely assign but Buyer cannot — creates unequal transferability.",
                    clause_reference="Assignment section",
                ))

        return risks
