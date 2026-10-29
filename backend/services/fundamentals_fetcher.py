"""
FINN - Primary Fundamentals Fetcher
Scrapes screener.in / investor relations for Annual Reports & Concall Transcripts,
extracts text via pdfplumber, chunks semantically, and indexes into the vector store.
"""
import logging
import os
import re
from typing import Optional, List, Dict, Any

import pdfplumber
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from config import SCREENER_BASE_URL
from services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)


def scrape_screener_documents(ticker: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Scrapes company document links from Screener.in.
    Returns categorized links for Annual Reports and Concall Transcripts.
    """
    clean_ticker = ticker.upper().replace(".NS", "").replace(".BO", "")
    url = f"{SCREENER_BASE_URL}/{clean_ticker}/"

    docs = {"annual_reports": [], "concalls": []}

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            # Try consolidated variant
            resp = requests.get(f"{SCREENER_BASE_URL}/{clean_ticker}/consolidated/", headers=HEADERS, timeout=12)

        if resp.status_code != 200:
            logger.warning(f"Screener returned HTTP {resp.status_code} for {clean_ticker}")
            return docs

        soup = BeautifulSoup(resp.text, "html.parser")

        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True).lower()

            full_url = href if href.startswith("http") else f"https://www.screener.in{href}"

            if ("annual" in text and "report" in text) or "ar " in text or "annual report" in href.lower():
                docs["annual_reports"].append({
                    "title": link.get_text(strip=True) or "Annual Report",
                    "url": full_url,
                })
            elif "concall" in text or "transcript" in text or "earnings call" in text:
                docs["concalls"].append({
                    "title": link.get_text(strip=True) or "Concall Transcript",
                    "url": full_url,
                })

    except Exception as e:
        logger.error(f"Error scraping screener.in for {clean_ticker}: {e}")

    logger.info(f"[{clean_ticker}] Discovered {len(docs['annual_reports'])} ARs and {len(docs['concalls'])} Concalls")
    return docs


def download_pdf(url: str, ticker: str, doc_type: str, index: int) -> Optional[str]:
    """Downloads a PDF document locally if not already cached."""
    clean_ticker = ticker.upper().replace(".NS", "").replace(".BO", "")
    filename = f"{clean_ticker}_{doc_type}_{index}.pdf"
    filepath = os.path.join(PDF_DIR, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
        return filepath

    try:
        resp = requests.get(url, headers=HEADERS, timeout=25, stream=True)
        if resp.status_code == 200:
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
            logger.info(f"Downloaded PDF: {filename} ({os.path.getsize(filepath)} bytes)")
            return filepath
    except Exception as e:
        logger.warning(f"Could not download {url}: {e}")

    return None


def extract_text_from_pdf(filepath: str, max_pages: int = 100) -> str:
    """Extracts text from a local PDF using pdfplumber."""
    if not filepath or not os.path.exists(filepath):
        return ""

    extracted = []
    try:
        with pdfplumber.open(filepath) as pdf:
            pages_to_read = pdf.pages[:max_pages]
            for page in pages_to_read:
                text = page.extract_text()
                if text:
                    extracted.append(text)
    except Exception as e:
        logger.error(f"pdfplumber failed reading {filepath}: {e}")

    return "\n\n".join(extracted)


def chunk_text(
    text: str,
    ticker: str,
    doc_type: str,
    period: str = "",
    chunk_size: int = 1400,
    overlap: int = 150
) -> List[Dict[str, Any]]:
    """
    Semantic section chunker preserving paragraph integrity.
    Attaches metadata for provenance tracking and citation.
    """
    if not text.strip():
        return []

    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current_buf = []
    current_len = 0
    chunk_idx = 0

    clean_ticker = ticker.upper().replace(".NS", "").replace(".BO", "")

    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue

        p_len = len(p_clean)
        if current_len + p_len > chunk_size and current_buf:
            chunk_body = "\n\n".join(current_buf)
            chunks.append({
                "id": f"{clean_ticker}_{doc_type}_{period}_{chunk_idx}",
                "text": chunk_body,
                "doc_type": doc_type,
                "period": period,
                "chunk_index": chunk_idx,
                "metadata": {
                    "ticker": clean_ticker,
                    "doc_type": doc_type,
                    "period": period,
                    "chunk_idx": chunk_idx,
                }
            })
            chunk_idx += 1

            # Retain trailing overlap
            tail = chunk_body[-overlap:] if len(chunk_body) > overlap else ""
            current_buf = [tail, p_clean] if tail else [p_clean]
            current_len = sum(len(x) for x in current_buf)
        else:
            current_buf.append(p_clean)
            current_len += p_len

    if current_buf:
        chunk_body = "\n\n".join(current_buf).strip()
        if chunk_body:
            chunks.append({
                "id": f"{clean_ticker}_{doc_type}_{period}_{chunk_idx}",
                "text": chunk_body,
                "doc_type": doc_type,
                "period": period,
                "chunk_index": chunk_idx,
                "metadata": {
                    "ticker": clean_ticker,
                    "doc_type": doc_type,
                    "period": period,
                    "chunk_idx": chunk_idx,
                }
            })

    return chunks


def build_index_for_company(db: Session, ticker: str, max_docs: int = 3) -> Dict[str, Any]:
    """
    Runs the full scraping -> downloading -> extraction -> chunking -> vector indexing pipeline.
    """
    clean_ticker = ticker.upper().replace(".NS", "").replace(".BO", "")
    vector_store = get_vector_store(db)

    # Check if we already have chunks for this ticker
    existing = vector_store.query(clean_ticker, "business overview", n_results=1)
    if existing:
        return {
            "status": "cached",
            "ticker": clean_ticker,
            "message": "Documents already indexed in vector store.",
        }

    docs = scrape_screener_documents(clean_ticker)
    total_chunks = []

    # Process Annual Reports
    for idx, ar in enumerate(docs.get("annual_reports", [])[:max_docs]):
        pdf_path = download_pdf(ar["url"], clean_ticker, "ar", idx)
        if pdf_path:
            text = extract_text_from_pdf(pdf_path, max_pages=80)
            chunks = chunk_text(text, clean_ticker, doc_type="annual_report", period=f"AR_{idx+1}")
            total_chunks.extend(chunks)

    # Process Concall Transcripts
    for idx, cc in enumerate(docs.get("concalls", [])[:max_docs]):
        pdf_path = download_pdf(cc["url"], clean_ticker, "concall", idx)
        if pdf_path:
            text = extract_text_from_pdf(pdf_path, max_pages=40)
            chunks = chunk_text(text, clean_ticker, doc_type="concall", period=f"Q{idx+1}")
            total_chunks.extend(chunks)

    inserted_count = vector_store.add_chunks(clean_ticker, total_chunks)

    return {
        "status": "success",
        "ticker": clean_ticker,
        "annual_reports_found": len(docs.get("annual_reports", [])),
        "concalls_found": len(docs.get("concalls", [])),
        "total_chunks_indexed": inserted_count,
    }
