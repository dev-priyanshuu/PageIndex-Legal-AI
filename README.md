---
title: PageIndex Legal AI
emoji: 🌲
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
license: mit
short_description: Agentic legal AI — hierarchical tree retrieval, no vector DB
---

# Legal Agentic PageIndex RAG

Production-grade AI system for legal document understanding. Uses the real **[VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex)** library for hierarchical, reasoning-based retrieval — no vector database, no arbitrary chunking.

---

## Architecture

```
PDF Upload
    │
    ▼
core/ — Document Ingestion (PyMuPDF)
    │
    ▼
core/ — PageIndex Tree Generation (LLM-powered or local font/regex)
    │
    ▼
pipeline/ — GraphExecutor (LangGraph-ready orchestration)
    │
    ├── agents/understanding.py    → extract parties, jurisdiction, clause types
    ├── agents/risk_detection.py   → ontology-driven, document-adaptive risk scan
    ├── agents/verification.py     → cross-check claims against actual headings
    ├── agents/validation.py       → clause dependency graph + contradiction detection
    ├── agents/party_analysis.py   → Buyer vs Seller protection scoring
    ├── agents/drafting.py         → negotiation strategy with fallback positions
    ├── agents/explainability.py   → step-by-step reasoning trace
    ├── knowledge/jurisdiction.py  → 5-jurisdiction legal standards engine
    └── knowledge/risk_simulation.py → financial impact simulation
    │
    ▼
infra/llm.py — Google Gemini (full document + section outline prompt)
    │
    ▼
api/ — FastAPI response with risks, tensions, jurisdiction, simulation, trace
    │
    ▼
frontend/ — Streamlit executive dashboard
```

---

## Why This Beats Vector RAG

| Feature | Vector RAG | PageIndex RAG |
|---|---|---|
| Index structure | Flat embeddings | Hierarchical TOC tree (LLM-generated) |
| Retrieval | Cosine similarity | IDF-weighted, document-adaptive scoring |
| Chunking | Arbitrary splits | Natural document sections (headings) |
| Explainability | Opaque similarity scores | Traceable section paths + reasoning trace |
| Legal reasoning | Surface-level matching | Hierarchy-aware clause analysis |
| Risk detection | Generic keyword match | Ontology-driven, document-specific checks |
| Jurisdiction | None | 5 jurisdiction profiles (NY, DE, CA, UK, India) |
| Financial impact | None | Per-risk simulation with portfolio metrics |

---

## Project Structure

```
pageindex/
│
├── main.py                          ← root entry point (uvicorn main:app)
│
├── agents/                          ← one file per AI agent
│   ├── understanding.py               extract parties, jurisdiction, obligations
│   ├── risk_detection.py              15+ ontology-driven, document-adaptive checks
│   ├── validation.py                  clause dependency graph + pattern contradictions
│   ├── verification.py                cross-check "missing clause" claims vs headings
│   ├── party_analysis.py              Buyer vs Seller protection scoring
│   ├── drafting.py                    negotiation suggestions + fallback positions
│   ├── explainability.py              step-by-step reasoning trace
│   └── memory.py                      session question/answer history
│
├── core/                            ← document engine & retrieval
│   ├── ingestion.py                   PDF (PyMuPDF) and plain-text extraction
│   ├── pageindex_engine.py            dynamic LegalTree builder from markdown headings
│   ├── pageindex_adapter.py           bridge: VectifyAI PageIndex → LegalTree
│   └── retrieval.py                   TreeRetriever (IDF-weighted) + VectorRetriever (TF-IDF)
│
├── knowledge/                       ← legal domain intelligence
│   ├── legal_ontology.py              20 ClauseTypes + ClauseDependencyGraph (12 edges)
│   ├── jurisdiction.py                5 jurisdiction profiles + detection engine
│   └── risk_simulation.py             per-risk financial impact + portfolio metrics
│
├── pipeline/                        ← orchestration layer
│   ├── graph_flow.py                  GraphExecutor — full agent pipeline (LangGraph-ready)
│   └── orchestrator.py                LegalOrchestrator — FastAPI request handler
│
├── api/                             ← HTTP interface
│   ├── main.py                        FastAPI routes
│   └── schemas.py                     Pydantic request/response models
│
├── infra/                           ← infrastructure & cross-cutting concerns
│   ├── config.py                      SETTINGS (reads .env)
│   ├── llm.py                         Gemini client with model fallback chain
│   ├── persistence.py                 SQLite + in-memory repositories
│   ├── store.py                       StoredDocument, SessionMemory dataclasses
│   ├── audit.py                       structured audit event log
│   ├── benchmark.py                   dynamic eval harness (document-adaptive cases)
│   └── sample_docs.py                 built-in sample SPA text
│
├── frontend/
│   └── streamlit_app.py               Streamlit executive dashboard
│
├── docs/
│   └── sample_agreements/             sample PDFs for demo and testing
│
├── tests/                           ← test suite
├── data/                            ← SQLite database (git-ignored)
├── logs/                            ← audit log files (git-ignored)
└── vendor/
    └── PageIndex/                     VectifyAI/PageIndex (MIT, cloned)
```

---

## Quick Start

```bash
# 1. Clone and set up environment
git clone <repo-url> pageindex
cd pageindex
python3 -m venv .venv
.venv/bin/pip install -e .

# 2. Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 3. Start the backend
uvicorn main:app --reload
# or: uvicorn api.main:app --reload

# 4. Start the frontend (new terminal)
.venv/bin/streamlit run frontend/streamlit_app.py
```

API docs: `http://127.0.0.1:8000/docs`

---

## Configuration (`.env`)

```env
# Storage
STORAGE_BACKEND=sqlite          # sqlite | memory
SQLITE_PATH=data/legal_ai.db

# Google Gemini — powers legal Q&A and PageIndex tree generation
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=models/gemini-2.5-flash

# Fallback model chain (tried in order on failure)
GEMINI_MODELS=models/gemini-2.5-flash,models/gemini-2.5-pro,models/gemini-2.0-flash-001,models/gemini-flash-latest

# Tree generation mode
TREE_GENERATION_MODE=auto       # auto | pageindex | local
PAGEINDEX_MODEL=models/gemini-2.5-flash
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Status + PageIndex availability |
| `/system/info` | GET | Active configuration |
| `/documents/ingest_file` | POST | Upload PDF or TXT (multipart) |
| `/documents/ingest` | POST | Ingest raw text (JSON) |
| `/documents/ingest_sample` | POST | Load built-in sample SPA |
| `/qa/ask` | POST | Legal Q&A — full agent pipeline |
| `/benchmark/run` | POST | Tree vs Vector retrieval benchmark |
| `/benchmark/report` | POST | Markdown evaluation report |
| `/audit/events` | GET | Audit trail |

### Ingest a PDF

```bash
curl -X POST http://localhost:8000/documents/ingest_file \
  -F "document_id=my-spa-v1" \
  -F "title=Purchase Agreement" \
  -F "jurisdiction=New York" \
  -F "deal_type=Asset Purchase" \
  -F "tree_mode=auto" \
  -F "file=@contract.pdf"
```

### Ask a Legal Question

```bash
curl -X POST http://localhost:8000/qa/ask \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "my-spa-v1",
    "question": "What are the key legal risks in this agreement?",
    "retriever_mode": "tree",
    "execution_mode": "graph",
    "top_k": 8,
    "session_id": "user-1",
    "llm_provider": "gemini"
  }'
```

### Run Benchmark

```bash
curl -X POST http://localhost:8000/benchmark/run \
  -H "Content-Type: application/json" \
  -d '{"document_id": "my-spa-v1", "top_k": 4}'
```

---

## Key System Capabilities

### Dynamic Tree (per document)
Every document gets its own tree built from its actual headings. Font-size distribution, bold ratios, and heading depth are computed per document — no fixed thresholds.

### Dynamic Retrieval (per document)
`TreeRetriever` computes per-document IDF so rare legal terms in *this* document score higher. Hierarchy bonus scales with the document's average tree depth. `VectorRetriever` uses `sublinear_tf` to adapt to long vs short documents.

### Legal Ontology (20 clause types)
`knowledge/legal_ontology.py` defines 20 `ClauseType` enums and a `ClauseDependencyGraph` with 12 edges mapping relationships like `undermines`, `contradicts`, `limits_remedy`, and `gap`. Risk detection only runs checks for clause types actually present in the uploaded document.

### Jurisdiction Engine (5 profiles)
`knowledge/jurisdiction.py` detects governing law using a 5-tier priority chain: metadata → explicit governing law clause → forum selection clause → party address → general scan. Profiles for New York, Delaware, California, England & Wales, and India apply jurisdiction-specific severity adjustments and flag missing mandatory provisions.

### Risk Simulation
`knowledge/risk_simulation.py` generates per-risk financial scenarios with probability, impact multiple (relative to purchase price), worst-case narrative, and mitigation value. Portfolio metrics include expected loss, worst-case exposure, and risk-to-price ratio.

### Benchmark (document-adaptive)
`infra/benchmark.py` generates eval cases entirely from the uploaded document's own tree nodes using 20 legal topic signals. No hardcoded paths — `eval_case_coverage` is always 1.0.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Tree generation | [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) (MIT) |
| LLM | Google Gemini 2.5 Flash / Pro |
| Backend | FastAPI + Pydantic v2 |
| PDF parsing | PyMuPDF |
| Retrieval baseline | scikit-learn TF-IDF |
| Storage | SQLite (PostgreSQL-ready) |
| Frontend | Streamlit |

---

## Deployment

### Hugging Face Spaces (Docker) — recommended

HF Spaces runs a single Docker container. The image starts **both services** using `supervisord`:

| Service | Internal address |
|---------|-----------------|
| FastAPI backend | `http://localhost:8000` |
| Streamlit frontend | `http://0.0.0.0:7860` (public) |

**Steps:**

1. Create a new Space → **Docker** SDK.
2. Push this repository (the `README.md` front-matter configures the Space automatically).
3. Add your Gemini key in **Settings → Repository secrets**:
   ```
   GOOGLE_API_KEY=AIza...
   ```
4. HF Spaces builds the image from `Dockerfile` and starts both processes. The frontend calls the backend on `localhost:8000` internally — no extra configuration needed.

> The `BACKEND_URL` env var is set to `http://localhost:8000` inside the container by `supervisord.conf`. You do **not** need to set it manually.

---

### Streamlit Cloud

1. Deploy `frontend/streamlit_app.py` as the main module.
2. Run the FastAPI backend separately (Railway, Render, Fly.io, etc.).
3. Add secrets in **App Settings → Secrets**:
   ```toml
   BACKEND_URL = "https://your-backend.up.railway.app"
   GOOGLE_API_KEY = "AIza..."
   ```

---

### Local development

```bash
# Terminal 1 — backend
uvicorn api.main:app --reload --port 8000

# Terminal 2 — frontend
streamlit run frontend/streamlit_app.py
```

Copy `.env.example` to `.env` and fill in your `GOOGLE_API_KEY`.

---

## Roadmap

- Wire real LangGraph DAG with retries and human-in-the-loop review nodes
- OCR fallback for scanned PDFs (Gemini vision)
- Multi-document reasoning: LOI → SPA → Disclosure Schedules
- RBAC + authentication + signed audit log export
- Regulatory compliance packs: GDPR, SEBI, SOX, HIPAA
- Clause comparison agent: version diff + vendor vs client redline
