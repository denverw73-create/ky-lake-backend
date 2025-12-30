import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from scraper import scrape_lakes

STORAGE_FILE = "storage.json"
CACHE_MAX_AGE_HOURS = int(os.getenv("CACHE_MAX_AGE_HOURS", "2"))

app = FastAPI(title="KY Lake Levels API")

# Allow your frontend to call this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down later if you want
    allow_methods=["*"],
    allow_headers=["*"],
)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def load_storage() -> Optional[Dict[str, Any]]:
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

def parse_timestamp(ts: str) -> Optional[datetime]:
    """
    Accepts ISO timestamps like:
      2025-12-30T12:34:56
      2025-12-30T12:34:56Z
      2025-12-30T12:34:56+00:00
    """
    if not ts or not isinstance(ts, str):
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        # If naive, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

@app.get("/")
def root():
    return {
        "message": "KY Lake Levels API is running",
        "endpoints": ["/lakes", "/refresh", "/health"],
    }

@app.get("/health")
def health():
    return {"ok": True, "time": utc_now().isoformat()}

@app.get("/lakes")
def get_lakes():
    """
    Get current lake data, using cache if newer than CACHE_MAX_AGE_HOURS.
    """
    saved = load_storage()

    # Use cache if fresh
    if saved and isinstance(saved, dict):
        saved_time = parse_timestamp(saved.get("timestamp", ""))
        if saved_time:
            age = utc_now() - saved_time
            if age < timedelta(hours=CACHE_MAX_AGE_HOURS):
                return {"source": "cached", **saved}

    # Otherwise scrape fresh
    result = scrape_lakes()

    # If scraper failed, fall back to cache if available
    if isinstance(result, dict) and result.get("error"):
        if saved and isinstance(saved, dict):
            return {"source": "cached", **saved, "warning": result.get("message", "Scrape failed")}
        raise HTTPException(status_code=502, detail=result.get("message", "Scrape failed"))

    # Ensure timestamp exists (frontend expects it)
    if isinstance(result, dict) and "timestamp" not in result:
        result["timestamp"] = utc_now().isoformat()

    save_storage(result)
    return {"source": "fresh", **result}

@app.get("/refresh")
def refresh():
    """
    Force a fresh scrape and update cache.
    """
    result = scrape_lakes()

    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Scraper returned unexpected format")

    if result.get("error"):
        raise HTTPException(status_code=502, detail=result.get("message", "Scrape failed"))

    if "timestamp" not in result:
        result["timestamp"] = utc_now().isoformat()

    save_storage(result)
    return {"source": "fresh", **result}
