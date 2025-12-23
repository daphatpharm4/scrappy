"""Mock API loaders and static HTML scrapers for the PoC ingestion service."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

SAMPLE_ROOT = Path(__file__).parent / "sample_inputs"
STATIC_ROOT = Path(__file__).parent / "static_html"


def load_api_payload(domain: str, country: str) -> List[dict]:
    path = SAMPLE_ROOT / domain / country / f"api_{domain}.json"
    with path.open() as f:
        return json.load(f)


def scrape_static_html(domain: str) -> List[dict]:
    html_path = STATIC_ROOT / domain / f"sample_{domain}.html"
    if not html_path.exists():
        return []
    soup = BeautifulSoup(html_path.read_text(), "html.parser")
    rows: List[dict] = []
    if domain == "prices":
        table = soup.find("table", {"id": "prices"})
        if table:
            for tr in table.find_all("tr")[1:]:
                tds = [td.text for td in tr.find_all("td")]
                if len(tds) == 6:
                    rows.append(
                        {
                            "item": tds[0],
                            "price": float(tds[1]),
                            "currency": tds[2],
                            "provider": tds[3],
                            "country": tds[4],
                            "captured_at": tds[5],
                        }
                    )
    elif domain == "realestate":
        table = soup.find("table", {"id": "listings"})
        if table:
            for tr in table.find_all("tr")[1:]:
                tds = [td.text for td in tr.find_all("td")]
                if len(tds) == 8:
                    rows.append(
                        {
                            "city": tds[0],
                            "bedrooms": int(tds[1]),
                            "bathrooms": int(tds[2]),
                            "rent": float(tds[3]),
                            "currency": tds[4],
                            "provider": tds[5],
                            "country": tds[6],
                            "captured_at": tds[7],
                        }
                    )
    elif domain == "providers":
        ul = soup.find("ul", {"id": "providers"})
        if ul:
            for li in ul.find_all("li"):
                rows.append(
                    {
                        "provider": li.text.strip(),
                        "country": li.get("data-country"),
                        "category": li.get("data-category"),
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
    return rows
