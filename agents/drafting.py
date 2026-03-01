from __future__ import annotations

from api.schemas import NegotiationPoint, RiskItem


class DraftingAgent:
    """Generates targeted negotiation suggestions with fallback positions."""

    def suggest(self, risks: list[RiskItem]) -> list[NegotiationPoint]:
        suggestions: list[NegotiationPoint] = []
        seen: set[str] = set()

        for risk in risks:
            cat = risk.category.lower()
            if cat in seen:
                continue
            seen.add(cat)

            if "liability cap" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Liability Cap",
                    suggestion="Negotiate liability cap at 2-3x Purchase Price for direct damages.",
                    fallback_position="Accept Purchase Price cap but carve out fraud, willful misconduct, and IP claims.",
                ))
            elif "risk of loss" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Risk of Loss",
                    suggestion="Risk should pass only after successful acceptance testing, not mere delivery.",
                    fallback_position="Risk passes at delivery but Seller bears defect-related losses for 90 days.",
                ))
            elif "warranty" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Warranty Duration",
                    suggestion="Extend warranty to 3 years for structural, 2 years for components.",
                    fallback_position="Accept 1-year warranty but add mandatory extended warranty purchase option.",
                ))
            elif "as-is" in cat:
                suggestions.append(NegotiationPoint(
                    issue="AS-IS Disclaimer Scope",
                    suggestion="Limit AS-IS to services only; exclude product warranties and IP indemnity.",
                    fallback_position="Add explicit carve-out: 'AS-IS does not limit Sections 6 and 7 obligations.'",
                ))
            elif "termination" in cat and "imbalance" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Termination Rights",
                    suggestion="Add reciprocal Buyer termination for Seller breach, non-delivery, and insolvency.",
                    fallback_position="Add Buyer termination only for material uncured breach after 30-day notice.",
                ))
            elif "cure" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Cure Period",
                    suggestion="Add 30-day cure period for all non-fundamental breaches before termination.",
                    fallback_position="15-day cure for payment breaches; 30-day for operational breaches.",
                ))
            elif "payment" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Payment Security",
                    suggestion="Use escrow for pre-delivery payments; release upon successful acceptance.",
                    fallback_position="Reduce upfront payment to 25% with balance tied to delivery milestones.",
                ))
            elif "indemnif" in cat or "indemnity" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Indemnification",
                    suggestion="Add mutual indemnification covering third-party claims, product liability, and IP.",
                    fallback_position="At minimum, Seller indemnifies Buyer for product defect and IP claims.",
                ))
            elif "insurance" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Insurance",
                    suggestion="Require insurance certificates, 30-day cancellation notice, and Buyer as additional insured.",
                    fallback_position="Annual certificate of insurance delivery with coverage aligned to liability cap.",
                ))
            elif "acceptance" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Acceptance Testing",
                    suggestion="Add formal 30-day acceptance period with right to reject for non-conformity.",
                    fallback_position="15-day inspection window with punch-list process for minor defects.",
                ))
            elif "force majeure" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Force Majeure",
                    suggestion="Narrow force majeure to truly unforeseeable events; add termination right after 90 days.",
                    fallback_position="Keep broad definition but add: Buyer may terminate if delay exceeds 60 days.",
                ))
            elif "ip" in cat:
                suggestions.append(NegotiationPoint(
                    issue="IP Indemnification",
                    suggestion="Seller must defend, indemnify, and hold harmless Buyer for all IP infringement claims.",
                    fallback_position="Seller indemnifies only for registered IP claims known at time of sale.",
                ))
            elif "consequential" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Consequential Damages",
                    suggestion="Remove blanket exclusion; allow consequential damages for willful breach and IP claims.",
                    fallback_position="Cap consequential damages at 1x Purchase Price.",
                ))
            elif "data" in cat:
                suggestions.append(NegotiationPoint(
                    issue="Data Protection",
                    suggestion="Add explicit data protection, FERPA/GDPR compliance, and breach notification obligations.",
                    fallback_position="At minimum, add data breach notification within 72 hours.",
                ))

        return suggestions
