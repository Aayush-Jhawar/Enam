# FINN: AI Build History & Agent Collaboration Log
> **ENAM Holdings - AI Engineer Build Challenge (Screening 2027)**  
> **Candidate:** Aayush Jhawar (IIT)  
> **Repository:** https://github.com/Aayush-Jhawar/Enam  
> **Platform:** Google Antigravity Agentic IDE (Python 3.11, FastAPI, Modern Vanilla JS)

---

## 1. Overview & Tooling Strategy

In accordance with the challenge brief (*"We want to see how you work with the tools, not just the finished code"*), this document chronicles how **FINN** was conceptualized, built, tested, and audited using an autonomous coding agent.

### Build Metrics
- **Total Agent Actions / Steps:** 539 logged events
- **Tool Invocations:**
- `run_command`: 104 invocations
- `read_file`: 51 invocations
- `manage_task`: 46 invocations
- `write_file`: 30 invocations
- `edit_file`: 14 invocations
- `schedule`: 8 invocations
- `search_web`: 1 invocations
- `list_plugin_accounts`: 1 invocations

### Key Engineering Principles Enforced During AI Generation:
1. **Domain-First Grounding (No AI Slop):** We fed the official ENAM challenge PDFs directly into the system, extracting the nuanced instincts of public-markets investing: focusing on primary sources (Annual Reports and Concalls), prioritizing earnings quality (CFO/PAT conversion), and comparing narrative promises against actual delivered financials over 4 quarters.
2. **Deterministic-First Fallbacks:** To eliminate fragility and avoid runtime crashes when API keys or internet connections are constrained, every LLM task was paired with a deterministic domain-rule fallback.
3. **Rigorous Test-Driven Loop:** Enforced an automated ASGI audit script (`check_endpoints.py`) covering all 29 REST endpoints and module responses before declaring the system ready for deployment.

---

## 2. Chronological Prompt & Iteration History

### Phase 1: Problem Statement Ingestion & Architecture Brainstorming
- **User Prompt:** Deep research on both PDF briefs, studying requirements, constraints, and structuring a top-tier IIT submission.
- **Agent Action:** Analyzed the 17 corporate filing categories, 8 fundamental research modules, and established the dual-mode interaction model (Push Mode for daily routine vs. Pull Mode for deep dive). Designed a lightweight, zero-dependency local TF-IDF vector retrieval engine backed by SQLite to avoid ChromaDB/OpenAI cloud dependencies.

### Phase 2: Core Engineering & Scaffolding
- **User Prompt:** Build clean, human-readable, and scalable code without AI bloat.
- **Agent Action:** 
  - Backend: Scaffolded FastAPI app with SQLAlchemy database (`Company`, `Price`, `Announcement`, `DocumentChunk`, `AlertConfig`, `TriggeredAlert`, `LLMCallLog`).
  - Data bootstrap: Seeded 25 realistic NSE tickers, 775 EOD price points with volume spikes, and classified filings with QoQ/YoY extractions.
  - Frontend: Developed mobile-first responsive client with dark institutional styling (`#090D16`), gold accents, and bottom navigation.
  - Research Engine: Implemented all 8 primary modules, highlighting the 4-quarter "Narrative vs. Numbers" credibility scorecard.

### Phase 3: Comprehensive Endpoint Health Check & Audit
- **User Prompt:** Run all checks so that everything works, verify all endpoints, and prepare for deployment.
- **Agent Action:** Created `check_endpoints.py` exercising 29 ASGI test cases.
  - Diagnosed initial test failures: 48h digest timestamp aging and structured JSON formatting in offline fallbacks.
  - Fixed fallback handlers in `model_router.py` to return typed JSON for all 8 modules.
  - Added realistic financial anchors in `research_engine.py` for resilient yfinance fallback.
  - Re-seeded dynamic database with fresh timestamps.
  - Re-ran audit: **29 / 29 checks passed (100% success rate)**.

### Phase 4: Cloud Readiness & Submission Packaging
- **Agent Action:** Configured `render.yaml`, dynamic `PORT` and `0.0.0.0` host binding in `run.py`, committed pre-seeded `finn.db` for cloud persistence, and assembled submission documentation.

---

## 3. Key Technical Artifacts Generated

1. `check_endpoints.py`: Automated audit script ensuring 100% route availability and contract compliance.
2. `backend/services/model_router.py`: Two-tier model router (cheap vs. frontier) with token cost auditing in SQLite and institutional deterministic fallbacks.
3. `backend/services/research_engine.py`: Implementation of all 8 primary-source research modules, led by the 4-quarter "Narrative vs. Numbers" management credibility scorecard.
4. `frontend/app.js`: Pure client-side reactive state management with zero build-tool bloat (no webpack/vite/node required).

---
*The raw machine-readable JSONL logs (`transcript.jsonl` and `transcript_full.jsonl`) are included in this directory for complete provenance.*
