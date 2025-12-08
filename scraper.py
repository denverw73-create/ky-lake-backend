import requests
from bs4 import BeautifulSoup
from datetime import datetime

USACE_URL = "https://www.lrl-wc.usace.army.mil/reports/lkreport.html"

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

        if len(cols) < 13:
            continue

        # Basin fill-down logic
        basin = cols[0] if cols[0] else last_basin
        if cols[0]:
            last_basin = cols[0]

        project = cols[1]

        def num(x):
            try:
                return float(x.replace(",", "").replace("%", ""))
            except:
                return None

        today_pool   = num(cols[5])
        deviation    = num(cols[6])
        change_24    = num(cols[7])
        precip_24    = num(cols[8])
        inflow       = num(cols[9])
        outflow      = num(cols[10])
        percent_util = num(cols[12])

        lakes.append({
            "basin": basin,
            "project": project,
            "todayPool": today_pool,
            "deviation": deviation,
            "change24h": change_24,
            "precip24h": precip_24,
            "inflow": inflow,
            "outflow": outflow,
            "percentUtil": percent_util,
        })

    return {
        "error": False,
        "timestamp": datetime.utcnow().isoformat(),
        "lakes": lakes
    }
