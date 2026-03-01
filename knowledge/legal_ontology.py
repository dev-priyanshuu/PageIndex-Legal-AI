"""
Legal Ontology & Clause Dependency Graph.

Provides a structured risk taxonomy for commercial agreements and a dependency
graph that maps clause interactions (e.g., liability cap undermines indemnity).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class ClauseType(str, Enum):
    LIABILITY_CAP = "liability_cap"
    INDEMNIFICATION = "indemnification"
    WARRANTY = "warranty"
    WARRANTY_DISCLAIMER = "warranty_disclaimer"
    TERMINATION = "termination"
    PAYMENT = "payment"
    RISK_OF_LOSS = "risk_of_loss"
    IP_RIGHTS = "ip_rights"
    FORCE_MAJEURE = "force_majeure"
    INSURANCE = "insurance"
    CONFIDENTIALITY = "confidentiality"
    DATA_PROTECTION = "data_protection"
    CONSEQUENTIAL_DAMAGES = "consequential_damages"
    ACCEPTANCE_TESTING = "acceptance_testing"
    GOVERNING_LAW = "governing_law"
    ASSIGNMENT = "assignment"
    DISPUTE_RESOLUTION = "dispute_resolution"
    REPRESENTATIONS = "representations"
    TITLE_OWNERSHIP = "title_ownership"
    COMPLIANCE = "compliance"


@dataclass(frozen=True)
class RiskRule:
    """A single entry in the legal risk ontology."""
    clause_type: ClauseType
    category: str
    default_severity: str
    affected_party: str
    detection_keywords: tuple[str, ...]
    absence_keywords: tuple[str, ...] = ()
    description_template: str = ""


LEGAL_ONTOLOGY: list[RiskRule] = [
    RiskRule(
        clause_type=ClauseType.LIABILITY_CAP,
        category="Liability Cap",
        default_severity="critical",
        affected_party="buyer",
        detection_keywords=("limit", "liability", "purchase price", "aggregate", "not exceed"),
        description_template=(
            "Seller's liability capped at {cap_ref}. Buyer exposed to losses "
            "exceeding the cap in case of product failure or breach."
        ),
    ),
    RiskRule(
        clause_type=ClauseType.RISK_OF_LOSS,
        category="Risk of Loss",
        default_severity="high",
        affected_party="buyer",
        detection_keywords=("risk of loss", "risk", "delivery", "title"),
        description_template="Buyer bears risk of loss after delivery, even if defects exist.",
    ),
    RiskRule(
        clause_type=ClauseType.WARRANTY,
        category="Warranty Duration",
        default_severity="medium",
        affected_party="buyer",
        detection_keywords=("warranty", "warrant", "year", "defect"),
        description_template="Warranty period may be insufficient for product type.",
    ),
    RiskRule(
        clause_type=ClauseType.WARRANTY_DISCLAIMER,
        category="AS-IS Disclaimer",
        default_severity="high",
        affected_party="buyer",
        detection_keywords=("as-is", "as is", "disclaim", "merchantab", "fitness"),
        description_template=(
            "AS-IS disclaimer removes implied warranties. May conflict "
            "with express warranties and IP indemnity elsewhere."
        ),
    ),
    RiskRule(
        clause_type=ClauseType.TERMINATION,
        category="Termination Imbalance",
        default_severity="high",
        affected_party="buyer",
        detection_keywords=("terminat", "seller may terminate", "seller can terminate"),
        absence_keywords=("buyer may terminate", "buyer can terminate"),
        description_template="Seller has termination rights without reciprocal Buyer rights.",
    ),
    RiskRule(
        clause_type=ClauseType.PAYMENT,
        category="Payment Risk",
        default_severity="high",
        affected_party="buyer",
        detection_keywords=("pay", "before", "deliver", "execution", "50%"),
        absence_keywords=("escrow", "milestone"),
        description_template="Payment required before delivery with no security mechanism.",
    ),
    RiskRule(
        clause_type=ClauseType.INDEMNIFICATION,
        category="Indemnification Gap",
        default_severity="critical",
        affected_party="buyer",
        detection_keywords=("indemnif", "indemnity", "hold harmless"),
        description_template="Indemnification provisions may be inadequate or one-sided.",
    ),
    RiskRule(
        clause_type=ClauseType.INSURANCE,
        category="Insurance Gap",
        default_severity="medium",
        affected_party="buyer",
        detection_keywords=("insurance", "coverage", "insured", "certificate"),
        description_template="Insurance provisions may lack proof, adequacy, or continuity requirements.",
    ),
    RiskRule(
        clause_type=ClauseType.ACCEPTANCE_TESTING,
        category="No Acceptance Testing",
        default_severity="medium",
        affected_party="buyer",
        detection_keywords=("deliver", "install"),
        absence_keywords=("acceptance", "reject", "inspection"),
        description_template="No formal acceptance testing or rejection mechanism.",
    ),
    RiskRule(
        clause_type=ClauseType.FORCE_MAJEURE,
        category="Broad Force Majeure",
        default_severity="medium",
        affected_party="buyer",
        detection_keywords=("force majeure",),
        description_template="Force majeure definition may be overbroad, allowing Seller to escape obligations.",
    ),
    RiskRule(
        clause_type=ClauseType.IP_RIGHTS,
        category="IP Indemnification Gap",
        default_severity="high",
        affected_party="buyer",
        detection_keywords=("intellectual property", "infringement", "ip right"),
        description_template="IP infringement protection may be insufficient or capped.",
    ),
    RiskRule(
        clause_type=ClauseType.CONFIDENTIALITY,
        category="Data Protection Gap",
        default_severity="low",
        affected_party="both",
        detection_keywords=("confidential",),
        absence_keywords=("data protection", "privacy", "gdpr"),
        description_template="Confidentiality clause lacks explicit data protection obligations.",
    ),
    RiskRule(
        clause_type=ClauseType.CONSEQUENTIAL_DAMAGES,
        category="Consequential Damages Exclusion",
        default_severity="high",
        affected_party="buyer",
        detection_keywords=("indirect", "consequential", "special", "incidental"),
        description_template="Broad exclusion of indirect/consequential damages limits Buyer's remedy.",
    ),
    RiskRule(
        clause_type=ClauseType.TITLE_OWNERSHIP,
        category="Title Retention Risk",
        default_severity="high",
        affected_party="buyer",
        detection_keywords=("title", "pass", "retain", "repossess"),
        description_template="Seller retains title until conditions met; Buyer risks repossession.",
    ),
    RiskRule(
        clause_type=ClauseType.ASSIGNMENT,
        category="Assignment Imbalance",
        default_severity="medium",
        affected_party="buyer",
        detection_keywords=("assign", "transfer"),
        description_template="Assignment rights may be unequal between parties.",
    ),
    RiskRule(
        clause_type=ClauseType.COMPLIANCE,
        category="Compliance Burden",
        default_severity="medium",
        affected_party="buyer",
        detection_keywords=("comply", "compliance", "permit", "approval", "regulation"),
        description_template="Buyer bears significant compliance and permitting burden.",
    ),
]

ONTOLOGY_BY_CLAUSE: dict[ClauseType, RiskRule] = {r.clause_type: r for r in LEGAL_ONTOLOGY}
ONTOLOGY_BY_CATEGORY: dict[str, RiskRule] = {r.category: r for r in LEGAL_ONTOLOGY}


# ---------------------------------------------------------------------------
# Clause Dependency Graph
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClauseDependency:
    """An edge in the clause dependency graph."""
    source: ClauseType
    target: ClauseType
    relationship: str
    tension_description: str
    severity: str = "high"


CLAUSE_DEPENDENCIES: list[ClauseDependency] = [
    ClauseDependency(
        source=ClauseType.LIABILITY_CAP,
        target=ClauseType.INDEMNIFICATION,
        relationship="undermines",
        tension_description=(
            "Liability cap may undermine indemnification obligations — "
            "IP and product liability indemnity should be carved out from the aggregate cap."
        ),
        severity="critical",
    ),
    ClauseDependency(
        source=ClauseType.LIABILITY_CAP,
        target=ClauseType.WARRANTY,
        relationship="limits_remedy",
        tension_description=(
            "Liability cap limits total warranty recovery — "
            "Buyer's warranty claims cannot exceed the cap even for critical defects."
        ),
        severity="high",
    ),
    ClauseDependency(
        source=ClauseType.WARRANTY_DISCLAIMER,
        target=ClauseType.WARRANTY,
        relationship="contradicts",
        tension_description=(
            "AS-IS disclaimer may conflict with express warranties in the same agreement — "
            "unclear which prevails."
        ),
        severity="high",
    ),
    ClauseDependency(
        source=ClauseType.WARRANTY_DISCLAIMER,
        target=ClauseType.IP_RIGHTS,
        relationship="contradicts",
        tension_description=(
            "AS-IS disclaimer conflicts with IP indemnification — "
            "Seller disclaims warranties but promises to defend IP claims."
        ),
        severity="high",
    ),
    ClauseDependency(
        source=ClauseType.CONSEQUENTIAL_DAMAGES,
        target=ClauseType.INDEMNIFICATION,
        relationship="limits_remedy",
        tension_description=(
            "Consequential damages exclusion may gut the indemnity obligation — "
            "most real-world losses from IP or product liability are consequential."
        ),
        severity="critical",
    ),
    ClauseDependency(
        source=ClauseType.CONSEQUENTIAL_DAMAGES,
        target=ClauseType.WARRANTY,
        relationship="limits_remedy",
        tension_description=(
            "Consequential damages exclusion limits warranty recovery to direct damages only — "
            "Buyer cannot recover for operational disruptions caused by defects."
        ),
        severity="high",
    ),
    ClauseDependency(
        source=ClauseType.TERMINATION,
        target=ClauseType.PAYMENT,
        relationship="interacts",
        tension_description=(
            "Termination clause does not address refund of pre-paid amounts — "
            "Buyer risks losing advance payments if Seller terminates."
        ),
        severity="high",
    ),
    ClauseDependency(
        source=ClauseType.RISK_OF_LOSS,
        target=ClauseType.ACCEPTANCE_TESTING,
        relationship="gap",
        tension_description=(
            "Risk passes at delivery but no acceptance testing exists — "
            "Buyer assumes risk for products that may not meet specifications."
        ),
        severity="high",
    ),
    ClauseDependency(
        source=ClauseType.RISK_OF_LOSS,
        target=ClauseType.INSURANCE,
        relationship="requires",
        tension_description=(
            "Buyer bears risk of loss but may not have adequate insurance coverage — "
            "insurance requirements should align with risk transfer point."
        ),
        severity="medium",
    ),
    ClauseDependency(
        source=ClauseType.FORCE_MAJEURE,
        target=ClauseType.TERMINATION,
        relationship="interacts",
        tension_description=(
            "Broad force majeure without time limit allows indefinite suspension — "
            "Buyer should have right to terminate after prolonged force majeure."
        ),
        severity="medium",
    ),
    ClauseDependency(
        source=ClauseType.TITLE_OWNERSHIP,
        target=ClauseType.PAYMENT,
        relationship="interacts",
        tension_description=(
            "Title does not pass until full payment — Buyer may invest in installation/site work "
            "for a product it does not yet own and could lose to repossession."
        ),
        severity="high",
    ),
    ClauseDependency(
        source=ClauseType.IP_RIGHTS,
        target=ClauseType.LIABILITY_CAP,
        relationship="constrained_by",
        tension_description=(
            "IP indemnification is subject to the general liability cap — "
            "IP claims could easily exceed the cap, leaving Buyer exposed."
        ),
        severity="critical",
    ),
]


class ClauseDependencyGraph:
    """
    Analyzes clause interactions to find tensions, contradictions,
    and gaps in a legal agreement.
    """

    def __init__(self) -> None:
        self._edges = CLAUSE_DEPENDENCIES
        self._adj: dict[ClauseType, list[ClauseDependency]] = {}
        for dep in self._edges:
            self._adj.setdefault(dep.source, []).append(dep)
            self._adj.setdefault(dep.target, [])

    @property
    def all_clause_types(self) -> set[ClauseType]:
        types: set[ClauseType] = set()
        for dep in self._edges:
            types.add(dep.source)
            types.add(dep.target)
        return types

    def neighbors(self, clause: ClauseType) -> list[ClauseDependency]:
        return self._adj.get(clause, [])

    def detect_tensions(
        self,
        present_clauses: set[ClauseType],
    ) -> list[dict[str, str]]:
        """
        Given the set of clause types present in the document,
        find all dependency-based tensions.
        """
        tensions: list[dict[str, str]] = []

        for dep in self._edges:
            source_present = dep.source in present_clauses
            target_present = dep.target in present_clauses

            if dep.relationship == "undermines" and source_present and target_present:
                tensions.append({
                    "type": "undermines",
                    "source": dep.source.value,
                    "target": dep.target.value,
                    "description": dep.tension_description,
                    "severity": dep.severity,
                })

            elif dep.relationship == "contradicts" and source_present and target_present:
                tensions.append({
                    "type": "contradiction",
                    "source": dep.source.value,
                    "target": dep.target.value,
                    "description": dep.tension_description,
                    "severity": dep.severity,
                })

            elif dep.relationship == "limits_remedy" and source_present and target_present:
                tensions.append({
                    "type": "limitation",
                    "source": dep.source.value,
                    "target": dep.target.value,
                    "description": dep.tension_description,
                    "severity": dep.severity,
                })

            elif dep.relationship == "gap" and source_present and not target_present:
                tensions.append({
                    "type": "gap",
                    "source": dep.source.value,
                    "target": dep.target.value,
                    "description": dep.tension_description,
                    "severity": dep.severity,
                })

            elif dep.relationship == "requires" and source_present and not target_present:
                tensions.append({
                    "type": "missing_dependency",
                    "source": dep.source.value,
                    "target": dep.target.value,
                    "description": dep.tension_description,
                    "severity": dep.severity,
                })

            elif dep.relationship == "interacts" and source_present and target_present:
                tensions.append({
                    "type": "interaction",
                    "source": dep.source.value,
                    "target": dep.target.value,
                    "description": dep.tension_description,
                    "severity": dep.severity,
                })

            elif dep.relationship == "constrained_by" and source_present and target_present:
                tensions.append({
                    "type": "constraint",
                    "source": dep.source.value,
                    "target": dep.target.value,
                    "description": dep.tension_description,
                    "severity": dep.severity,
                })

        return tensions

    def detect_present_clauses(self, text: str) -> set[ClauseType]:
        """Determine which clause types are present in the document."""
        lower = text.lower()
        present: set[ClauseType] = set()

        clause_signals: dict[ClauseType, list[str]] = {
            ClauseType.LIABILITY_CAP: ["limit", "liability", "aggregate"],
            ClauseType.INDEMNIFICATION: ["indemnif", "indemnity", "hold harmless"],
            ClauseType.WARRANTY: ["warranty", "warrant"],
            ClauseType.WARRANTY_DISCLAIMER: ["as-is", "as is", "disclaim"],
            ClauseType.TERMINATION: ["terminat"],
            ClauseType.PAYMENT: ["purchase price", "payment", "pay"],
            ClauseType.RISK_OF_LOSS: ["risk of loss", "title shall pass"],
            ClauseType.IP_RIGHTS: ["intellectual property", "infringement"],
            ClauseType.FORCE_MAJEURE: ["force majeure"],
            ClauseType.INSURANCE: ["insurance"],
            ClauseType.CONFIDENTIALITY: ["confidential"],
            ClauseType.DATA_PROTECTION: ["data protection", "privacy", "gdpr"],
            ClauseType.CONSEQUENTIAL_DAMAGES: ["consequential", "indirect"],
            ClauseType.ACCEPTANCE_TESTING: ["acceptance", "inspection", "reject"],
            ClauseType.GOVERNING_LAW: ["governing law", "governed by"],
            ClauseType.ASSIGNMENT: ["assign"],
            ClauseType.DISPUTE_RESOLUTION: ["arbitrat", "mediat", "dispute resolution"],
            ClauseType.REPRESENTATIONS: ["represent", "warrant"],
            ClauseType.TITLE_OWNERSHIP: ["title", "pass", "repossess"],
            ClauseType.COMPLIANCE: ["compliance", "permit", "regulation"],
        }

        for clause_type, signals in clause_signals.items():
            if any(sig in lower for sig in signals):
                present.add(clause_type)

        return present

    def get_risk_score(self, tensions: list[dict[str, str]]) -> float:
        """Compute an aggregate risk score from 0-100 based on tensions found."""
        severity_weights = {"critical": 15, "high": 10, "medium": 5, "low": 2}
        total = sum(severity_weights.get(t["severity"], 5) for t in tensions)
        return min(total, 100)
