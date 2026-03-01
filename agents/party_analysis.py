from __future__ import annotations

from core.retrieval import RetrievalHit
from api.schemas import PartyAnalysis


class PartyAnalysisAgent:
    """Analyzes which party is more protected by the agreement."""

    def analyze(self, hits: list[RetrievalHit], full_text: str = "") -> PartyAnalysis:
        combined = " ".join((h.heading_path + " " + h.node.content).lower() for h in hits)
        full = (combined + " " + full_text).lower()

        buyer_protections: list[str] = []
        seller_protections: list[str] = []

        if "warranty" in full or "warrant" in full:
            buyer_protections.append("Express warranties on product")
        if "as-is" in full or "as is" in full:
            seller_protections.append("AS-IS disclaimer limits warranty scope")
        if "limit" in full and "liability" in full:
            seller_protections.append("Liability capped (likely at Purchase Price)")
        if "indirect" in full and "consequential" in full:
            seller_protections.append("Indirect/consequential damages excluded")
        if "seller may terminate" in full and "buyer may terminate" not in full:
            seller_protections.append("Unilateral termination rights")
        elif "buyer may terminate" in full:
            buyer_protections.append("Buyer termination rights present")
        if "infringement" in full and "seller" in full:
            buyer_protections.append("Some IP infringement protection from Seller")
        if "insurance" in full:
            buyer_protections.append("Seller required to maintain insurance")
        if "before" in full and ("deliver" in full or "execution" in full):
            seller_protections.append("Payment before or at delivery reduces Seller risk")
        if "force majeure" in full:
            seller_protections.append("Broad force majeure protects Seller from obligations")
        if "governing law" in full or "governed by" in full:
            buyer_protections.append("Governing law and jurisdiction defined")

        seller_score = len(seller_protections)
        buyer_score = len(buyer_protections)

        if seller_score > buyer_score + 1:
            advantage = "seller"
            summary = (
                f"Agreement favors Seller ({seller_score} protections vs Buyer's {buyer_score}). "
                "Buyer should negotiate stronger terms."
            )
        elif buyer_score > seller_score + 1:
            advantage = "buyer"
            summary = f"Agreement favors Buyer ({buyer_score} protections vs Seller's {seller_score})."
        elif abs(seller_score - buyer_score) <= 1:
            advantage = "balanced"
            summary = (
                f"Roughly balanced ({buyer_score} buyer vs {seller_score} seller protections), "
                "but check quality of each."
            )
        else:
            advantage = "unclear"
            summary = "Cannot determine clear advantage from retrieved clauses."

        return PartyAnalysis(
            advantage=advantage,
            buyer_protections=buyer_protections,
            seller_protections=seller_protections,
            summary=summary,
        )
