# FINN: Financial Investment Agent — Covering Note
**Submission for ENAM Holdings AI Engineer Build Challenge (Screening 2027)**  
**Candidate:** Aayush Jhawar (IIT)  
**To:** `assessment@enam.com`  
**Subject:** `ENAM - IIT screening - 2027`  
**GitHub Repository:** [https://github.com/Aayush-Jhawar/Enam](https://github.com/Aayush-Jhawar/Enam)  
**Live Deployed Application:** [https://finn-enam.onrender.com/](https://finn-enam.onrender.com/)  

---

### Executive Summary & Domain Genesis

During my summer internship building an institutional market intelligence platform ([Oil Market Dashboard](https://github.com/Aayush-Jhawar/Oil_Market_Dashboard)), I grappled firsthand with the core dilemma of market analysis: financial markets produce an overwhelming flood of noisy time-series data, speculative headlines, and sell-side commentary, yet true differentiated signal resides strictly in **primary, structural data**.

When analyzing ENAM Holdings' challenge brief, it became clear that public-markets value investing suffers from the exact same pathology: an analyst at ENAM is inundated with daily exchange filings, macro noise, and compliance paperwork. Applying the lessons from my internship to ENAM's patient, bottom-up investment philosophy (pioneered by Nemish Shah), I formulated the architecture of **FINN**:
1. **Push Mode (The Daily Morning Routine):** A proactive, windowed digest that ruthlessly filters out administrative compliance paperwork while surfacing high-conviction events with structured extractions (Revenue, Operating EBITDA, PBT, PAT deltas, and executive management backgrounds).
2. **Pull Mode (Primary Grounded Research):** Strictly grounded in Annual Reports and Concall Transcripts — zero broker notes, zero news, zero LLM hallucinations.
3. **The Crown Jewel ("Narrative vs. Numbers"):** A 4-quarter audit comparing management's forward commentary and guidance against subsequent actual delivered financials, generating an objective credibility score.

I conducted the complete domain brainstorming, financial ontology formulation, and architectural design, while directing an autonomous AI coding agent strictly as a technical implementation copilot to write the backend endpoints, database models, vector indexers, and automated test suites.

---

### 1. What Was Built

FINN is a mobile-first equity intelligence agent built to save hours of an investor's day by giving them a focused, judgment-driven canvas:

#### A. Push Mode: Proactive Event Filtering & Alerts
- **Windowed Digest (24h, 48h, 7d):** Filters corporate announcements across the 20-company portfolio. Routine compliance paperwork (ESOP allotments, trading window closures, secretarial returns) is collapsed into an expandable vault, while material disclosures are highlighted.
- **Results Headline Extractor:** Instantly converts quarterly financial results into standardized tables showing **Revenue, Operating EBITDA, PBT, and PAT** with QoQ and YoY delta percentages in Crores (₹ Cr).
- **Executive Management Bio Enrichment:** Automatically extracts incoming executive names, new roles, actions (joining vs. resigning), and prior corporate pedigree.
- **Threshold-Triggered Alerts:** Monitors EOD prices and volumes against user-configurable criteria (e.g., daily price swings $\ge \pm 5\%$, volume surges $\ge 2.0\times$ 20-day average volume, or material litigation/M&A).

#### B. Pull Mode: Primary-Source Fundamental Research Suite
Grounded strictly in **Annual Reports (ARs)** and **Earnings Call Transcripts** across 8 structured modules:
1. **Business Snapshot:** Business model, segmental revenue contribution, and structural competitive moats.
2. **Financial Snapshot:** 9-factor fundamental health metrics (Revenue, EBITDA margins, PAT, P/E, ROE, ROCE, D/E).
3. **Multi-Year Trajectory:** 3-year CAGR, expanding product lines vs. compressing legacy lines.
4. **Balance Sheet & Leverage:** Gross vs. Net Debt, D/E ratio, working capital cycle, and debtor/inventory days.
5. **Cash Quality & Conversion:** Operating cash conversion ratio ($\text{CFO} / \text{PAT}$), Free Cash Flow, and capex intensity.
6. **Narrative vs. Numbers (The Showcase Feature):** A 4-quarter audit comparing management's forward promises from concalls against actual delivered financial filings, outputting an objective credibility score and hit/miss scorecard.
7. **Forward Guidance Tracker:** Explicit forward targets on top-line growth, margin bands, and capex budgets.
8. **Bull vs. Bear Case:** 3 high-conviction structural tailwinds vs. 3 key operational/cyclical failure modes.

#### C. Generalization Beyond Demo Portfolio
The engine is not hardcoded to the 20 demo stocks; querying any arbitrary NSE symbol (e.g., `POLYCAB`, `SBIN`, `TATACONSUM`) dynamically scrapes Screener.in for primary filings, extracts MD&A text, chunks and indexes into the vector store, and synthesizes the 8 research modules on the fly.

---

### 2. Key Decisions & Architecture Trade-offs

1. **Local-First Zero-Crash Hybrid Vector Store:**
   - *Decision:* Rather than mandating heavy external dependencies or paid cloud vector databases, we implemented a dual-mode retrieval engine. By default, it runs a blazing-fast local TF-IDF / Cosine Similarity store persisted directly in SQLite, with optional ChromaDB/OpenAI pluggability.
   - *Trade-off:* While dense neural embeddings capture subtle linguistic nuances, sparse TF-IDF with exact financial tokenization guarantees zero runtime crashes, instant cold-starts, zero API bills, and 100% determinism.

2. **Smart Model Routing & Token Economics:**
   - *Decision:* Tiered model routing based on cognitive load:
     - High-volume classification, summaries, and ratio calculations run on cheap, fast models (Gemini 1.5 Flash / GPT-4o-mini at $\sim \$0.075/\text{1M tokens}$).
     - Deep synthesis (Narrative vs. Numbers, Bull/Bear thesis) routes to frontier reasoning models (GPT-4o).
     - Deterministic rule heuristics act as a live fail-safe if network or rate-limits occur.
   - *Trade-off:* Tracking tokens in `LLMCallLog` allows us to audit total demo cost (under $\$0.02$ for full portfolio evaluation), proving compute frugality.

3. **Mobile-First Responsive Web Canvas over Native App:**
   - *Decision:* Built as a responsive web client with a mobile device viewport emulator, bottom thumb navigation, and dark institutional aesthetics (`#090D16` with amber gold accents).
   - *Trade-off:* Avoids TestFlight invite bottlenecks and simulator installation hurdles; opens instantly on any phone browser or laptop screen.

---

### 3. What Was Deliberately Left Out (And Why)

- **Macro Commentary & Broker Research:** Sell-side broker reports and financial news were deliberately excluded from pull synthesis. Differentiated investment edge lives in primary company disclosures; secondary commentary introduces consensus bias and noise.
- **Complex Intraday Tick Charting:** Candlestick charts and technical indicators were excluded. ENAM is a bottom-up fundamental value fund; intraday technical noise distracts from operating cash flows, competitive moats, and management integrity.
- **Uncontrolled Autonomous Agents:** We avoided multi-agent "chatty" swarms that loop unpredictably and burn tokens. A structured pipeline with clear inputs, deterministic caching, and typed outputs is far more reliable for capital allocation.

---

### 4. Where We Would Take It Next

1. **Forensic Red-Flag Scanner:** Automated parsing of Annual Report Notes to Accounts for Related Party Transactions (RPTs), auditor qualifications, contingent liabilities, and changes in accounting policies.
2. **Management Voice Tone & Hesitation Analysis:** Audio acoustic analysis of earnings call recordings to flag vocal stress or hesitation when answering difficult analyst questions.
3. **Peer Cohort Multi-Bagger Matrix:** Automated peer comparison across unlisted vs. listed competitors within the same sub-sector.

---

### 5. Verification & Audit Results

FINN has been validated using a 29-point automated ASGI health-check script (`check_endpoints.py`):
- **Health & DB Integrity:** 25 companies, 775 EOD prices, 10 active alerts (PASSED)
- **Push Mode:** 24h/48h/7d windowed digests & results enrichments (PASSED)
- **Alert Mutability:** Config threshold updates & dismissal lifecycle (PASSED)
- **Pull Mode:** All 8 modules verified with structured schemas (PASSED)
- **Ad-Hoc Generalization:** Tested and verified on `POLYCAB` (PASSED)
- **Total Endpoint Pass Rate:** **29 / 29 checks passed (100%)**
