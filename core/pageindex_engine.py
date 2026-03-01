from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class LegalNode:
    node_id: str
    title: str
    content: str
    level: int
    parent_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class LegalTree:
    document_id: str
    nodes: dict[str, LegalNode]
    children: dict[str, list[str]]
    root_ids: list[str]

    def path_titles(self, node_id: str) -> list[str]:
        path: list[str] = []
        current = self.nodes[node_id]
        while True:
            path.append(current.title)
            if current.parent_id is None:
                break
            current = self.nodes[current.parent_id]
        return list(reversed(path))

    def iter_content_nodes(self) -> Iterable[LegalNode]:
        return self.nodes.values()


def _heading_level(line: str) -> int | None:
    if not line.startswith("#"):
        return None
    level = 0
    for ch in line:
        if ch == "#":
            level += 1
        else:
            break
    return level if level > 0 else None


def build_tree_from_markdown(document_id: str, text: str, metadata: dict[str, str]) -> LegalTree:
    """
    Build a LegalTree from markdown-formatted text.

    Fully dynamic — adapts to whatever headings the document contains:
    - Each heading becomes a node; its body text is stored as content.
    - No placeholder/empty nodes: content is always merged into the heading node.
    - Hierarchy is inferred from # depth, not from fixed section numbering.
    - Preamble text (before the first heading) is kept only if non-empty.
    """
    nodes: dict[str, LegalNode] = {}
    children: dict[str, list[str]] = {}
    root_ids: list[str] = []
    # stack holds (node_id, level) pairs
    stack: list[tuple[str, int]] = []
    counter = 0

    def _add_node(title: str, level: int, content: str) -> str:
        nonlocal counter
        counter += 1
        node_id = f"{document_id}-n{counter}"
        parent_id = stack[-1][0] if stack else None
        node = LegalNode(
            node_id=node_id,
            title=title.strip(),
            content=content.strip(),
            level=level,
            parent_id=parent_id,
            metadata=metadata.copy(),
        )
        nodes[node_id] = node
        children[node_id] = []
        if parent_id:
            children[parent_id].append(node_id)
        else:
            root_ids.append(node_id)
        return node_id

    current_title: str | None = None
    current_level: int = 0
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        level = _heading_level(line)

        if level is None:
            current_lines.append(line)
            continue

        # --- Flush the previous section ---
        if current_title is not None:
            content = "\n".join(current_lines).strip()
            # Pop stack entries at same or deeper level
            while stack and stack[-1][1] >= level:
                stack.pop()
            node_id = _add_node(current_title, current_level, content)
            stack.append((node_id, current_level))
        else:
            # Pre-heading preamble text
            preamble = "\n".join(current_lines).strip()
            if preamble:
                while stack and stack[-1][1] >= 1:
                    stack.pop()
                node_id = _add_node("Preamble", 1, preamble)
                stack.append((node_id, 1))

        heading_text = line[level:].strip() or f"Section {counter + 1}"
        current_title = heading_text
        current_level = level
        current_lines = []

    # Flush the last section
    if current_title is not None:
        content = "\n".join(current_lines).strip()
        while stack and stack[-1][1] >= current_level:
            stack.pop()
        node_id = _add_node(current_title, current_level, content)
    elif current_lines:
        preamble = "\n".join(current_lines).strip()
        if preamble:
            _add_node("Preamble", 1, preamble)

    return LegalTree(document_id=document_id, nodes=nodes, children=children, root_ids=root_ids)

