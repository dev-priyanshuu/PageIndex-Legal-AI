from __future__ import annotations

from dataclasses import dataclass

from infra.persistence import get_repository
from core.retrieval import TreeRetriever, VectorRetriever
from api.schemas import RetrieverMetrics
from infra.store import StoredDocument


@dataclass
class EvalCase:
    question: str
    expected_paths: list[str]
    expect_risk: bool


def _normalize_path(path: str) -> str:
    return " > ".join(part.strip().lower() for part in path.split(">"))


# Legal topic signals — used to generate questions from whatever headings exist
_TOPIC_SIGNALS: list[tuple[str, str, bool]] = [
    # (keyword_in_title_or_content, question_template, expect_risk_if_absent)
    ("indemnif",      "What are the indemnification obligations and any caps?",        False),
    ("terminat",      "What are the termination rights and conditions?",               False),
    ("warrant",       "What warranties are provided and what is excluded?",            False),
    ("liabilit",      "How is liability limited and what are the exclusions?",         False),
    ("payment",       "What are the payment terms and schedule?",                      False),
    ("deliver",       "What are the delivery obligations and timelines?",              False),
    ("ip right",      "What intellectual property rights are granted or retained?",    False),
    ("confidential",  "What confidentiality obligations apply to each party?",         False),
    ("govern",        "What law governs this agreement and where is disputes resolved?",False),
    ("force majeure", "What force majeure events excuse performance?",                 False),
    ("insurance",     "What insurance is required and who must maintain it?",          True),
    ("represent",     "What representations and warranties are made?",                 False),
    ("assignm",       "Can either party assign this agreement?",                       False),
    ("compli",        "What compliance and regulatory obligations apply?",             False),
    ("risk of loss",  "When does risk of loss transfer between parties?",              False),
    ("accept",        "What acceptance testing or inspection rights exist?",           True),
    ("title",         "When does title to the product transfer?",                      False),
    ("arbitrat",      "How are disputes resolved — arbitration or litigation?",        False),
    ("tax",           "Which party bears tax obligations?",                            False),
    ("remedies",      "What remedies are available for breach?",                       False),
]


def _build_eval_cases_from_tree(doc: StoredDocument, max_cases: int = 8) -> list[EvalCase]:
    """
    Generate eval cases entirely from the document's actual tree nodes.
    Every case uses a real node path from this document — no hardcoded paths.
    """
    cases: list[EvalCase] = []
    used_node_ids: set[str] = set()

    # Collect all nodes that have content
    content_nodes = [
        n for n in doc.tree.iter_content_nodes()
        if n.content.strip()
    ]
    if not content_nodes:
        content_nodes = list(doc.tree.iter_content_nodes())

    for keyword, question, expect_risk_if_absent in _TOPIC_SIGNALS:
        if len(cases) >= max_cases:
            break

        # Find the best matching node for this topic
        best_node = None
        best_score = 0

        for node in content_nodes:
            if node.node_id in used_node_ids:
                continue
            title_lower = node.title.lower()
            content_lower = node.content.lower()[:400]
            combined = title_lower + " " + content_lower

            # Title match scores higher than content match
            score = 0
            if keyword in title_lower:
                score = 3
            elif keyword in content_lower[:100]:
                score = 2
            elif keyword in combined:
                score = 1

            if score > best_score:
                best_score = score
                best_node = node

        if best_node is None:
            continue

        path = " > ".join(doc.tree.path_titles(best_node.node_id))
        content_lower = best_node.content.lower()

        # Detect if this node signals a risk (missing/absent clause)
        expect_risk = expect_risk_if_absent and any(
            w in content_lower for w in ("missing", "not included", "absent", "no provision", "none")
        )

        cases.append(EvalCase(
            question=question,
            expected_paths=[path],
            expect_risk=expect_risk,
        ))
        used_node_ids.add(best_node.node_id)

    # If we found fewer than 3 cases, add generic cases from top-level nodes
    if len(cases) < 3:
        for node in content_nodes:
            if node.node_id in used_node_ids:
                continue
            if not node.title.strip():
                continue
            path = " > ".join(doc.tree.path_titles(node.node_id))
            cases.append(EvalCase(
                question=f"What does the agreement say about {node.title.lower()}?",
                expected_paths=[path],
                expect_risk=False,
            ))
            used_node_ids.add(node.node_id)
            if len(cases) >= max_cases:
                break

    return cases


def _applicable_eval_cases(document_id: str) -> tuple[list[EvalCase], int, bool]:
    repo = get_repository()
    doc = repo.get(document_id)
    if doc is None:
        raise ValueError(f"Document not found: {document_id}")

    # Always generate from the document's own tree — fully dynamic
    cases = _build_eval_cases_from_tree(doc)
    return cases, len(cases) if cases else 1, True


def _score_retriever(document_id: str, mode: str, top_k: int, cases: list[EvalCase]) -> RetrieverMetrics:
    repo = get_repository()
    doc = repo.get(document_id)
    if doc is None:
        raise ValueError(f"Document not found: {document_id}")
    retriever = TreeRetriever() if mode == "tree" else VectorRetriever()

    recalls: list[float] = []
    citation_accuracies: list[float] = []
    risk_accuracies: list[float] = []

    if not cases:
        return RetrieverMetrics(recall_at_k=0.0, citation_path_accuracy=0.0, risk_detection_accuracy=0.0)

    for case in cases:
        hits = retriever.retrieve(doc.tree, case.question, top_k=top_k)
        hit_paths = [_normalize_path(h.heading_path) for h in hits]

        expected = [_normalize_path(p) for p in case.expected_paths]
        matched = sum(1 for p in expected if any(p in hp for hp in hit_paths))
        recall = matched / len(expected) if expected else 1.0
        recalls.append(recall)

        citation_accuracies.append(1.0 if hits and any(exp in hit_paths[0] for exp in expected) else 0.0)

        joined = " ".join(h.node.content.lower() for h in hits)
        detected_risk = "missing" in joined or "not included" in joined
        risk_accuracies.append(1.0 if detected_risk == case.expect_risk else 0.0)

    return RetrieverMetrics(
        recall_at_k=round(sum(recalls) / len(recalls), 4),
        citation_path_accuracy=round(sum(citation_accuracies) / len(citation_accuracies), 4),
        risk_detection_accuracy=round(sum(risk_accuracies) / len(risk_accuracies), 4),
    )


def run_benchmark(document_id: str, top_k: int) -> tuple[RetrieverMetrics, RetrieverMetrics, float]:
    applicable_cases, total_cases, auto_generated = _applicable_eval_cases(document_id=document_id)
    tree_metrics = _score_retriever(document_id=document_id, mode="tree", top_k=top_k, cases=applicable_cases)
    vector_metrics = _score_retriever(document_id=document_id, mode="vector", top_k=top_k, cases=applicable_cases)
    if auto_generated:
        # Coverage is 1.0 for auto-generated cases (they always match the doc)
        coverage = 1.0 if applicable_cases else 0.0
    else:
        coverage = round(len(applicable_cases) / total_cases, 4) if total_cases else 0.0
    return tree_metrics, vector_metrics, coverage


def build_markdown_report(document_id: str, top_k: int) -> str:
    tree_metrics, vector_metrics, coverage = run_benchmark(document_id=document_id, top_k=top_k)
    tree_total = tree_metrics.recall_at_k + tree_metrics.citation_path_accuracy + tree_metrics.risk_detection_accuracy
    vector_total = (
        vector_metrics.recall_at_k + vector_metrics.citation_path_accuracy + vector_metrics.risk_detection_accuracy
    )
    winner = "Tree retrieval" if tree_total >= vector_total else "Vector retrieval"
    return (
        f"# Evaluation Report: {document_id}\n\n"
        "## Retrieval Comparison\n"
        f"- Winner: **{winner}**\n"
        f"- Tree recall@k: {tree_metrics.recall_at_k}\n"
        f"- Tree citation path accuracy: {tree_metrics.citation_path_accuracy}\n"
        f"- Tree risk detection accuracy: {tree_metrics.risk_detection_accuracy}\n"
        f"- Vector recall@k: {vector_metrics.recall_at_k}\n"
        f"- Vector citation path accuracy: {vector_metrics.citation_path_accuracy}\n"
        f"- Vector risk detection accuracy: {vector_metrics.risk_detection_accuracy}\n"
        f"- Eval case coverage: {coverage}\n\n"
        "## Why this matters\n"
        "Hierarchy-aware retrieval preserves clause lineage and improves citation precision for legal reasoning.\n"
    )

