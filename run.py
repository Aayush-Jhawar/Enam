"""
FINN: Financial Investment Agent
Main Startup Script - Serves both REST API and Mobile-First Web Frontend.
"""
import os
import sys

# Ensure backend package is in python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import DB_PATH
from seed_data import seed_all_data

def main():
    print("=" * 65)
    print("  FINN - Financial Investment Agent")
    print("  Built for ENAM Holdings AI Engineer Build Challenge (2027)")
    print("=" * 65)

    # Automatically bootstrap SQLite if database doesn't exist
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        print("[*] Initializing local database and seeding primary filings...")
        seed_all_data()
        print("[*] Database bootstrap complete.")
    else:
        print(f"[*] Found existing database at: {DB_PATH}")

    print("\n[*] Starting FINN HTTP Server on http://127.0.0.1:8000")
    print("    - Mobile Web App: http://127.0.0.1:8000/")
    print("    - Interactive API Docs: http://127.0.0.1:8000/docs")
    print("=" * 65 + "\n")

    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()

