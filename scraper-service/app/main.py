import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import pandas as pd
import yaml
from playwright.async_api import async_playwright


DATA_DIR = Path("/data/out")
DEFAULT_CONFIG_PATH = "/config/targets.txt"


def log_event(message: str, **extra: Any) -> None:
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "message": message,
        **extra,
    }
    print(json.dumps(payload))


def ensure_output_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_config_source() -> str:
    config_value = os.getenv("SCRAPER_CONFIG", DEFAULT_CONFIG_PATH)
    if os.path.exists(config_value):
        return Path(config_value).read_text(encoding="utf-8")
    return config_value


def parse_targets(config_raw: str) -> List[str]:
    content = config_raw.strip()
    if not content:
        return []

    # Try YAML/JSON structures first
    try:
        data = yaml.safe_load(content)
        if isinstance(data, list):
            return [str(item) for item in data]
        if isinstance(data, dict):
            for key in ("targets", "urls", "links"):
                if key in data and isinstance(data[key], list):
                    return [str(item) for item in data[key]]
    except Exception:
        pass

    if "\n" in content:
        return [line.strip() for line in content.splitlines() if line.strip()]
    if "," in content:
        return [item.strip() for item in content.split(",") if item.strip()]
    return [content]


def load_targets() -> List[str]:
    return parse_targets(read_config_source())


def get_proxy_pool() -> List[str]:
    proxies = []
    for env_var in ["HTTP_PROXY", "HTTPS_PROXY"]:
        value = os.getenv(env_var)
        if not value:
            continue
        proxies.extend([entry.strip() for entry in value.split(",") if entry.strip()])
    return proxies


def select_proxy(proxies: List[str], index: int) -> Optional[str]:
    if not proxies:
        return None
    return proxies[index % len(proxies)]


def extract_api_keys() -> Dict[str, Optional[str]]:
    return {
        "openai": os.getenv("OPENAI_API_KEY"),
        "deepseek": os.getenv("DEEPSEEK_API_KEY"),
        "xai": os.getenv("XAI_API_KEY"),
    }


def build_prompt(url: str, html_content: str) -> str:
    return (
        "You are a lead enrichment assistant. Given the page HTML, extract: "
        "business or person name, contact email if present, phone number if present, "
        "and a concise personalization note referencing the page content. "
        "Respond in JSON with keys name, email, phone, personalization. "
        f"Source URL: {url}. HTML: {html_content[:4000]}"
    )


def parse_model_response(text: str) -> Dict[str, Optional[str]]:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {
                "name": data.get("name"),
                "email": data.get("email"),
                "phone": data.get("phone"),
                "personalization": data.get("personalization"),
            }
    except Exception:
        pass
    return {"name": None, "email": None, "phone": None, "personalization": text.strip()[:1000]}


async def call_model(
    session: aiohttp.ClientSession,
    provider: str,
    api_keys: Dict[str, Optional[str]],
    url: str,
    html_content: str,
    correlation_id: str,
) -> Dict[str, Optional[str]]:
    provider = provider.lower()
    prompt = build_prompt(url, html_content)

    if provider == "openai":
        endpoint = "https://api.openai.com/v1/chat/completions"
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        headers = {"Authorization": f"Bearer {api_keys.get('openai')}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Extract lead details as JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
    elif provider == "deepseek":
        endpoint = "https://api.deepseek.com/v1/chat/completions"
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        headers = {"Authorization": f"Bearer {api_keys.get('deepseek')}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Extract lead details as JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
    elif provider == "xai":
        endpoint = "https://api.x.ai/v1/chat/completions"
        model = os.getenv("XAI_MODEL", "grok-beta")
        headers = {"Authorization": f"Bearer {api_keys.get('xai')}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Extract lead details as JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
    else:
        raise ValueError(f"Unsupported SCRAPER_MODEL_PROVIDER: {provider}")

    async with session.post(endpoint, json=payload, headers=headers) as resp:
        response_text = await resp.text()
        if resp.status >= 400:
            log_event(
                "model_request_failed",
                correlation_id=correlation_id,
                provider=provider,
                status=resp.status,
                response=response_text,
            )
            return {"name": None, "email": None, "phone": None, "personalization": response_text[:500]}

    try:
        data = json.loads(response_text)
        content = None
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content")
        if content:
            return parse_model_response(content)
    except Exception:
        pass

    return parse_model_response(response_text)


async def fetch_html(url: str, proxy: Optional[str]) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy={"server": proxy} if proxy else None)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        content = await page.content()
        await browser.close()
        return content


async def process_url(
    url: str,
    session: aiohttp.ClientSession,
    provider: str,
    api_keys: Dict[str, Optional[str]>,
    proxies: List[str],
    index: int,
) -> Optional[Dict[str, Any]]:
    correlation_id = str(uuid.uuid4())
    proxy = select_proxy(proxies, index)
    log_event("scrape_started", correlation_id=correlation_id, url=url, model_provider=provider, proxy=proxy)

    try:
        html_content = await fetch_html(url, proxy)
        log_event("scrape_completed", correlation_id=correlation_id, url=url, model_provider=provider, status="ok")
    except Exception as exc:
        log_event(
            "scrape_failed",
            correlation_id=correlation_id,
            url=url,
            model_provider=provider,
            status="error",
            error=str(exc),
        )
        return None

    try:
        lead = await call_model(session, provider, api_keys, url, html_content, correlation_id)
        lead.update({"url": url})
        log_event("model_completed", correlation_id=correlation_id, url=url, model_provider=provider, status="ok")
        return lead
    except Exception as exc:
        log_event(
            "model_failed",
            correlation_id=correlation_id,
            url=url,
            model_provider=provider,
            status="error",
            error=str(exc),
        )
        return None


def write_outputs(leads: List[Dict[str, Any]]) -> None:
    ensure_output_dir()
    json_path = DATA_DIR / "leads.json"
    md_path = DATA_DIR / "leads.md"
    csv_path = DATA_DIR / "leads.csv"

    json_path.write_text(json.dumps(leads, indent=2), encoding="utf-8")

    lines = ["# Scraped Leads\n"]
    for lead in leads:
        lines.append(f"- **Name:** {lead.get('name') or ''}")
        lines.append(f"  - Email: {lead.get('email') or ''}")
        lines.append(f"  - Phone: {lead.get('phone') or ''}")
        lines.append(f"  - URL: {lead.get('url') or ''}")
        lines.append(f"  - Personalization: {lead.get('personalization') or ''}\n")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    df = pd.DataFrame(leads, columns=["name", "email", "phone", "personalization", "url"])
    df.to_csv(csv_path, index=False)


async def run() -> None:
    targets = load_targets()
    if not targets:
        log_event("no_targets_found", correlation_id=str(uuid.uuid4()), url=None, model_provider=None, status="skipped")
        return

    provider = os.getenv("SCRAPER_MODEL_PROVIDER", "openai").lower()
    api_keys = extract_api_keys()
    if provider not in api_keys or not api_keys.get(provider):
        raise RuntimeError(f"API key missing for provider {provider}")

    proxies = get_proxy_pool()
    timeout = aiohttp.ClientTimeout(total=120)
    results: List[Dict[str, Any]] = []

    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [process_url(url, session, provider, api_keys, proxies, idx) for idx, url in enumerate(targets)]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result:
                results.append(result)

    write_outputs(results)


if __name__ == "__main__":
    asyncio.run(run())
