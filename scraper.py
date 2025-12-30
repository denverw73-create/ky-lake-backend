# scraper.py
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

USACE_URL = "https://www.lrl-wc.usace.army.mil/reports/lkreport.html"
WOL_URL = "https://www.lrn-wc.usace.army.mil/basin_project.shtml?p=wol"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://www.lrl-wc.usace.army.mil/",
}


# ---------------------------
# Small helpers
# ---------------------------
def _num(x):
    try:
        return float(str(x).replace(",", "").replace("%", "").strip())
    except Exception:
        return None


def _first_number_near_label(full_text: str, label_regex: str, window: int = 140):
    """
    Find first number that appears within `window` chars after a label match.
    Works even when label/number are split across HTML tags/lines.
    """
    m = re.search(label_regex, full_text, flags=re.IGNORECASE)
    if not m:
        return None
    snippet = full_text[m.end() : m.end() + window]
    n = re.search(r"(-?\d+(?:\.\d+)?)", snippet.replace(",", ""))
    return _num(n.group(1)) if n else None


def _maybe_kcfs_to_cfs(v):
    """
    If value is small, it might be in kcfs. Heuristic: <200 => treat as kcfs.
    """
    if v is None:
        return None
    return v * 1000 if v < 200 else v


def _clean_text_for_regex(soup: BeautifulSoup) -> str:
    # Single-line-ish text is easier to regex across table breaks
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text


# ---------------------------
# Wolf Creek / Lake Cumberland
# ---------------------------
def scrape_wolf_creek_cumberland():
    """
    Scrapes Wolf Creek (Lake Cumberland) from LRN-WC basin_project page.
    Returns one lake object in the SAME SHAPE your app uses.
    """
    resp = requests.get(WOL_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    full_text = _clean_text_for_regex(soup)

    # Try a few label variations (these sites aren't consistent)
    pool = (
        _first_number_near_label(full_text, r"Pool\s*Elevation")
        or _first_number_near_label(full_text, r"Lake\s*Elevation")
        or _first_number_near_label(full_text, r"Elevation")
    )

    inflow = (
        _first_number_near_label(full_text, r"\bInflow\b")
        or _first_number_near_label(full_text, r"\bIn\s*Flow\b")
    )

    outflow = (
        _first_number_near_label(full_text, r"\bOutflow\b")
        or _first_number_near_label(full_text, r"\bOut\s*Flow\b")
        or _first_number_near_label(full_text, r"\bTotal\s*Flow\b")
        or _first_number_near_label(full_text, r"\bRelease\b")
    )

    # Fallback: scan tables for a row containing "Pool Elevation"
    if pool is None:
        for tr in soup.select("table tr"):
            row_text = " ".join(td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"]))
            if re.search(r"Pool\s*Elevation", row_text, flags=re.IGNORECASE):
                n = re.search(r"(-?\d+(?:\.\d+)?)", row_text.replace(",", ""))
                if n:
                    pool = _num(n.group(1))
                    break

    inflow_cfs = _maybe_kcfs_to_cfs(inflow)
    outflow_cfs = _maybe_kcfs_to_cfs(outflow)

    # If we still don't have pool, return None so we don't poison your dataset
    if pool is None and inflow_cfs is None and outflow_cfs is None:
        return None

    return {
        "basin": "Cumberland",
        "project": "Lake Cumberland",
        "todayPool": pool,
        "deviation": None,
        "change24h": None,
        "precip24h": None,
        "inflow": inflow_cfs,
        "outflow": outflow_cfs,
        "percentUtil": None,
    }


# ---------------------------
# Main lake scraper (LKREPORT)
# ---------------------------
def scrape_lakes():
    try:
        resp = requests.get(USACE_URL, headers=HEADERS, timeout=12)
        resp.raise_for_status()
    except Exception as e:
        return {"error": True, "message": str(e), "lakes": []}

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        return {"error": True, "message": "Lake table not found", "lakes": []}

    lakes = []
    rows = table.find_all("tr")
    last_basin = ""

    for row in rows[1:]:
        cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]

        # Your original table shape assumption
        if len(cols) < 13:
            continue

        # Basin fill-down logic
        basin = cols[0] if cols[0] else last_basin
        if cols[0]:
            last_basin = cols[0]

        project = cols[1]

        today_pool = _num(cols[5])
        deviation = _num(cols[6])
        change_24 = _num(cols[7])
        precip_24 = _num(cols[8])
        inflow = _num(cols[9])
        outflow = _num(cols[10])
        percent_util = _num(cols[12])

        lakes.append(
            {
                "basin": basin,
                "project": project,
                "todayPool": today_pool,
                "deviation": deviation,
                "change24h": change_24,
                "precip24h": precip_24,
                "inflow": inflow,
                "outflow": outflow,
                "percentUtil": percent_util,
            }
        )

    # --- Add/merge Lake Cumberland from Wolf Creek page ---
    try:
        wol = scrape_wolf_creek_cumberland()
        if wol:
            # If LKREPORT already has Lake Cumberland, merge missing fields only
            merged = False
            for i, l in enumerate(lakes):
                if (l.get("project") or "").strip().lower() == "lake cumberland":
                    for k in ["todayPool", "inflow", "outflow"]:
                        if l.get(k) is None and wol.get(k) is not None:
                            l[k] = wol[k]
                    lakes[i] = l
                    merged = True
                    break
            if not merged:
                lakes.append(wol)
    except Exception as e:
        print("Wolf Creek scrape failed:", e)

    return {
        "error": False,
        "timestamp": datetime.utcnow().isoformat(),
        "lakes": lakes,
    }
