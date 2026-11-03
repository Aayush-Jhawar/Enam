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

    # Render / Railway use PORT env variable; local dev defaults to 8000
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"  # Listen on all interfaces for cloud deployment

    print(f"\n[*] Starting FINN HTTP Server on http://{host}:{port}")
    print(f"    - Mobile Web App: http://{host}:{port}/")
    print(f"    - Interactive API Docs: http://{host}:{port}/docs")
    print("=" * 65 + "\n")

    import uvicorn
    # Disable watchfiles in cloud (Render/Railway) to prevent SQLite file writes from triggering reloads
    is_cloud = bool(os.environ.get("RENDER") or os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("ENVIRONMENT") == "production")
    reload = not is_cloud
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    main()

