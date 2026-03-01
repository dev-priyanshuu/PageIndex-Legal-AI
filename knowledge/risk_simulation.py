"""
Risk Simulation Agent.

For each detected risk, simulates:
  - Probability of materialisation (based on contract signals)
  - Estimated financial impact (relative to Purchase Price)
  - Worst-case scenario narrative
  - Mitigation effectiveness if the recommended amendment is adopted

Output is a structured RiskScenario list that feeds the frontend
risk simulation dashboard.
"""
from __future__ import annotations

import re

from api.schemas import RiskItem, RiskScenario


_SIMULATION_RULES: dict[str, dict] = {
    "Liability Cap": {
        "probability": 0.35,
        "impact_multiple": 1.0,
        "worst_case": (
            "Product failure causes $500K+ operational disruption. Buyer can only recover "
            "the Purchase Price (~$77K). Net loss: ~$423K+ unrecoverable."
        ),
        "mitigation": "Negotiate cap at 2-3x Purchase Price with carve-outs for fraud and IP.",
        "residual": 0.15,
    },
    "Risk of Loss": {
        "probability": 0.20,
        "impact_multiple": 0.5,
        "worst_case": (
            "Product damaged in transit or during installation. Buyer bears full replacement "
            "cost (~$38K) with no recourse against Seller."
        ),
        "mitigation": "Risk passes only after successful acceptance testing; Seller insures in transit.",
        "residual": 0.05,
    },
    "Warranty Duration": {
        "probability": 0.40,
        "impact_multiple": 0.3,
        "worst_case": (
            "Major component failure in Year 2. Warranty expired; Buyer pays full repair "
            "cost (~$23K) with no Seller obligation."
        ),
        "mitigation": "Extend warranty to 3 years structural, 2 years components.",
        "residual": 0.10,
    },
    "AS-IS Disclaimer": {
        "probability": 0.30,
        "impact_multiple": 0.8,
        "worst_case": (
            "Product does not perform as represented. AS-IS clause bars all warranty claims. "
            "Buyer loses investment (~$62K) with no legal recourse."
        ),
        "mitigation": "Limit AS-IS to services; preserve express warranties and IP indemnity.",
        "residual": 0.10,
    },
    "Termination Imbalance": {
        "probability": 0.15,
        "impact_multiple": 1.2,
        "worst_case": (
            "Seller terminates mid-installation. Buyer has paid 50% (~$38K), product is "
            "partially installed, and has no contractual right to compel completion or "
            "recover consequential losses."
        ),
        "mitigation": "Add reciprocal Buyer termination rights and refund of pre-paid amounts.",
        "residual": 0.05,
    },
    "Missing Cure Period": {
        "probability": 0.25,
        "impact_multiple": 0.4,
        "worst_case": (
            "Minor technical breach triggers immediate termination. Buyer loses product "
            "and all payments (~$31K) without opportunity to cure."
        ),
        "mitigation": "Add 30-day cure period for all non-fundamental breaches.",
        "residual": 0.08,
    },
    "Payment Risk": {
        "probability": 0.20,
        "impact_multiple": 0.5,
        "worst_case": (
            "Buyer pays 50% upfront (~$38K). Seller becomes insolvent before delivery. "
            "Buyer is unsecured creditor with low recovery prospects."
        ),
        "mitigation": "Use escrow for pre-delivery payments; release upon acceptance.",
        "residual": 0.05,
    },
    "Missing Indemnification": {
        "probability": 0.25,
        "impact_multiple": 2.0,
        "worst_case": (
            "Third party sues Buyer for product-related injury (~$150K claim). No "
            "indemnification from Seller. Buyer bears full defense cost and damages."
        ),
        "mitigation": "Add mutual indemnification covering third-party claims and product liability.",
        "residual": 0.10,
    },
    "Buyer Indemnity Gap": {
        "probability": 0.20,
        "impact_multiple": 1.5,
        "worst_case": (
            "Third party IP claim against Buyer for Seller's product (~$115K). "
            "Seller's indemnity is ambiguous; Buyer bears defense costs alone."
        ),
        "mitigation": "Require Seller to defend, indemnify, and hold harmless Buyer for all product claims.",
        "residual": 0.08,
    },
    "Insurance Verification": {
        "probability": 0.30,
        "impact_multiple": 0.6,
        "worst_case": (
            "Seller's insurance lapses. Product causes property damage (~$46K). "
            "Buyer cannot claim against Seller's policy; Seller may be judgment-proof."
        ),
        "mitigation": "Require annual insurance certificates with Buyer as additional insured.",
        "residual": 0.08,
    },
    "Missing Insurance": {
        "probability": 0.40,
        "impact_multiple": 1.0,
        "worst_case": (
            "Product causes damage during installation. No insurance coverage. "
            "Buyer bears full loss (~$77K) with no insured recovery path."
        ),
        "mitigation": "Require Seller to maintain product liability and installation insurance.",
        "residual": 0.12,
    },
    "No Acceptance Testing": {
        "probability": 0.35,
        "impact_multiple": 0.7,
        "worst_case": (
            "Product delivered with latent defects. No acceptance testing means risk "
            "passed at delivery. Buyer pays ~$54K to fix defects post-warranty."
        ),
        "mitigation": "Add 30-day acceptance period with right to reject non-conforming product.",
        "residual": 0.08,
    },
    "Broad Force Majeure": {
        "probability": 0.15,
        "impact_multiple": 0.5,
        "worst_case": (
            "Seller invokes force majeure for supply chain issues. Delivery delayed 6+ months. "
            "Buyer has no termination right; loses use of facility (~$38K opportunity cost)."
        ),
        "mitigation": "Add Buyer termination right after 60-day force majeure delay.",
        "residual": 0.06,
    },
    "IP Indemnification Gap": {
        "probability": 0.15,
        "impact_multiple": 2.5,
        "worst_case": (
            "Patent holder sues Buyer for using Seller's product (~$192K claim). "
            "IP indemnity is ambiguous or capped at Purchase Price. Buyer exposed."
        ),
        "mitigation": "Seller must defend, indemnify, and hold harmless Buyer for all IP claims without cap.",
        "residual": 0.08,
    },
    "Data Protection Gap": {
        "probability": 0.10,
        "impact_multiple": 0.3,
        "worst_case": (
            "Data breach involving student records. No contractual data protection "
            "obligations. Regulatory fine + reputational damage (~$23K+)."
        ),
        "mitigation": "Add explicit data protection, breach notification, and FERPA compliance obligations.",
        "residual": 0.05,
    },
    "Consequential Damages Exclusion": {
        "probability": 0.40,
        "impact_multiple": 3.0,
        "worst_case": (
            "Product failure causes crop loss + program disruption (~$231K). "
            "Consequential damages waiver bars all recovery beyond Purchase Price. "
            "Net unrecoverable loss: ~$154K."
        ),
        "mitigation": "Remove blanket exclusion; allow consequential damages for willful breach and IP claims.",
        "residual": 0.15,
    },
    "Title Retention Risk": {
        "probability": 0.15,
        "impact_multiple": 0.8,
        "worst_case": (
            "Buyer defaults on final payment. Seller repossesses product after Buyer "
            "has invested in site preparation (~$62K). Buyer also owes repossession costs."
        ),
        "mitigation": "Title should pass at delivery; payment obligations secured separately.",
        "residual": 0.06,
    },
    "Assignment Imbalance": {
        "probability": 0.10,
        "impact_multiple": 0.2,
        "worst_case": (
            "Seller assigns agreement to unknown third party. Buyer has no approval "
            "right and must deal with new counterparty with unknown capabilities."
        ),
        "mitigation": "Require mutual consent for assignment or add Buyer approval right.",
        "residual": 0.04,
    },
}

_PROBABILITY_LABELS = [
    (0.10, "Low"),
    (0.25, "Medium"),
    (0.45, "High"),
    (1.00, "Very High"),
]

_IMPACT_LABELS = [
    (0.3, "Low"),
    (0.7, "Moderate"),
    (1.5, "High"),
    (99.0, "Severe"),
]


def _prob_label(p: float) -> str:
    for threshold, label in _PROBABILITY_LABELS:
        if p <= threshold:
            return label
    return "Very High"


def _impact_label(m: float) -> str:
    for threshold, label in _IMPACT_LABELS:
        if m <= threshold:
            return label
    return "Severe"


def _extract_purchase_price(text: str) -> float | None:
    """Try to extract the purchase price from the document text."""
    patterns = [
        r"\$\s*([\d,]+(?:\.\d{2})?)",
        r"purchase price.*?\$\s*([\d,]+)",
        r"([\d,]+(?:\.\d{2})?)\s*(?:USD|dollars)",
    ]
    for pat in patterns:
        m = re.search(pat, text[:3000], flags=re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


class RiskSimulationAgent:
    """
    Simulates the financial and operational impact of each detected risk.
    Produces scenario narratives with probability, impact, and mitigation.
    """

    def simulate(
        self,
        risks: list[RiskItem],
        full_text: str = "",
        purchase_price: float | None = None,
    ) -> list[RiskScenario]:
        if purchase_price is None:
            purchase_price = _extract_purchase_price(full_text) or 100_000.0

        scenarios: list[RiskScenario] = []
        seen: set[str] = set()

        for risk in risks:
            cat = risk.category
            if cat in seen:
                continue
            seen.add(cat)

            rule = _SIMULATION_RULES.get(cat)
            if rule is None:
                rule = {
                    "probability": 0.20,
                    "impact_multiple": 0.5,
                    "worst_case": (
                        f"Risk materialises: {risk.description[:200]} "
                        f"Estimated impact: ~${purchase_price * 0.5:,.0f}."
                    ),
                    "mitigation": "Review and negotiate this clause with legal counsel.",
                    "residual": 0.10,
                }

            prob = rule["probability"]
            impact_m = rule["impact_multiple"]
            impact_dollars = purchase_price * impact_m

            worst_case = rule["worst_case"]
            if "$77K" in worst_case or "$77,000" in worst_case:
                worst_case = worst_case.replace("$77K", f"${purchase_price:,.0f}")
                worst_case = worst_case.replace("$77,000", f"${purchase_price:,.0f}")

            scenarios.append(RiskScenario(
                risk_category=cat,
                severity=risk.severity,
                probability=prob,
                probability_label=_prob_label(prob),
                financial_impact_multiple=impact_m,
                financial_impact_label=_impact_label(impact_m),
                worst_case=worst_case,
                mitigation_suggestion=rule["mitigation"],
                residual_risk_after_mitigation=rule["residual"],
                affected_party=risk.affected_party or "buyer",
            ))

        scenarios.sort(
            key=lambda s: (
                {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(s.severity, 0),
                s.probability * s.financial_impact_multiple,
            ),
            reverse=True,
        )
        return scenarios

    def compute_portfolio_risk(
        self,
        scenarios: list[RiskScenario],
        purchase_price: float,
    ) -> dict:
        """Aggregate expected loss and worst-case exposure across all scenarios."""
        expected_loss = sum(
            s.probability * s.financial_impact_multiple * purchase_price
            for s in scenarios
        )
        worst_case_exposure = sum(
            s.financial_impact_multiple * purchase_price
            for s in scenarios
            if s.severity in ("critical", "high")
        )
        mitigated_loss = sum(
            s.residual_risk_after_mitigation * s.financial_impact_multiple * purchase_price
            for s in scenarios
        )
        mitigation_value = expected_loss - mitigated_loss

        return {
            "purchase_price": purchase_price,
            "expected_loss": round(expected_loss, 2),
            "worst_case_exposure": round(worst_case_exposure, 2),
            "mitigated_expected_loss": round(mitigated_loss, 2),
            "mitigation_value": round(mitigation_value, 2),
            "risk_to_price_ratio": round(expected_loss / max(purchase_price, 1), 3),
            "scenario_count": len(scenarios),
        }
