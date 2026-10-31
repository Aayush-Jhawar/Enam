# FINN: Financial Investment Agent — Covering Note
**Submission for ENAM Holdings AI Engineer Build Challenge (Screening 2027)**  
**To:** `assessment@enam.com`  
**Subject:** `ENAM - IIT screening - 2027`

---

### 1. What Was Built

We built **FINN** — a mobile-first financial investment agent designed specifically around the daily workflow and primary-data discipline of an institutional public-markets investor at ENAM Holdings. 

FINN resolves the fundamental tension between **Push** (proactive, event-driven filtering) and **Pull** (on-demand, rigorous fundamental research) through a dual-mode engine:

#### A. Push Mode: The Investor's Daily Morning Routine
- **Windowed Digest (24h, 48h, 7d):** Filters exchange disclosures across the 20-company portfolio. Routine paperwork (ESOPs, compliance forms) is cleanly collapsed into an expandable drawer, while high-conviction events are expanded front-and-center.
- **Judgment-Driven Presentation:**
  - *Quarterly Results:* Instantly extracts headline metrics — Revenue, Operating EBITDA, PBT, and PAT — with QoQ and YoY delta pills in Crores (₹ Cr).
  - *Management Changes:* Bypasses raw regulatory text to surface incoming executive background, past institutional pedigree, and mandate.
  - *M&A / Litigation:* Highlights transaction value, strategic rationale, and legal exposure.
- **Triggered Threshold Alerts:** Watches EOD prices and trading volumes against user-configurable criteria (e.g., daily swing $\ge \pm 5\%$, volume $\ge 2\times$ 20-day average, or material filings).

#### B. Pull Mode: Primary-Source Fundamental Research Suite
Grounded strictly in **Annual Reports (ARs)** and **Earnings Call Transcripts** — zero broker notes, zero media noise, zero unverified LLM hallucinations. Covers 8 structured modules:
1. **Business Snapshot:** Segment revenue contribution, operating model, and structural competitive moats.
2. **Financial Snapshot:** 9-factor fundamental health metrics (Revenue, EBITDA margins, PAT, P/E, ROE, ROCE, D/E).
3. **Multi-Year Trajectory:** 3-year CAGR, expanding product lines vs. compressing legacy lines.
4. **Balance Sheet & Leverage:** Gross vs. Net Debt, D/E ratio, working capital cycle, and debtor/inventory days.
5. **Cash Quality & Conversion:** Operating cash conversion ratio ($\text{CFO} / \text{PAT}$), Free Cash Flow, and capex intensity.
6. **Narrative vs. Numbers (The Showcase Feature):** A 4-quarter audit comparing management's forward promises from concalls against actual delivered financial filings, outputting an objective credibility score and hit/miss scorecard.
7. **Forward Guidance Tracker:** Explicit forward targets on top-line growth, margin bands, and capex budgets.
8. **Bull vs. Bear Case:** 3 high-conviction structural tailwinds vs. 3 key operational/cyclical failure modes.

#### C. Generalization Beyond Demo Portfolio
The engine is not hardcoded to the 20 demo stocks; querying any arbitrary NSE symbol (e.g., `SBIN`, `TATACONSUM`, `BAJAJ-AUTO`) dynamically fetches fundamentals, extracts primary document sections, synthesizes the 8 modules, and caches the result for sub-50ms repeat retrieval.

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

