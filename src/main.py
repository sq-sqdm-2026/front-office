"""
Front Office - Main Entry Point
Baseball Universe Simulation powered by Local LLMs.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.staticfiles import StaticFiles
from pathlib import Path

from src.api.routes import app
from pathlib import Path

# Seed the database on first run — prefer real MLB data if cache exists
if (Path(__file__).parent.parent / "mlb_cache.json").exists():
    from src.database.seed_real import seed_real_database
    seed_real_database()
else:
    from src.database.seed import seed_database
    seed_database()

# Serve static files (frontend)
static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
