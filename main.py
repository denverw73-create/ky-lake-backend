# main.py
import json
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from threading import Lock

from scraper import scrape_lakes

# -----------------------------
# Files / cache settings
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
STORAGE_FILE = BASE_DIR / "storage.json"
VISITS_FILE = BASE_DIR / "visits.json"

CACHE_HOURS = 2
VISITS_START = 1000

# Simple lock so two requests at once don't corrupt json files
storage_lock = Lock()
visits_lock = Lock()

app = FastAPI(title="Anchor Point API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Storage helpers (lakes cache)
# -----------------------------
def load_storage() -> Dict[str, Any] | None:
    if not STORAGE_FILE.exists():
        return None
    try:
        with storage_lock:
            return json.loads(STORAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_storage(data: Dict[str, Any]) -> None:
    try:
        with storage_lock:
            STORAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        # If writing fails, don't crash the API
        pass


def is_cache_fresh(saved: Dict[str, Any]) -> bool:
    """
    We store a precise timestamp_utc for caching purposes.
    """
    try:
        ts = saved.get("timestamp_utc")
        if not ts:
            return False
        saved_time = datetime.fromisoformat(ts)
        return (datetime.utcnow() - saved_time) < timedelta(hours=CACHE_HOURS)
    except Exception:
        return False


def normalize_scrape_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Forces a date-only timestamp for your frontend (no time shown).
    Keeps timestamp_utc internally for caching freshness.
    """
    out = dict(result or {})
    out["timestamp"] = date.today().isoformat()          # <--- DATE ONLY (no time)
    out["timestamp_utc"] = datetime.utcnow().isoformat() # <--- for cache freshness
    if "lakes" not in out:
        out["lakes"] = []
    return out

# -----------------------------
# Visits helpers
# -----------------------------
def load_visits() -> Dict[str, Any]:
    if not VISITS_FILE.exists():
        return {"count": VISITS_START}
    try:
        with visits_lock:
            data = json.loads(VISITS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"count": VISITS_START}
        if "count" not in data:
            data["count"] = VISITS_START
        return data
    except Exception:
        return {"count": VISITS_START}


def save_visits(data: Dict[str, Any]) -> None:
    try:
        with visits_lock:
            VISITS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def increment_visits() -> int:
    data = load_visits()
    try:
        data["count"] = int(data.get("count", VISITS_START)) + 1
    except Exception:
        data["count"] = VISITS_START + 1
    save_visits(data)
    return data["count"]

# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def root():
    return {
        "message": "Anchor Point API is running",
        "endpoints": ["/lakes", "/refresh", "/visits", "/visits/count"],
        "cache_hours": CACHE_HOURS,
    }


@app.get("/lakes")
def get_lakes():
    """
    Returns lake data.
    Uses cached data if it's newer than CACHE_HOURS.
    Falls back to stale cache if scrape fails.
    """
    saved = load_storage()

    # Return fresh cache if available
    if saved and is_cache_fresh(saved):
        return {"source": "cached", **saved}

    # Otherwise scrape fresh
    result = scrape_lakes()

    # If scrape fails, fall back to any cache we have
    if result.get("error"):
        if saved:
            return {
                "source": "cached",
                **saved,
                "warning": result.get("message", "Scrape failed"),
            }
        return {"source": "error", **result}

    normalized = normalize_scrape_result(result)
    save_storage(normalized)
    return {"source": "fresh", **normalized}


@app.get("/refresh")
def refresh():
    """
    Forces a fresh scrape and updates cache.
    """
    result = scrape_lakes()
    if result.get("error"):
        return {"source": "error", **result}

    normalized = normalize_scrape_result(result)
    save_storage(normalized)
    return {"source": "fresh", **normalized}


@app.get("/visits")
def visits():
    """
    Increments and returns the visit counter.
    Call this from the frontend on page load.
    """
    count = increment_visits()
    return {"count": count}


@app.get("/visits/count")
def visits_count():
    """
    Returns the counter WITHOUT incrementing.
    Useful for testing / admin display.
    """
    return load_visits()
from flask import Flask
from flask_cors import CORS

app = Flask(__name__)

CORS(app, origins=[
    "https://anchorpointfishing.com",
    "https://www.anchorpointfishing.com"
])
