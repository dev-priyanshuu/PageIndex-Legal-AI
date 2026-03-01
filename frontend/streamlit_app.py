from __future__ import annotations

import json
import os
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # loads .env when running locally; no-op on HF Spaces / Streamlit Cloud

# ──────────────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PageIndex Legal AI",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }

    /* ── Tab bar: force labels visible in all themes ── */
    [data-testid="stTabs"] [role="tab"],
    [data-testid="stTabs"] button[role="tab"],
    [data-testid="stTab"] button,
    [data-testid="stTab"] {
        color: #ccd6f6 !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        background: transparent !important;
        opacity: 1 !important;
    }
    [data-testid="stTabs"] [role="tab"]:hover,
    [data-testid="stTabs"] button[role="tab"]:hover {
        color: #ffffff !important;
    }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"],
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        color: #58a6ff !important;
        font-weight: 700 !important;
    }
    /* Tab panel spacing */
    [data-testid="stTabsContent"] { padding-top: 0.5rem; }

    /* ── Metric cards ── */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 16px 20px;
    }
    div[data-testid="stMetric"] label { color: #a8b2d1 !important; font-size: 0.8rem; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #ccd6f6 !important; }

    /* ── Severity colours ── */
    .severity-critical { color: #ff1744; font-weight: 700; }
    .severity-high     { color: #ff6d00; font-weight: 600; }
    .severity-medium   { color: #ffc400; }
    .severity-low      { color: #00c853; }

    /* ── Pipeline / tree cards ── */
    .pipeline-step {
        background: #161b22;
        border-left: 3px solid #58a6ff;
        padding: 12px 16px;
        margin: 6px 0;
        border-radius: 0 8px 8px 0;
        color: #e6edf3;
    }
    .tree-node {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 4px 0;
        font-family: monospace;
        font-size: 0.85rem;
        color: #e6edf3;
    }
    .party-buyer  { border-left: 4px solid #58a6ff; padding-left: 12px; margin: 4px 0; }
    .party-seller { border-left: 4px solid #f78166; padding-left: 12px; margin: 4px 0; }

    /* ── Document tree visualizer ── */
    .tree-root {
        border-left: 3px solid #58a6ff;
        padding-left: 12px;
        margin: 2px 0 2px 0;
    }
    .tree-l1 { margin-left: 0px; }
    .tree-l2 { margin-left: 20px; }
    .tree-l3 { margin-left: 40px; }
    .tree-l4 { margin-left: 60px; }
    .tree-l5 { margin-left: 80px; }
    .tree-l6 { margin-left: 100px; }
    .node-title-l1 {
        font-size: 1.0rem; font-weight: 700; color: #58a6ff;
        background: #0d1117; border: 1px solid #1f6feb;
        border-radius: 6px; padding: 8px 14px; margin: 3px 0;
        display: flex; align-items: center; gap: 8px;
    }
    .node-title-l2 {
        font-size: 0.92rem; font-weight: 600; color: #ccd6f6;
        background: #161b22; border: 1px solid #21262d;
        border-radius: 6px; padding: 6px 12px; margin: 2px 0;
        display: flex; align-items: center; gap: 8px;
    }
    .node-title-l3 {
        font-size: 0.86rem; font-weight: 500; color: #8b949e;
        background: #0d1117; border: 1px solid #161b22;
        border-radius: 4px; padding: 5px 10px; margin: 2px 0;
        display: flex; align-items: center; gap: 8px;
    }
    .node-title-deep {
        font-size: 0.82rem; color: #6e7681;
        padding: 4px 10px; margin: 1px 0;
        display: flex; align-items: center; gap: 8px;
    }
    .node-badge {
        font-size: 0.7rem; background: #1f6feb22; color: #58a6ff;
        border: 1px solid #1f6feb55; border-radius: 10px;
        padding: 1px 7px; margin-left: auto; white-space: nowrap;
    }
    .node-preview {
        font-size: 0.78rem; color: #6e7681; font-style: italic;
        padding: 3px 10px 6px 10px; margin-top: -2px;
        border-left: 2px solid #21262d; margin-left: 14px;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────
SEVERITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
SEVERITY_CLASS = {"critical": "severity-critical", "high": "severity-high", "medium": "severity-medium", "low": "severity-low"}

# ──────────────────────────────────────────────────────────────────────────────
# API helpers
# ──────────────────────────────────────────────────────────────────────────────

def post_json(base_url: str, path: str, payload: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    r = requests.post(f"{base_url}{path}", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def post_file(base_url: str, path: str, data: dict[str, str], file_name: str, file_bytes: bytes, mime: str, timeout: int = 300) -> dict[str, Any]:
    r = requests.post(f"{base_url}{path}", data=data, files={"file": (file_name, file_bytes, mime)}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_json(base_url: str, path: str, timeout: int = 15) -> dict[str, Any]:
    r = requests.get(f"{base_url}{path}", timeout=timeout)
    r.raise_for_status()
    return r.json()


def ask_legal(base_url: str, doc_id: str, question: str, retriever: str, execution: str, provider: str, model: str, session: str, top_k: int) -> dict[str, Any]:
    return post_json(base_url, "/qa/ask", {
        "document_id": doc_id, "question": question, "retriever_mode": retriever,
        "execution_mode": execution, "llm_provider": provider,
        "llm_model": model if provider == "gemini" else None,
        "session_id": session, "top_k": top_k,
    }, timeout=120)


def fetch_document_tree(base_url: str, doc_id: str) -> dict[str, Any]:
    r = requests.get(f"{base_url}/documents/tree", params={"document_id": doc_id}, timeout=15)
    r.raise_for_status()
    return r.json()

# ──────────────────────────────────────────────────────────────────────────────
# Reusable render components
# ──────────────────────────────────────────────────────────────────────────────

def _to_dict(item: Any) -> dict[str, Any]:
    """Ensure an item is a dict (guards against stale session state with strings)."""
    if isinstance(item, dict):
        return item
    return {}


def render_risk_panel(risks: list[Any]) -> None:
    risks = [_to_dict(r) for r in risks if isinstance(r, dict)]
    if not risks:
        st.success("No risks detected.")
        return
    counts: dict[str, int] = {}
    for r in risks:
        s = r.get("severity", "medium")
        counts[s] = counts.get(s, 0) + 1
    cols = st.columns(4)
    for i, sev in enumerate(["critical", "high", "medium", "low"]):
        with cols[i]:
            st.metric(f"{SEVERITY_EMOJI.get(sev, '')} {sev.title()}", counts.get(sev, 0))

    for risk in risks:
        sev = risk.get("severity", "medium")
        emoji = SEVERITY_EMOJI.get(sev, "⚪")
        cls = SEVERITY_CLASS.get(sev, "")
        cat = risk.get("category", "")
        desc = risk.get("description", "")
        clause = risk.get("clause_reference", "")
        party = risk.get("affected_party", "")
        interacts = risk.get("interacts_with", [])
        ref = f" — _{clause}_" if clause else ""
        party_tag = f" <span style='color:#8b949e;'>[{party}]</span>" if party else ""
        dep_tag = ""
        if interacts:
            dep_tag = f"<br/><span style='color:#58a6ff;font-size:0.78rem;'>↔ Interacts with: {', '.join(interacts)}</span>"
        st.markdown(
            f"<p>{emoji} <span class='{cls}'><b>{cat}</b> ({sev.upper()})</span>"
            f"{party_tag}{ref}<br/>{desc}{dep_tag}</p>",
            unsafe_allow_html=True,
        )


def render_tensions(tensions: list[dict[str, Any]], risk_score: float = 0.0) -> None:
    if risk_score > 0:
        score_color = "#ff1744" if risk_score >= 60 else "#ff6d00" if risk_score >= 30 else "#ffc400"
        st.markdown(
            f"<div style='background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #0f3460;"
            f"border-radius:12px;padding:16px 20px;margin-bottom:16px;'>"
            f"<span style='color:#a8b2d1;font-size:0.8rem;'>Aggregate Risk Score</span><br/>"
            f"<span style='color:{score_color};font-size:2rem;font-weight:700;'>{risk_score:.0f}</span>"
            f"<span style='color:#8b949e;font-size:1rem;'> / 100</span></div>",
            unsafe_allow_html=True,
        )
    if not tensions:
        st.success("No structural clause tensions detected.")
        return
    type_icons = {
        "undermines": "💥", "contradiction": "⚡", "limitation": "🔒",
        "gap": "🕳️", "missing_dependency": "🔗", "interaction": "↔️", "constraint": "📎",
    }
    for t in tensions:
        icon = type_icons.get(t.get("tension_type", ""), "⚠️")
        sev = t.get("severity", "medium")
        cls = SEVERITY_CLASS.get(sev, "")
        src = t.get("source_clause", "").replace("_", " ").title()
        tgt = t.get("target_clause", "").replace("_", " ").title()
        desc = t.get("description", "")
        st.markdown(
            f"<div class='pipeline-step'>{icon} <span class='{cls}'><b>{src}</b> → <b>{tgt}</b></span> "
            f"<span style='color:#8b949e;'>({t.get('tension_type', '')})</span><br/>{desc}</div>",
            unsafe_allow_html=True,
        )


def render_party(pa: dict[str, Any] | None) -> None:
    if not pa:
        return
    adv = pa.get("advantage", "unclear")
    labels = {"buyer": "🛡️ Buyer Favored", "seller": "⚔️ Seller Favored", "balanced": "⚖️ Balanced", "unclear": "❓ Unclear"}
    st.markdown(f"#### {labels.get(adv, '❓')}")
    st.caption(pa.get("summary", ""))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Buyer Protections**")
        for p in pa.get("buyer_protections", []):
            st.markdown(f"<div class='party-buyer'>{p}</div>", unsafe_allow_html=True)
        if not pa.get("buyer_protections"):
            st.warning("None found")
    with c2:
        st.markdown("**Seller Protections**")
        for p in pa.get("seller_protections", []):
            st.markdown(f"<div class='party-seller'>{p}</div>", unsafe_allow_html=True)
        if not pa.get("seller_protections"):
            st.warning("None found")


def render_negotiation(suggestions: list[dict[str, Any]]) -> None:
    if not suggestions:
        st.info("No negotiation points generated.")
        return
    for s in suggestions:
        with st.expander(f"📋 {s.get('issue', 'Issue')}", expanded=False):
            st.markdown(f"**Recommendation:** {s.get('suggestion', '')}")
            fb = s.get("fallback_position", "")
            if fb:
                st.markdown(f"**Fallback:** {fb}")


def render_evidence(response: dict[str, Any]) -> None:
    evidences = response.get("evidences", [])
    if not evidences:
        st.info("No evidence retrieved.")
        return
    for ev in evidences:
        score = ev.get("score", 0)
        path = ev.get("heading_path", "")
        excerpt = ev.get("excerpt", "")
        bar_width = min(int(score * 30), 100)
        st.markdown(
            f"<div class='tree-node'>"
            f"<b>{path}</b> <span style='color:#58a6ff;'>({score:.3f})</span><br/>"
            f"<div style='background:#21262d;border-radius:4px;margin:6px 0;'>"
            f"<div style='background:#238636;height:4px;width:{bar_width}%;border-radius:4px;'></div></div>"
            f"<span style='color:#8b949e;font-size:0.8rem;'>{excerpt[:200]}</span></div>",
            unsafe_allow_html=True,
        )


def render_trace(trace: list[str]) -> None:
    for i, step in enumerate(trace, 1):
        st.markdown(f"<div class='pipeline-step'><b>Step {i}:</b> {step}</div>", unsafe_allow_html=True)


def render_jurisdiction(jur: dict[str, Any] | None) -> None:
    if not jur:
        st.info("Jurisdiction information not available.")
        return
    name = jur.get("detected_jurisdiction", "Unknown")
    flag = {"New York": "🗽", "Delaware": "🏛️", "California": "🌴",
            "England & Wales": "🇬🇧", "India": "🇮🇳"}.get(name, "🌍")
    st.markdown(f"#### {flag} {name}")
    notes = jur.get("jurisdiction_notes", [])
    for note in notes:
        st.markdown(f"<div class='pipeline-step'>{note}</div>", unsafe_allow_html=True)

    missing = jur.get("missing_mandatory_provisions", [])
    if missing:
        st.warning(f"Missing mandatory provisions under {name} law: **{', '.join(missing)}**")

    adjustments = jur.get("severity_adjustments", [])
    if adjustments:
        st.markdown("**Jurisdiction-adjusted severities:**")
        for adj in adjustments:
            orig = adj.get("original_severity", "")
            new = adj.get("adjusted_severity", "")
            cat = adj.get("category", "")
            reason = adj.get("reason", "")
            arrow = "⬆️" if new in ("critical",) and orig != "critical" else "⬇️" if orig == "critical" and new != "critical" else "➡️"
            st.markdown(
                f"<div class='tree-node'>{arrow} <b>{cat}</b>: {orig.upper()} → {new.upper()}<br/>"
                f"<span style='color:#8b949e;font-size:0.8rem;'>{reason[:200]}</span></div>",
                unsafe_allow_html=True,
            )

    jur_risks = jur.get("jurisdiction_risks", [])
    if jur_risks:
        st.markdown("**Jurisdiction-specific risks:**")
        for jr in jur_risks:
            sev = jr.get("severity", "medium")
            emoji = SEVERITY_EMOJI.get(sev, "⚪")
            cls = SEVERITY_CLASS.get(sev, "")
            st.markdown(
                f"<p>{emoji} <span class='{cls}'><b>{jr.get('category', '')}</b> ({sev.upper()})</span>"
                f"<br/>{jr.get('description', '')}</p>",
                unsafe_allow_html=True,
            )


def render_simulation(scenarios: list[dict[str, Any]], portfolio: dict[str, Any]) -> None:
    if not scenarios:
        st.info("No simulation data available.")
        return

    pp = portfolio.get("purchase_price", 0)
    el = portfolio.get("expected_loss", 0)
    wc = portfolio.get("worst_case_exposure", 0)
    mv = portfolio.get("mitigation_value", 0)
    ratio = portfolio.get("risk_to_price_ratio", 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Purchase Price", f"${pp:,.0f}")
    with c2:
        st.metric("Expected Loss", f"${el:,.0f}", delta=f"{ratio:.1%} of deal")
    with c3:
        st.metric("Worst-Case Exposure", f"${wc:,.0f}")
    with c4:
        st.metric("Mitigation Value", f"${mv:,.0f}", delta="if all amendments adopted")

    st.markdown("---")
    st.markdown("**Risk Scenarios (sorted by severity × probability)**")

    for s in scenarios:
        sev = s.get("severity", "medium")
        emoji = SEVERITY_EMOJI.get(sev, "⚪")
        cls = SEVERITY_CLASS.get(sev, "")
        cat = s.get("risk_category", "")
        prob = s.get("probability", 0)
        prob_label = s.get("probability_label", "")
        impact_label = s.get("financial_impact_label", "")
        impact_m = s.get("financial_impact_multiple", 0)
        worst = s.get("worst_case", "")
        mitigation = s.get("mitigation_suggestion", "")
        residual = s.get("residual_risk_after_mitigation", 0)
        impact_dollars = pp * impact_m

        with st.expander(
            f"{emoji} {cat} — Prob: {prob:.0%} ({prob_label}) | Impact: {impact_label} (~${impact_dollars:,.0f})",
            expanded=False,
        ):
            c_a, c_b = st.columns(2)
            with c_a:
                st.metric("Probability", f"{prob:.0%}", help="Likelihood of this risk materialising")
                st.metric("Financial Impact", f"${impact_dollars:,.0f}", help=f"{impact_m:.1f}x Purchase Price")
            with c_b:
                st.metric("Residual Risk (post-mitigation)", f"{residual:.0%}")
                st.metric("Severity", sev.upper())

            st.markdown(f"**Worst-case scenario:** {worst}")
            st.markdown(f"**Recommended mitigation:** {mitigation}")

def render_document_tree(tree_data: dict[str, Any]) -> None:
    """
    Render the full document tree as an interactive, indented hierarchy.
    Each node shows its title, depth, content length, and a collapsible preview.
    """
    nodes: dict[str, Any] = tree_data.get("nodes", {})
    root_ids: list[str] = tree_data.get("root_ids", [])
    doc_title = tree_data.get("title", "Document")
    node_count = tree_data.get("node_count", 0)
    max_depth = tree_data.get("max_depth", 0)
    metadata = tree_data.get("metadata", {})

    if not nodes:
        st.warning("No tree nodes found. Try re-ingesting the document.")
        return

    # ── Summary metrics ──
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Nodes", node_count)
    with m2:
        st.metric("Tree Depth", max_depth + 1)
    with m3:
        st.metric("Root Sections", len(root_ids))
    with m4:
        mode = metadata.get("tree_generation_mode", "local")
        st.metric("Built With", mode.upper())

    # ── Metadata strip ──
    meta_parts = []
    if metadata.get("jurisdiction"):
        meta_parts.append(f"📍 {metadata['jurisdiction']}")
    if metadata.get("deal_type"):
        meta_parts.append(f"📑 {metadata['deal_type']}")
    if metadata.get("source_file"):
        meta_parts.append(f"📄 {metadata['source_file']}")
    if meta_parts:
        st.caption("  ·  ".join(meta_parts))

    st.markdown("---")

    # ── Level icons and colours ──
    LEVEL_ICONS = ["📘", "📗", "📄", "🔹", "▸", "·"]
    LEVEL_CLASSES = ["node-title-l1", "node-title-l2", "node-title-l3",
                     "node-title-deep", "node-title-deep", "node-title-deep"]
    INDENT_CLASSES = ["tree-l1", "tree-l2", "tree-l3", "tree-l4", "tree-l5", "tree-l6"]

    # ── Controls ──
    ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 2])
    with ctrl1:
        show_previews = st.checkbox("Show content previews", value=True, key="tree_previews")
    with ctrl2:
        filter_text = st.text_input("Filter nodes", placeholder="e.g. warranty, payment…", key="tree_filter", label_visibility="collapsed")
    with ctrl3:
        min_content = st.checkbox("Only nodes with content", value=False, key="tree_content_only")

    filter_lower = filter_text.strip().lower()

    # ── Recursive renderer ──
    def _render_node(node_id: str) -> None:
        node = nodes.get(node_id)
        if node is None:
            return

        title: str = node.get("title", "Untitled")
        level: int = node.get("level", 1)
        preview: str = node.get("content_preview", "")
        content_len: int = node.get("content_length", 0)
        children: list[str] = node.get("children", [])
        heading_path: str = node.get("heading_path", title)

        # Apply filters
        if filter_lower and filter_lower not in title.lower() and filter_lower not in preview.lower():
            # Still recurse so children can match
            for child_id in children:
                _render_node(child_id)
            return
        if min_content and content_len == 0 and not children:
            return

        depth_idx = min(level - 1, len(LEVEL_ICONS) - 1)
        icon = LEVEL_ICONS[depth_idx]
        title_cls = LEVEL_CLASSES[depth_idx]
        indent_cls = INDENT_CLASSES[depth_idx]

        # Badge: show content length or child count
        if children:
            badge = f"{len(children)} sub-section{'s' if len(children) != 1 else ''}"
        elif content_len > 0:
            badge = f"{content_len:,} chars"
        else:
            badge = "empty"

        st.markdown(
            f"<div class='{indent_cls}'>"
            f"<div class='{title_cls}'>"
            f"{icon} {title}"
            f"<span class='node-badge'>{badge}</span>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Content preview (indented under the title)
        if show_previews and preview.strip() and content_len > 0:
            preview_text = preview[:220].replace("\n", " ").strip()
            if len(preview) > 220:
                preview_text += "…"
            st.markdown(
                f"<div class='{indent_cls}'>"
                f"<div class='node-preview'>{preview_text}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # Recurse into children
        for child_id in children:
            _render_node(child_id)

    # ── Walk from roots ──
    for root_id in root_ids:
        _render_node(root_id)

    # ── Raw JSON export ──
    st.markdown("---")
    with st.expander("📥 Export Tree as JSON", expanded=False):
        st.download_button(
            label="Download tree.json",
            data=json.dumps(tree_data, indent=2),
            file_name=f"{tree_data.get('document_id', 'doc')}-tree.json",
            mime="application/json",
        )
        st.json(tree_data, expanded=False)


# ──────────────────────────────────────────────────────────────────────────────
# Session state  (version-stamped so stale data from old UI runs is cleared)
# ──────────────────────────────────────────────────────────────────────────────
_UI_VERSION = "v6"
if st.session_state.get("_ui_version") != _UI_VERSION:
    for _k in ["chat_history", "latest_benchmark", "latest_compare", "ingested_docs",
               "last_ingested_doc_id", "cached_trees"]:
        st.session_state.pop(_k, None)
    st.session_state["_ui_version"] = _UI_VERSION

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "latest_benchmark" not in st.session_state:
    st.session_state.latest_benchmark = None
if "latest_compare" not in st.session_state:
    st.session_state.latest_compare = None
if "ingested_docs" not in st.session_state:
    st.session_state.ingested_docs = []
if "last_ingested_doc_id" not in st.session_state:
    st.session_state.last_ingested_doc_id = ""
if "cached_trees" not in st.session_state:
    st.session_state.cached_trees = {}

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.shields.io/badge/Powered_by-PageIndex-blue?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTMgM2gxOHYxOEgzeiIgZmlsbD0ibm9uZSIvPjxwYXRoIGQ9Ik0xMiAyTDQgN3YxMGw4IDUgOC01VjdsLTgtNXoiIGZpbGw9IiNmZmYiLz48L3N2Zz4=", width=220)

    # ── Navigation (top) ──
    st.markdown("### Navigation")
    page = st.radio(
        "Go to",
        ["🏠 Overview", "📥 Ingest", "⚖️ Legal Analysis", "🔬 Tree vs Vector", "📊 Benchmark", "🛡️ Audit", "⚙️ System"],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()

    # ── Backend URL resolution (never shown to the user) ──────────────────────
    # Priority order:
    #   1. Streamlit Cloud  → App Settings → Secrets → BACKEND_URL
    #   2. HF Spaces Docker → supervisor sets BACKEND_URL=http://localhost:8000
    #   3. Local .env       → BACKEND_URL=http://127.0.0.1:8000
    #   4. Hardcoded        → http://127.0.0.1:8000
    try:
        base_url = st.secrets["BACKEND_URL"]
    except (FileNotFoundError, KeyError):
        base_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    base_url = base_url.rstrip("/")

    backend_ok = False
    sys_info: dict[str, Any] = {}
    try:
        sys_info = get_json(base_url, "/health")
        backend_ok = True
        pi_ready = sys_info.get("pageindex_available") == "True"
        st.success("Backend connected")
    except Exception:
        st.error("Backend unreachable")
        pi_ready = False

    st.divider()
    st.markdown("##### Gemini LLM")
    llm_provider = st.selectbox("Provider", ["gemini", "mock"], index=0)
    llm_model = st.selectbox("Model", [
        "models/gemini-2.5-flash", "gemini-2.5-flash",
        "models/gemini-2.5-pro", "gemini-2.5-pro",
        "models/gemini-2.0-flash-001", "gemini-2.0-flash-001",
    ], index=0)

    st.divider()
    st.markdown("##### Tree Generation")
    tree_mode = st.selectbox("Mode", ["auto", "pageindex", "local"], index=0,
        help="auto = PageIndex if available, else local | pageindex = LLM-powered | local = regex/font")
    if backend_ok:
        st.caption(f"{'🟢' if pi_ready else '🔴'} PageIndex: {'Ready' if pi_ready else 'Needs GEMINI_API_KEY'}")

    st.divider()
    st.markdown("##### Retrieval")
    retriever_mode = st.radio("Retriever", ["tree", "vector"], index=0, horizontal=True)
    execution_mode = st.radio("Execution", ["graph", "sequential"], index=0, horizontal=True)
    top_k = st.slider("Top K evidence", 1, 10, 6)
    session_id = st.text_input("Session", value="session-1")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 0 — Overview / Architecture
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Overview":
    st.markdown("# 🌲 PageIndex Legal AI")
    st.markdown("##### Vectorless, Reasoning-Based RAG for Legal Document Understanding")
    st.markdown("---")

    st.markdown("### How It Works")
    st.markdown("""
> Traditional RAG: **PDF → Chunks → Embeddings → Vector DB → Similarity Search**
>
> PageIndex RAG: **PDF → LLM-Powered Tree Index → Reasoning-Based Retrieval → Legal Agents**
""")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Tree Generation", "Gemini LLM")
    with c2:
        st.metric("Risk Ontology", "20 Clause Types")
    with c3:
        st.metric("Jurisdictions", "5 Profiles")
    with c4:
        st.metric("Simulation", "Portfolio Risk")

    st.markdown("---")
    st.markdown("### Pipeline Architecture")

    steps = [
        ("📄 PDF Upload", "Legal document uploaded (SPA, LOI, contracts)"),
        ("🌲 PageIndex Tree Generation", "Gemini builds hierarchical TOC tree with node summaries — no chunking"),
        ("🔍 Reasoning-Based Retrieval", "LLM reasons over tree structure to find relevant sections — no vector similarity"),
        ("🤖 Legal Agent Layer", "Ontology-driven risk detection (20 clause types) + Verification + Party Analysis + Drafting"),
        ("🔗 Clause Dependency Graph", "12-edge graph detects undermines, contradictions, and gaps between interacting clauses"),
        ("🌍 Jurisdiction Engine", "5 jurisdiction profiles (NY, DE, CA, UK, India) — adjusts severity and adds mandatory provisions"),
        ("📈 Risk Simulation", "Per-risk probability × financial impact scenarios + portfolio expected loss and worst-case exposure"),
        ("💎 Gemini Legal Reasoning", "Senior counsel-grade analysis with jurisdiction context and clause interdependency analysis"),
        ("📊 Explainable Response", "Severity-rated risks, clause tensions, jurisdiction analysis, risk simulation, negotiation strategy"),
    ]
    for title, desc in steps:
        st.markdown(f"<div class='pipeline-step'><b>{title}</b><br/><span style='color:#8b949e;'>{desc}</span></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Why PageIndex Beats Vector Search")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### ❌ Vector RAG Problems")
        st.markdown("""
- Arbitrary chunking destroys clause context
- Similarity ≠ Relevance
- No heading hierarchy awareness
- Opaque retrieval ("vibe search")
- Cannot trace reasoning path
""")
    with col2:
        st.markdown("#### ✅ PageIndex Advantages")
        st.markdown("""
- Natural document sections preserved
- LLM reasons to find relevant nodes
- Full heading path traceability
- Hierarchical clause dependency
- Explainable, auditable retrieval
""")

    st.markdown("---")
    st.markdown("### Tech Stack")
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        st.markdown("**Tree Engine**\n\n[VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex)")
    with t2:
        st.markdown("**LLM**\n\nGoogle Gemini 2.5")
    with t3:
        st.markdown("**Backend**\n\nFastAPI + Pydantic")
    with t4:
        st.markdown("**Frontend**\n\nStreamlit")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Ingest
# ══════════════════════════════════════════════════════════════════════════════
if page == "📥 Ingest":
    st.markdown("## 📥 Document Ingestion")
    st.caption("Upload legal PDFs and build a PageIndex tree structure using Gemini")
    st.markdown("---")

    ingest_tab, tree_tab = st.tabs(["📤 Upload & Ingest", "🌲 Document Tree"])

    # ── Tab 1: Upload ──────────────────────────────────────────────────────────
    with ingest_tab:
        col_sample, col_upload = st.columns([1, 2])

        with col_sample:
            st.markdown("#### Quick Start")
            st.markdown("Load the built-in sample SPA to try the system instantly.")
            if st.button("🚀 Ingest Sample SPA", use_container_width=True):
                try:
                    result = post_json(base_url, "/documents/ingest_sample", {})
                    st.session_state.ingested_docs.append(result)
                    st.session_state.last_ingested_doc_id = result.get("document_id", "sample-spa-v1")
                    st.session_state.cached_trees.pop(st.session_state.last_ingested_doc_id, None)
                    st.success(f"Sample ingested — **{result.get('node_count', 0)}** nodes")
                    st.info("Switch to the **🌲 Document Tree** tab to explore the structure.")
                except Exception as exc:
                    st.error(str(exc))

        with col_upload:
            st.markdown("#### Upload Legal Document")
            with st.form("upload_form"):
                uf1, uf2 = st.columns(2)
                with uf1:
                    document_id = st.text_input("Document ID", value="rubicon-agro-v1")
                    jurisdiction = st.text_input("Jurisdiction", value="USA")
                with uf2:
                    title = st.text_input("Title", value="Purchase Agreement - Rubicon Agriculture AgroBox")
                    deal_type = st.text_input("Deal Type", value="Purchase Agreement")
                uploaded_file = st.file_uploader("Choose PDF or TXT file", type=["pdf", "txt"])

                tm_display = {
                    "auto": "🤖 Auto (PageIndex if available)",
                    "pageindex": "🌲 PageIndex (Gemini-powered)",
                    "local": "📄 Local (regex/font)",
                }
                st.info(f"Tree generation: **{tm_display.get(tree_mode, tree_mode)}**")
                submit = st.form_submit_button("📤 Upload & Build Tree", use_container_width=True, type="primary")

            if submit:
                if uploaded_file is None:
                    st.warning("Select a file first.")
                else:
                    try:
                        with st.spinner(f"Building tree with **{tree_mode}** mode…"):
                            result = post_file(
                                base_url, "/documents/ingest_file",
                                data={
                                    "document_id": document_id, "title": title,
                                    "jurisdiction": jurisdiction, "deal_type": deal_type,
                                    "tree_mode": tree_mode,
                                },
                                file_name=uploaded_file.name,
                                file_bytes=uploaded_file.getvalue(),
                                mime=uploaded_file.type or "application/octet-stream",
                            )
                        st.session_state.ingested_docs.append(result)
                        st.session_state.last_ingested_doc_id = document_id
                        st.session_state.cached_trees.pop(document_id, None)

                        gen = result.get("tree_generation_mode", "?")
                        node_cnt = result.get("node_count", 0)
                        chars = result.get("extracted_chars", 0)

                        st.success(f"Ingested using **{gen}** mode — **{node_cnt}** nodes built")
                        m1, m2, m3 = st.columns(3)
                        with m1:
                            st.metric("Tree Nodes", node_cnt)
                        with m2:
                            st.metric("Characters", f"{chars:,}")
                        with m3:
                            st.metric("Engine", gen.upper())
                        st.info("Switch to the **🌲 Document Tree** tab to explore the structure.")
                    except Exception as exc:
                        st.error(str(exc))

        if st.session_state.ingested_docs:
            st.markdown("---")
            st.markdown("#### Session History")
            for doc in reversed(st.session_state.ingested_docs[-6:]):
                did = doc.get("document_id", "?")
                is_active = did == st.session_state.last_ingested_doc_id
                border_color = "#1f6feb" if is_active else "#21262d"
                st.markdown(
                    f"<div class='tree-node' style='border-color:{border_color};'>"
                    f"{'🟢' if is_active else '⚪'} <b>{did}</b> — "
                    f"{doc.get('node_count', '?')} nodes | "
                    f"{doc.get('tree_generation_mode', doc.get('message', ''))}"
                    f"{'  ← active' if is_active else ''}</div>",
                    unsafe_allow_html=True,
                )

    # ── Tab 2: Tree Viewer ─────────────────────────────────────────────────────
    with tree_tab:
        st.markdown("### 🌲 Document Tree Explorer")
        st.caption("Visual hierarchy of every section and clause extracted from the document")

        tc1, tc2 = st.columns([3, 1])
        with tc1:
            view_doc_id = st.text_input(
                "Document ID to view",
                value=st.session_state.last_ingested_doc_id or "rubicon-agro-v1",
                key="tree_view_doc_id",
            )
        with tc2:
            st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            load_tree = st.button("🔍 Load Tree", use_container_width=True, type="primary")

        if load_tree and view_doc_id:
            with st.spinner("Fetching document tree…"):
                try:
                    tree_data = fetch_document_tree(base_url, view_doc_id)
                    st.session_state.cached_trees[view_doc_id] = tree_data
                except Exception as exc:
                    st.error(f"Could not load tree: {exc}")

        # Auto-load tree right after ingestion
        if (
            st.session_state.last_ingested_doc_id
            and st.session_state.last_ingested_doc_id not in st.session_state.cached_trees
        ):
            try:
                tree_data = fetch_document_tree(base_url, st.session_state.last_ingested_doc_id)
                st.session_state.cached_trees[st.session_state.last_ingested_doc_id] = tree_data
            except Exception:
                pass

        # Render cached tree
        display_id = view_doc_id or st.session_state.last_ingested_doc_id
        if display_id and display_id in st.session_state.cached_trees:
            cached = st.session_state.cached_trees[display_id]
            st.markdown(f"#### 📄 {cached.get('title', display_id)}")
            render_document_tree(cached)
        elif not st.session_state.ingested_docs:
            st.info("No documents ingested yet. Go to **📤 Upload & Ingest** to get started.")
        else:
            st.info("Enter a Document ID above and click **🔍 Load Tree**.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Legal Analysis (Q&A)
# ══════════════════════════════════════════════════════════════════════════════
if page == "⚖️ Legal Analysis":
    st.markdown("## ⚖️ Legal Contract Analysis")
    st.caption("Ask legal questions — get severity-rated risks, party analysis, and negotiation strategy")
    st.markdown("---")

    with st.form("qa_form"):
        qc1, qc2 = st.columns([2, 1])
        with qc1:
            question = st.text_area(
                "Legal Question",
                value="What are key legal risks in this agreement and what should we amend?",
                height=100,
            )
        with qc2:
            qa_doc_id = st.text_input("Document ID", value="rubicon-agro-v1")
            st.caption(f"Retriever: **{retriever_mode}** | Execution: **{execution_mode}** | Model: **{llm_model}**")
        submit_qa = st.form_submit_button("🔍 Analyze Contract", width="stretch", type="primary")

    if submit_qa:
        try:
            with st.spinner("Gemini is analyzing the contract..."):
                result = ask_legal(base_url, qa_doc_id, question, retriever_mode, execution_mode, llm_provider, llm_model, session_id, top_k)
            st.session_state.chat_history.append({"question": question, "response": result})
        except Exception as exc:
            st.error(str(exc))

    if st.session_state.chat_history:
        for idx, item in enumerate(reversed(st.session_state.chat_history), 1):
            resp = item["response"]
            with st.expander(f"{'🟢' if idx == 1 else '⚪'} Q{idx}: {item['question'][:100]}", expanded=(idx == 1)):

                # -- Answer
                st.markdown("#### Gemini Analysis")
                st.markdown(resp.get("answer", ""))

                conf = resp.get("confidence", 0)
                st.progress(conf, text=f"Confidence: {conf:.0%}")
                st.caption(f"Model: `{resp.get('llm_model_used', '')}` | Mode: `{resp.get('execution_mode', '')}`")

                st.markdown("---")
                with st.expander("🔴 Risk Assessment", expanded=True):
                    render_risk_panel(resp.get("risks", []))
                with st.expander("🔗 Clause Dependencies", expanded=True):
                    render_tensions(resp.get("clause_tensions", []), resp.get("risk_score", 0.0))
                with st.expander("🌍 Jurisdiction Analysis", expanded=True):
                    render_jurisdiction(resp.get("jurisdiction_info"))
                with st.expander("📈 Risk Simulation", expanded=True):
                    render_simulation(resp.get("risk_scenarios", []), resp.get("portfolio_risk", {}))
                with st.expander("⚖️ Party Analysis", expanded=False):
                    render_party(resp.get("party_analysis"))
                with st.expander("📋 Negotiation Strategy", expanded=False):
                    render_negotiation(resp.get("suggestions", []))
                with st.expander("📎 Evidence Trail", expanded=False):
                    render_evidence(resp)
                with st.expander("🧠 Reasoning Trace", expanded=False):
                    render_trace(resp.get("reasoning_trace", []))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Tree vs Vector Comparison
# ══════════════════════════════════════════════════════════════════════════════
if page == "🔬 Tree vs Vector":
    st.markdown("## 🔬 Tree vs Vector — Side by Side")
    st.caption("Run the same question through both retrievers and compare results")
    st.markdown("---")

    cmp_doc = st.text_input("Document ID", value="rubicon-agro-v1", key="cmp_doc")
    cmp_question = st.text_area(
        "Question",
        value="What are key legal risks in this agreement and what should we amend?",
        height=80,
        key="cmp_q",
    )

    if st.button("⚡ Run Comparison", width="stretch", type="primary"):
        try:
            with st.spinner("Running tree retrieval..."):
                tree_resp = ask_legal(base_url, cmp_doc, cmp_question, "tree", execution_mode, llm_provider, llm_model, session_id, top_k)
            with st.spinner("Running vector retrieval..."):
                vec_resp = ask_legal(base_url, cmp_doc, cmp_question, "vector", execution_mode, llm_provider, llm_model, session_id, top_k)
            st.session_state.latest_compare = {"tree": tree_resp, "vector": vec_resp}
        except Exception as exc:
            st.error(str(exc))

    if st.session_state.latest_compare:
        cmp = st.session_state.latest_compare
        tree_r = cmp["tree"]
        vec_r = cmp["vector"]

        # KPI row
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("🌲 Tree Confidence", f"{tree_r.get('confidence', 0):.0%}")
        with k2:
            st.metric("📊 Vector Confidence", f"{vec_r.get('confidence', 0):.0%}")
        with k3:
            st.metric("🌲 Risks Found", len(tree_r.get("risks", [])))
        with k4:
            st.metric("📊 Risks Found", len(vec_r.get("risks", [])))

        st.markdown("---")
        left, right = st.columns(2)

        with left:
            st.markdown("### 🌲 Tree Retrieval (PageIndex)")
            st.markdown(tree_r.get("answer", "")[:1500])
            st.markdown("---")
            st.markdown("**Risk Assessment**")
            render_risk_panel(tree_r.get("risks", []))
            st.markdown("---")
            render_party(tree_r.get("party_analysis"))
            st.markdown("---")
            st.markdown("**Negotiation Strategy**")
            render_negotiation(tree_r.get("suggestions", []))
            st.markdown("---")
            st.markdown("**Evidence Trail**")
            render_evidence(tree_r)

        with right:
            st.markdown("### 📊 Vector Retrieval (TF-IDF)")
            st.markdown(vec_r.get("answer", "")[:1500])
            st.markdown("---")
            st.markdown("**Risk Assessment**")
            render_risk_panel(vec_r.get("risks", []))
            st.markdown("---")
            render_party(vec_r.get("party_analysis"))
            st.markdown("---")
            st.markdown("**Negotiation Strategy**")
            render_negotiation(vec_r.get("suggestions", []))
            st.markdown("---")
            st.markdown("**Evidence Trail**")
            render_evidence(vec_r)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — Benchmark
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Benchmark":
    st.markdown("## 📊 Retrieval Benchmark")
    st.caption("Quantitative evaluation — recall, citation accuracy, risk detection")
    st.markdown("---")

    bench_doc = st.text_input("Document ID", value="rubicon-agro-v1", key="bench_doc")
    bc1, bc2 = st.columns(2)

    with bc1:
        if st.button("▶️ Run Benchmark", width="stretch", type="primary"):
            try:
                with st.spinner("Evaluating both retrievers..."):
                    result = post_json(base_url, "/benchmark/run", {"document_id": bench_doc, "top_k": top_k})
                st.session_state.latest_benchmark = result
            except Exception as exc:
                st.error(str(exc))

    with bc2:
        if st.button("📝 Generate Report", width="stretch"):
            try:
                report = post_json(base_url, "/benchmark/report", {"document_id": bench_doc, "top_k": top_k})
                md = report.get("markdown_report", "")
                st.markdown(md)
                st.download_button("Download Report", data=md.encode(), file_name=f"{bench_doc}-report.md", mime="text/markdown", width="stretch")
            except Exception as exc:
                st.error(str(exc))

    if st.session_state.latest_benchmark:
        bm = st.session_state.latest_benchmark
        winner = bm.get("winner", "tree")

        st.markdown(f"### {'🌲 Tree Wins!' if winner == 'tree' else '📊 Vector Wins!'}")
        st.caption(bm.get("summary", ""))

        tree_m = bm.get("tree", {})
        vec_m = bm.get("vector", {})

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown("**Recall@K**")
            st.metric("🌲 Tree", tree_m.get("recall_at_k", 0))
            st.metric("📊 Vector", vec_m.get("recall_at_k", 0))
        with m2:
            st.markdown("**Citation Accuracy**")
            st.metric("🌲 Tree", tree_m.get("citation_path_accuracy", 0))
            st.metric("📊 Vector", vec_m.get("citation_path_accuracy", 0))
        with m3:
            st.markdown("**Risk Detection**")
            st.metric("🌲 Tree", tree_m.get("risk_detection_accuracy", 0))
            st.metric("📊 Vector", vec_m.get("risk_detection_accuracy", 0))

        coverage = bm.get("eval_case_coverage", 0)
        st.progress(coverage, text=f"Eval Case Coverage: {coverage:.0%}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — Audit
# ══════════════════════════════════════════════════════════════════════════════
if page == "🛡️ Audit":
    st.markdown("## 🛡️ Audit Trail")
    st.caption("Every action is logged — ingestion, queries, benchmarks")
    st.markdown("---")

    if st.button("🔄 Load Audit Events", width="stretch"):
        try:
            events = get_json(base_url, "/audit/events").get("events", [])
            if events:
                st.dataframe(events, width="stretch", height=400)
                st.download_button(
                    "Download Audit Log",
                    data=json.dumps(events, indent=2).encode(),
                    file_name="audit_log.json",
                    mime="application/json",
                    width="stretch",
                )
            else:
                st.info("No audit events yet. Ingest a document or run a query to generate events.")
        except Exception as exc:
            st.error(str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — System
# ══════════════════════════════════════════════════════════════════════════════
if page == "⚙️ System":
    st.markdown("## ⚙️ System Status")
    st.caption("Full system configuration and health")
    st.markdown("---")

    if backend_ok:
        try:
            info = get_json(base_url, "/system/info")
        except Exception:
            info = {}

        s1, s2, s3 = st.columns(3)
        with s1:
            st.metric("PageIndex Engine", "🟢 Ready" if info.get("pageindex_available") else "🔴 Not Available")
        with s2:
            st.metric("Tree Mode", info.get("tree_generation_mode", "?").upper())
        with s3:
            st.metric("LLM Provider", info.get("llm_provider", "?").upper())

        st.markdown("---")
        st.markdown("### Full Configuration")
        st.json(info)

        st.markdown("---")
        st.markdown("### Architecture Components")

        components = [
            ("VectifyAI/PageIndex", "LLM-powered hierarchical tree index generation", "vendor/PageIndex/"),
            ("Legal Ontology", "20 clause types, structured risk taxonomy with severity & party tags", "knowledge/legal_ontology.py"),
            ("Clause Dependency Graph", "12-edge graph: undermines, contradicts, limits_remedy, gap, requires, interacts", "knowledge/legal_ontology.py"),
            ("Jurisdiction Engine", "5 profiles (NY, DE, CA, UK, India) — severity adjustments + mandatory provisions", "knowledge/jurisdiction.py"),
            ("Risk Simulation Agent", "Per-risk probability × impact scenarios + portfolio expected loss analysis", "knowledge/risk_simulation.py"),
            ("Risk Detection Agent", "Ontology-driven, document-adaptive checks (only present clauses)", "agents/risk_detection.py"),
            ("Verification Agent", "Cross-checks 'missing clause' claims against actual document headings", "agents/verification.py"),
            ("Party Analysis Agent", "Buyer vs Seller protection scoring", "agents/party_analysis.py"),
            ("Drafting Agent", "Negotiation suggestions with fallback positions", "agents/drafting.py"),
            ("Gemini Integration", "Google Gemini 2.5 Flash/Pro for all LLM reasoning", "infra/llm.py"),
            ("Tree Retriever", "IDF-weighted, document-adaptive hierarchy-aware retrieval", "core/retrieval.py"),
            ("Vector Baseline", "TF-IDF flat-chunk retriever for comparison", "core/retrieval.py"),
            ("Graph Executor", "LangGraph-ready orchestration pipeline", "pipeline/graph_flow.py"),
            ("SQLite Storage", "Persistent document and tree storage", "infra/persistence.py"),
            ("Audit Logger", "Every action tracked with timestamps", "infra/audit.py"),
        ]
        for name, desc, path in components:
            st.markdown(f"<div class='pipeline-step'><b>{name}</b> <code>{path}</code><br/><span style='color:#8b949e;'>{desc}</span></div>", unsafe_allow_html=True)
    else:
        st.error("Cannot reach backend. Start it with: `uvicorn main:app --reload`")
