import json
import os
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from scraper import scrape_lakes
from flask import Flask, jsonify
from scraper import scrape_lakes

app = Flask(__name__)

@app.get("/lakes")
def lakes():
    data = scrape_lakes()
    return jsonify(data)

STORAGE_FILE = "storage.json"

app = FastAPI(title="KY Lake Levels API")

# Allow your app to call this from anywhere
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_storage():
    if not os.path.exists(STORAGE_FILE):
        return None
    try:
        with open(STORAGE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def save_storage(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)


@app.get("/")
def root():
    return {"message": "KY Lake Levels API is running", "endpoints": ["/lakes", "/refresh"]}


@app.get("/lakes")
def get_lakes():
    """
    Get current lake data, using cache if newer than 2 hours.
    """
    saved = load_storage()

    # Use cache if fresh
    if saved:
        try:
            saved_time = datetime.fromisoformat(saved["timestamp"])
            if datetime.utcnow() - saved_time < timedelta(hours=2):
                return {"source": "cached", **saved}
        except Exception:
            pass

    # Otherwise scrape fresh
    result = scrape_lakes()
    if result["error"]:
        # fall back to old cache if available
        if saved:
            return {"source": "cached", **saved, "warning": result["message"]}
        return {"source": "error", **result}

    save_storage(result)
    return {"source": "fresh", **result}


@app.get("/refresh")
def refresh():
    """
    Force a fresh scrape and update cache.
    """
    result = scrape_lakes()
    if not result["error"]:
        save_storage(result)
        return {"source": "fresh", **result}
    return {"source": "error", **result}
