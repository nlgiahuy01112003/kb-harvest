from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper import fetch_articles, write_markdown_articles
from state import load_state, write_json

DEFAULT_REQUIRED_ARTICLE_IDS = "360051014713"


def parse_required_article_ids(value: str) -> list[int]:
    ids: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if item:
            ids.append(int(item))
    return ids


def main() -> int:
    load_dotenv()
    data_dir = Path("data")
    base_url = os.getenv("SUPPORT_BASE_URL", "https://support.optisigns.com")
    locale = os.getenv("SUPPORT_LOCALE", "en-us")
    max_articles = int(os.getenv("MAX_ARTICLES", "35"))
    required_article_ids = parse_required_article_ids(
        os.getenv("SUPPORT_REQUIRED_ARTICLE_IDS", DEFAULT_REQUIRED_ARTICLE_IDS)
    )
    state = load_state(data_dir / "state.json")

    articles = fetch_articles(
        base_url=base_url,
        locale=locale,
        max_articles=max_articles,
        required_article_ids=required_article_ids,
    )
    scraped = write_markdown_articles(
        articles=articles,
        base_url=base_url,
        output_dir=data_dir / "markdown",
        previous_state=state,
    )
    log = {
        "mode": "dry_run_scrape_only",
        "required_article_ids": required_article_ids,
        "articles_seen": len(scraped),
        "added": sum(1 for article in scraped if article.status == "added"),
        "updated": sum(1 for article in scraped if article.status == "updated"),
        "skipped": sum(1 for article in scraped if article.status == "skipped"),
        "files_uploaded": 0,
    }
    write_json(data_dir / "run-log.json", log)
    print(json.dumps(log, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
