from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict

from infra.config import SETTINGS
from core.pageindex_engine import LegalNode, LegalTree
from infra.store import StoredDocument


class DocumentRepository:
    def save(self, doc: StoredDocument) -> None:
        raise NotImplementedError

    def get(self, document_id: str) -> StoredDocument | None:
        raise NotImplementedError


class MemoryRepository(DocumentRepository):
    def __init__(self) -> None:
        self.docs: dict[str, StoredDocument] = {}

    def save(self, doc: StoredDocument) -> None:
        self.docs[doc.document_id] = doc

    def get(self, document_id: str) -> StoredDocument | None:
        return self.docs.get(document_id)


class SqliteRepository(DocumentRepository):
    def __init__(self, path: str) -> None:
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    tree_json TEXT NOT NULL
                )
                """
            )

    def save(self, doc: StoredDocument) -> None:
        payload = {
            "document_id": doc.document_id,
            "title": doc.title,
            "metadata_json": json.dumps(doc.metadata),
            "source_text": doc.source_text,
            "tree_json": json.dumps(_tree_to_dict(doc.tree)),
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents(document_id, title, metadata_json, source_text, tree_json)
                VALUES(:document_id, :title, :metadata_json, :source_text, :tree_json)
                ON CONFLICT(document_id) DO UPDATE SET
                  title = excluded.title,
                  metadata_json = excluded.metadata_json,
                  source_text = excluded.source_text,
                  tree_json = excluded.tree_json
                """,
                payload,
            )

    def get(self, document_id: str) -> StoredDocument | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT document_id, title, metadata_json, source_text, tree_json
                FROM documents WHERE document_id = ?
                """,
                (document_id,),
            ).fetchone()
        if row is None:
            return None
        tree = _tree_from_dict(json.loads(row[4]))
        return StoredDocument(
            document_id=row[0],
            title=row[1],
            metadata=json.loads(row[2]),
            source_text=row[3],
            tree=tree,
        )


def _tree_to_dict(tree: LegalTree) -> dict:
    return {
        "document_id": tree.document_id,
        "nodes": {node_id: asdict(node) for node_id, node in tree.nodes.items()},
        "children": tree.children,
        "root_ids": tree.root_ids,
    }


def _tree_from_dict(data: dict) -> LegalTree:
    nodes = {node_id: LegalNode(**node_data) for node_id, node_data in data["nodes"].items()}
    return LegalTree(
        document_id=data["document_id"],
        nodes=nodes,
        children=data["children"],
        root_ids=data["root_ids"],
    )


def get_repository() -> DocumentRepository:
    global _REPO
    if _REPO is not None:
        return _REPO
    backend = SETTINGS.storage_backend.lower()
    if backend == "sqlite":
        _REPO = SqliteRepository(SETTINGS.sqlite_path)
        return _REPO
    _REPO = MemoryRepository()
    return _REPO


_REPO: DocumentRepository | None = None

