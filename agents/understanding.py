from __future__ import annotations

import re
from dataclasses import dataclass, field

from knowledge.legal_ontology import ClauseDependencyGraph


@dataclass
class LegalContext:
    parties: list[str]
    jurisdiction: str | None
    obligations: list[str]
    section_titles: list[str] = field(default_factory=list)
    present_clauses: set[str] = field(default_factory=set)


class LegalUnderstandingAgent:
    """Extracts parties, jurisdiction, obligations, and present clause types from document text."""

    def __init__(self) -> None:
        self._dep_graph = ClauseDependencyGraph()

    def analyze(self, text: str) -> LegalContext:
        party_matches = re.findall(
            r"\b([A-Z][A-Za-z0-9& ]+?)\s*\((?:Buyer|Seller|Company|Vendor)\)", text
        )
        jurisdiction_match = re.search(
            r"\bgoverned by the laws of ([A-Za-z ,]+)\b", text, flags=re.IGNORECASE
        )
        obligations = [
            kw for kw in ("shall", "must", "obligated", "required") if kw in text.lower()
        ]
        section_titles = re.findall(r"^#+\s+(.+)$", text, flags=re.MULTILINE)
        present_clauses = {ct.value for ct in self._dep_graph.detect_present_clauses(text)}
        return LegalContext(
            parties=sorted(set(p.strip() for p in party_matches)),
            jurisdiction=jurisdiction_match.group(1).strip() if jurisdiction_match else None,
            obligations=obligations,
            section_titles=section_titles,
            present_clauses=present_clauses,
        )
