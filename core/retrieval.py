from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core.pageindex_engine import LegalNode, LegalTree


TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]+")


@dataclass
class RetrievalHit:
    node: LegalNode
    score: float
    heading_path: str


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text)}


def _tokenize_list(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def _node_text(node: LegalNode) -> str:
    return (node.title + " " + node.content).strip()


def _build_doc_idf(tree: LegalTree) -> dict[str, float]:
    """
    Compute per-document IDF for every token across all nodes.
    This makes scoring adapt to each document's vocabulary — rare terms
    in this document get a higher weight than common ones.
    """
    node_count = 0
    df: Counter[str] = Counter()
    for node in tree.iter_content_nodes():
        tokens = _tokenize(node.title + " " + node.content)
        if tokens:
            node_count += 1
            df.update(tokens)
    idf: dict[str, float] = {}
    for token, freq in df.items():
        idf[token] = math.log((node_count + 1) / (freq + 1)) + 1.0
    return idf


class TreeRetriever:
    """
    PageIndex-style hierarchy-aware retriever.

    Scoring is fully dynamic per document:
    - Uses per-document IDF so rare legal terms in this document score higher.
    - Hierarchy bonus scales with the document's average tree depth.
    - Specificity bonus scales with the node's relative depth in the tree.
    """

    def retrieve(self, tree: LegalTree, question: str, top_k: int = 4) -> list[RetrievalHit]:
        if not tree.nodes:
            return []

        idf = _build_doc_idf(tree)
        q_tokens = _tokenize(question)

        # Document-adaptive parameters
        all_levels = [n.level for n in tree.nodes.values()]
        max_level = max(all_levels) if all_levels else 1
        avg_level = sum(all_levels) / len(all_levels) if all_levels else 1.0
        # Hierarchy bonus scales up for deeper documents
        hierarchy_weight = 1.5 + (avg_level / max(max_level, 1)) * 0.8

        scored: list[RetrievalHit] = []

        for node in tree.iter_content_nodes():
            # Skip pure structural nodes with no content and no children
            if not node.content.strip() and not tree.children.get(node.node_id):
                continue

            path_tokens = _tokenize(" ".join(tree.path_titles(node.node_id)))
            content_tokens = _tokenize(node.title + " " + node.content)

            # IDF-weighted overlap on content
            content_overlap = sum(
                idf.get(t, 1.0) for t in q_tokens & content_tokens
            )
            # IDF-weighted hierarchy bonus
            hierarchy_bonus = sum(
                idf.get(t, 1.0) for t in q_tokens & path_tokens
            ) * hierarchy_weight

            # Relative depth bonus: deeper nodes are more specific
            relative_depth = node.level / max(max_level, 1)
            specificity_bonus = 0.3 + relative_depth * 0.7

            score = content_overlap + hierarchy_bonus + specificity_bonus

            if score <= 0.3:
                continue

            path = " > ".join(tree.path_titles(node.node_id))
            scored.append(RetrievalHit(node=node, score=score, heading_path=path))

        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]


class VectorRetriever:
    """
    TF-IDF vector retriever over full node text (title + content).
    Uses the document's own vocabulary — fully dynamic per upload.
    """

    def retrieve(self, tree: LegalTree, question: str, top_k: int = 4) -> list[RetrievalHit]:
        nodes = [n for n in tree.iter_content_nodes() if _node_text(n).strip()]
        if not nodes:
            return []
        corpus = [_node_text(n) for n in nodes]
        try:
            vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),
                stop_words="english",
                sublinear_tf=True,   # log-scale TF — adapts to long vs short docs
                min_df=1,
            )
            matrix = vectorizer.fit_transform(corpus + [question])
        except ValueError:
            # Corpus too small or all stop words
            return []
        q = matrix[-1]
        d = matrix[:-1]
        sims = cosine_similarity(q, d)[0]

        pairs = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)[:top_k]
        hits: list[RetrievalHit] = []
        for idx, score in pairs:
            node = nodes[idx]
            path = " > ".join(tree.path_titles(node.node_id))
            hits.append(RetrievalHit(node=node, score=float(score), heading_path=path))
        return hits

