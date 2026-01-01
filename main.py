# main.py
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from scraper import scrape_lakes

STORAGE_FILE = "storage.json"
CACHE_HOURS = 2

app = FastAPI(title="Anchor Point API")

VISITS_FILE = "visits.json"

# Allow your frontend to call this from anywhere
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_storage() -> Dict[str, Any] | None:
    if not os.path.exists(STORAGE_FILE):
        return None
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_storage(data: Dict[str, Any]) -> None:
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_cache_fresh(saved: Dict[str, Any]) -> bool:
    try:
        ts = saved.get("timestamp")
        if not ts:
            return False
        saved_time = date.fromisoformat(ts)
        return (date.utcnow() - saved_time) < timedelta(hours=CACHE_HOURS)
    except Exception:
        return False


@app.get("/")
def root():
    return {
        "message": "Anchor Point API is running",
        "endpoints": ["/lakes", "/refresh"],
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
            return {"source": "cached", **saved, "warning": result.get("message", "Scrape failed")}
        return {"source": "error", **result}

    # Save new data + return
    save_storage(result)
    return {"source": "fresh", **result}


@app.get("/refresh")
def refresh():
    """
    Forces a fresh scrape and updates cache.
    """
    result = scrape_lakes()
    if result.get("error"):
        return {"source": "error", **result}

    save_storage(result)
    return {"source": "fresh", **result}
def load_visits():
    if not os.path.exists(VISITS_FILE):
        return {"count": 1000}  # start at 1k
    try:
        with open(VISITS_FILE, "r") as f:
            data = json.load(f)
            if "count" not in data:
                data["count"] = 1000
            return data
    except Exception:
        return {"count": 1000}
        def save_visits(data: Dict[str, Any]) -> None:
    with open(VISITS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def increment_visits() -> int:
    data = load_visits()
    data["count"] = int(data.get("count", 1000)) + 1
    save_visits(data)
    return data["count"]
@app.get("/visits")
def visits():
    count = increment_visits()
    return {"count": count}

