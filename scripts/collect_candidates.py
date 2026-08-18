import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "resources" / "content_curator_sources.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
    )
}
TIMEOUT = (5, 15)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def clean_text(value: str) -> str:
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def fetch_rss(source: dict, per_source: int) -> list[dict]:
    response = requests.get(source["url"], headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    items = []
    for entry in feed.entries[:per_source]:
        link = entry.get("link", "").strip()
        title = clean_text(entry.get("title", ""))
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "summary": clean_text(entry.get("summary", ""))[:1000],
                "published": entry.get("published", entry.get("updated", "")),
                "source": source["name"],
                "source_layer": source["layer"],
                "verification_status": "pending",
            }
        )
    return items


def fetch_aihot(source: dict, per_source: int) -> list[dict]:
    response = requests.get(source["url"], headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    seen_links = set()
    for link in soup.select("a[href]"):
        href = urljoin(source["url"], link.get("href", "")).replace(".com//", ".com/")
        title_node = link.select_one("div.font-\\[500\\]")
        title = clean_text(str(title_node)) if title_node else clean_text(link.get_text(" "))
        title = re.sub(r"^\d+\s*[.、]?\s*", "", title)
        if not title or len(title) < 8 or not href.startswith("http") or href in seen_links:
            continue
        seen_links.add(href)
        items.append(
            {
                "title": title,
                "link": href,
                "summary": "",
                "published": "",
                "source": source["name"],
                "source_layer": source["layer"],
                "verification_status": "pending",
            }
        )
        if len(items) >= per_source:
            break
    return items


def fetch_source(source: dict, per_source: int) -> list[dict]:
    if source["type"] == "rss":
        return fetch_rss(source, per_source)
    if source["type"] == "aihot":
        return fetch_aihot(source, per_source)
    raise ValueError(f"Unsupported source type: {source['type']}")


def is_relevant(item: dict, keywords: list[str]) -> bool:
    text = f"{item['title']} {item['summary']}".lower()
    return any(keyword.lower() in text for keyword in keywords)


def title_key(title: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", title.lower())


def filter_candidates(items: list[dict], config: dict) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=config["collection"]["lookback_days"])
    keywords = config["relevance_keywords"]
    result = []
    seen = set()
    for item in items:
        key = title_key(item["title"])
        if not key or key in seen or not is_relevant(item, keywords):
            continue
        published = parse_date(item["published"])
        if published and published < cutoff:
            continue
        seen.add(key)
        item["published_iso"] = published.isoformat() if published else None
        result.append(item)
    result.sort(key=lambda item: item["published_iso"] or "", reverse=True)
    return result[: config["collection"]["max_candidates"]]


def collect(config: dict) -> tuple[list[dict], list[dict], dict[str, int]]:
    items = []
    errors = []
    source_counts = {}
    per_source = config["collection"]["per_source"]
    with ThreadPoolExecutor(max_workers=min(12, len(config["discovery_sources"]))) as executor:
        futures = {
            executor.submit(fetch_source, source, per_source): source
            for source in config["discovery_sources"]
        }
        for future in as_completed(futures):
            source = futures[future]
            try:
                source_items = future.result()
                source_counts[source["name"]] = len(source_items)
                items.extend(source_items)
            except Exception as error:
                source_counts[source["name"]] = 0
                errors.append({"source": source["name"], "error": str(error)})
    return filter_candidates(items, config), errors, source_counts


def write_output(
    candidates: list[dict],
    errors: list[dict],
    source_counts: dict[str, int],
    output_root: Path,
) -> Path:
    run_dir = output_root / datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
    run_dir.mkdir(parents=True, exist_ok=False)
    output = run_dir / "raw_candidates.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "fetched_source_counts": source_counts,
        "source_errors": errors,
        "candidates": candidates,
    }
    with output.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect unscored AI topic candidates.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=ROOT / "topics")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config.resolve())
    candidates, errors, source_counts = collect(config)
    output = write_output(candidates, errors, source_counts, args.output_root.resolve())
    print(output)


if __name__ == "__main__":
    main()
