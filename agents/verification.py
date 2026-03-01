from __future__ import annotations

from core.retrieval import RetrievalHit
from api.schemas import RiskItem


class VerificationAgent:
    """
    Cross-checks risk claims against the actual document structure.
    Prevents false 'missing clause' claims by verifying against section
    headings and full document text.
    """

    HEADING_KEYWORDS: dict[str, list[str]] = {
        "Missing Indemnification": ["indemnif", "indemnity", "hold harmless"],
        "Missing Insurance": ["insurance", "coverage", "insured"],
        "Missing Termination": ["terminat", "suspension"],
        "Missing Governing Law": ["governing law", "governed by", "jurisdiction"],
        "Missing Force Majeure": ["force majeure"],
        "Missing Confidentiality": ["confidential", "data sharing", "privacy"],
        "Missing Warranty": ["warrant", "warranty", "as-is"],
        "Missing Liability Limit": ["limit", "liability", "damages"],
        "Missing Acceptance": ["acceptance", "approval", "inspection"],
        "Missing Payment": ["payment", "purchase price", "terms of payment"],
    }

    def verify_risks(
        self,
        risks: list[RiskItem],
        section_titles: list[str],
        full_text: str,
    ) -> list[RiskItem]:
        titles_lower = " ".join(t.lower() for t in section_titles)
        text_lower = full_text.lower()
        verified: list[RiskItem] = []

        for risk in risks:
            if risk.category.startswith("Missing"):
                keywords = self.HEADING_KEYWORDS.get(risk.category, [])
                if not keywords:
                    keywords = [risk.category.replace("Missing ", "").lower()]

                found_in_headings = any(kw in titles_lower for kw in keywords)
                found_in_text = any(kw in text_lower for kw in keywords)

                if found_in_headings or found_in_text:
                    verified.append(RiskItem(
                        category=risk.category.replace("Missing ", "") + " Gap",
                        severity="medium" if risk.severity == "critical" else risk.severity,
                        description=(
                            f"Clause exists but may have gaps: {risk.description} "
                            "(Verified: found in document headings/text.)"
                        ),
                        clause_reference=risk.clause_reference or "See document sections",
                    ))
                else:
                    verified.append(risk)
            else:
                verified.append(risk)

        return verified

    def compute_section_coverage(self, hits: list[RetrievalHit], total_sections: int) -> float:
        if total_sections == 0:
            return 0.0
        return len(hits) / total_sections
