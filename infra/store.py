from __future__ import annotations

from dataclasses import dataclass, field

from core.pageindex_engine import LegalTree


@dataclass
class StoredDocument:
    document_id: str
    title: str
    metadata: dict[str, str]
    source_text: str
    tree: LegalTree


@dataclass
class SessionMemory:
    session_id: str
    questions: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    preferences: dict[str, str] = field(default_factory=dict)


DOCUMENTS: dict[str, StoredDocument] = {}
SESSIONS: dict[str, SessionMemory] = {}

