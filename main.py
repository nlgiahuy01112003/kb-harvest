from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from scraper import (
    ScrapedArticle,
    STATUS_ADDED,
    STATUS_SKIPPED,
    STATUS_UPDATED,
    fetch_articles,
    write_markdown_articles,
)
from state import load_state, save_state, write_json
from gemini_uploader import (
    ensure_file_search_store,
    estimate_chunks,
    get_client,
    remove_documents,
    upload_files,
)

DATA_DIR = Path("data")
MARKDOWN_DIR = DATA_DIR / "markdown"
STATE_PATH = DATA_DIR / "state.json"
RUN_LOG_PATH = DATA_DIR / "run-log.json"
DEFAULT_REQUIRED_ARTICLE_IDS = "360051014713"


@dataclass(frozen=True)
class SyncConfig:
    support_base_url: str
    support_locale: str
    max_articles: int
    required_article_ids: list[int]

    @classmethod
    def from_env(cls) -> "SyncConfig":
        return cls(
            support_base_url=os.getenv("SUPPORT_BASE_URL", "https://support.optisigns.com"),
            support_locale=os.getenv("SUPPORT_LOCALE", "en-us"),
            max_articles=int(os.getenv("MAX_ARTICLES", "35")),
            required_article_ids=parse_required_article_ids(
                os.getenv("SUPPORT_REQUIRED_ARTICLE_IDS", DEFAULT_REQUIRED_ARTICLE_IDS)
            ),
        )


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def parse_required_article_ids(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def upload_changed_articles(
    client,
    store_name: str,
    changed_articles: list[ScrapedArticle],
    state: dict,
) -> list[str]:
    if not changed_articles:
        logging.getLogger("main").info("No article changes detected; upload skipped.")
        return []

    stale_document_names = [
        state["articles"].get(str(article.id), {}).get("gemini_document_name", "")
        for article in changed_articles
        if article.status == STATUS_UPDATED
    ]
    upload_paths = [article.markdown_path for article in changed_articles]
    remove_documents(client, stale_document_names)
    uploaded_document_names = upload_files(client, store_name, upload_paths)

    for article, document_name in zip(changed_articles, uploaded_document_names, strict=True):
        state["articles"][str(article.id)]["gemini_document_name"] = document_name

    return uploaded_document_names


def count_article_statuses(scraped_articles: list[ScrapedArticle]) -> dict[str, int]:
    return {
        "added": sum(1 for article in scraped_articles if article.status == STATUS_ADDED),
        "updated": sum(1 for article in scraped_articles if article.status == STATUS_UPDATED),
        "skipped": sum(1 for article in scraped_articles if article.status == STATUS_SKIPPED),
    }


def changed_markdown_paths(scraped_articles: list[ScrapedArticle]) -> list[Path]:
    return [
        article.markdown_path
        for article in scraped_articles
        if article.status in {STATUS_ADDED, STATUS_UPDATED}
    ]


def build_run_log(
    config: SyncConfig,
    scraped_articles: list[ScrapedArticle],
    uploaded_document_names: list[str],
    store_name: str,
) -> dict:
    changed_paths = changed_markdown_paths(scraped_articles)
    counts = count_article_statuses(scraped_articles)

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "support_base_url": config.support_base_url,
        "locale": config.support_locale,
        "required_article_ids": config.required_article_ids,
        "articles_seen": len(scraped_articles),
        **counts,
        "files_uploaded": len(uploaded_document_names),
        "uploaded_document_names": uploaded_document_names,
        "estimated_chunks": estimate_chunks(changed_paths) if changed_paths else 0,
        "gemini_file_search_store_name": store_name,
    }


def run_sync(config: SyncConfig) -> dict:
    logger = logging.getLogger("main")
    state = load_state(STATE_PATH)

    logger.info("Starting OptiBot knowledge sync.")
    articles = fetch_articles(
        base_url=config.support_base_url,
        locale=config.support_locale,
        max_articles=config.max_articles,
        required_article_ids=config.required_article_ids,
    )
    scraped_articles = write_markdown_articles(
        articles=articles,
        base_url=config.support_base_url,
        output_dir=MARKDOWN_DIR,
        previous_state=state,
    )
    changed_articles = [
        article for article in scraped_articles if article.status in {STATUS_ADDED, STATUS_UPDATED}
    ]

    client = get_client()
    store_name = ensure_file_search_store(client, state)
    save_state(STATE_PATH, state)

    uploaded_document_names = upload_changed_articles(client, store_name, changed_articles, state)
    run_log = build_run_log(config, scraped_articles, uploaded_document_names, store_name)
    write_json(RUN_LOG_PATH, run_log)
    save_state(STATE_PATH, state)

    logger.info(
        "Run complete: added=%s updated=%s skipped=%s uploaded=%s estimated_chunks=%s",
        run_log["added"],
        run_log["updated"],
        run_log["skipped"],
        len(uploaded_document_names),
        run_log["estimated_chunks"],
    )
    return run_log


def main() -> int:
    load_dotenv()
    configure_logging()
    run_sync(SyncConfig.from_env())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
