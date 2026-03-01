from __future__ import annotations

import re
import statistics
from dataclasses import dataclass


@dataclass
class ExtractedDocument:
    text: str
    char_count: int
    page_count: int


# Numbered section: "1.2 Title" or "12.3.4 Title" — must start with a capital word
SECTION_RE = re.compile(r"^(\d+(\.\d+)*)\s{1,4}([A-Z][A-Za-z].{2,})$")

# Table-of-contents lines: contain 3+ consecutive dots
TOC_RE = re.compile(r"\.{3,}")

# Standalone page number
PAGE_NUM_RE = re.compile(r"^\d{1,4}$")

# ALL CAPS heading (e.g. "INDEMNIFICATION", "WARRANTIES OF THE SELLER")
ALL_CAPS_RE = re.compile(r"^[A-Z][A-Z\s\-&,/\']{3,}$")


def _promote_to_markdown(raw_text: str) -> str:
    """Fallback for plain-text files: use numbered sections and ALL CAPS as headings."""
    lines = [line.strip() for line in raw_text.splitlines()]
    out: list[str] = []
    for line in lines:
        if not line:
            out.append("")
            continue
        if bool(PAGE_NUM_RE.match(line)) or bool(TOC_RE.search(line)):
            continue
        m = SECTION_RE.match(line)
        if m:
            depth = m.group(1).count(".") + 2
            out.append(f"{'#' * min(depth, 6)} {m.group(3).strip()}")
            continue
        if ALL_CAPS_RE.match(line) and len(line) < 80:
            out.append(f"## {line.title()}")
            continue
        out.append(line)
    return "\n".join(out).strip()


NOISE_LINE_RE = re.compile(
    r"^\[●\]$"
    r"|^\d+\.$"
    r"|^\(\d+\)$"
    r"|^\d+\(\d+\)$"
)


def _extract_structured_from_pdf(fitz_doc: object) -> str:  # type: ignore[type-arg]
    """
    Use PyMuPDF font metadata (size + bold flags) to identify real headings.
    Strategy:
      1. Collect font sizes and bold flags for every text line.
      2. Compute the dominant (most common) body font size.
      3. Any line that is BOLD or has font size significantly above body size → heading.
      4. Drop ToC lines, page numbers, and noise patterns.
    """
    import fitz  # type: ignore
    from collections import Counter

    all_sizes: list[float] = []
    page_spans: list[list[tuple[float, str, bool]]] = []

    for page in fitz_doc:
        spans_on_page: list[tuple[float, str, bool]] = []
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                line_text = "".join(s["text"] for s in line.get("spans", [])).strip()
                if not line_text:
                    continue
                if bool(TOC_RE.search(line_text)):
                    continue
                if bool(PAGE_NUM_RE.match(line_text)):
                    continue
                if bool(NOISE_LINE_RE.match(line_text)):
                    continue
                sizes = [s["size"] for s in line.get("spans", []) if s.get("text", "").strip()]
                if not sizes:
                    continue
                avg_size = sum(sizes) / len(sizes)
                is_bold = any(s.get("flags", 0) & 16 for s in line.get("spans", []))
                all_sizes.append(round(avg_size, 1))
                spans_on_page.append((avg_size, line_text, is_bold))
        page_spans.append(spans_on_page)

    if not all_sizes:
        return ""

    # Find the dominant body font size (most frequent)
    size_counts = Counter(round(s, 1) for s in all_sizes)
    body_size = size_counts.most_common(1)[0][0]

    # Count bold lines to decide strategy
    total_lines = sum(len(sp) for sp in page_spans)
    bold_lines = sum(1 for sp in page_spans for _, _, b in sp if b)
    bold_ratio = bold_lines / total_lines if total_lines else 0

    # Bold is a heading signal if bold lines are a minority (<40% of total)
    use_bold_as_heading = 0.02 < bold_ratio < 0.40

    out_lines: list[str] = []
    for page_span_list in page_spans:
        for avg_size, text, is_bold in page_span_list:
            # Determine if this line is a heading
            is_larger = avg_size > body_size + 1.0
            is_heading = False

            if is_larger and len(text) < 120:
                is_heading = True
            elif use_bold_as_heading and is_bold and len(text) < 120:
                # Skip bold definitions: lines starting with a quoted term
                starts_with_def = text.startswith('"') or text.startswith('\u201c')
                # Skip schedule references, party placeholders, dates
                is_schedule = text.startswith("Schedule ")
                is_placeholder = "[" in text and "]" in text
                is_fragment = text.endswith((",", ";"))

                # ALL CAPS sentence fragments (mid-paragraph disclaimers)
                is_caps_sentence = text.isupper() and len(text.split()) > 10
                # Lines ending with punctuation typical of mid-sentence content
                ends_like_sentence = text.endswith((".", ":", '"', "\u201d", ")", ";"))

                if starts_with_def or is_schedule or is_placeholder or is_fragment or is_caps_sentence:
                    is_heading = False
                else:
                    words = text.split()
                    looks_like_heading = (
                        (len(words) <= 10 and not ends_like_sentence)
                        or (text.isupper() and len(words) <= 8)
                        or bool(ALL_CAPS_RE.match(text))
                    )
                    if looks_like_heading:
                        is_heading = True

            if is_heading:
                if avg_size > body_size + 3.0:
                    depth = 1
                elif avg_size > body_size + 1.0:
                    depth = 2
                else:
                    depth = 3
                out_lines.append(f"{'#' * depth} {text}")
            else:
                out_lines.append(text)

    return "\n".join(out_lines).strip()


def extract_text_from_pdf_bytes(content: bytes) -> ExtractedDocument:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for PDF ingestion. Install dependency `pymupdf`.") from exc

    doc = fitz.open(stream=content, filetype="pdf")
    text = _extract_structured_from_pdf(doc)
    if not text.strip():
        # Fallback: plain text extraction
        pages_text = [page.get_text("text") for page in doc]
        text = _promote_to_markdown("\n".join(pages_text))
    return ExtractedDocument(text=text, char_count=len(text), page_count=len(doc))


def extract_text_from_text_bytes(content: bytes) -> ExtractedDocument:
    raw = content.decode("utf-8", errors="ignore")
    text = _promote_to_markdown(raw)
    return ExtractedDocument(text=text, char_count=len(text), page_count=1)

