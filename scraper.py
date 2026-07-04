from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests

from markdown_cleaner import article_to_markdown
from state import sha256_text

LOGGER = logging.getLogger(__name__)
STATUS_ADDED = "added"
STATUS_UPDATED = "updated"
STATUS_SKIPPED = "skipped"


@dataclass(frozen=True)
class ScrapedArticle:
    id: int
    slug: str
    title: str
    url: str
    updated_at: str
    content_hash: str
    markdown_path: Path
    status: str


def _articles_endpoint(base_url: str, locale: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", f"api/v2/help_center/{locale}/articles.json")


def _article_endpoint(base_url: str, locale: str, article_id: int) -> str:
    return urljoin(
        base_url.rstrip("/") + "/",
        f"api/v2/help_center/{locale}/articles/{article_id}.json",
    )


def fetch_article(base_url: str, locale: str, article_id: int, session: requests.Session) -> dict:
    url = _article_endpoint(base_url, locale, article_id)
    LOGGER.info("Fetching required article %s", url)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.json()["article"]


def fetch_articles(
    base_url: str,
    locale: str,
    max_articles: int,
    required_article_ids: Iterable[int] | None = None,
) -> list[dict]:
    articles: list[dict] = []
    next_page: str | None = _articles_endpoint(base_url, locale)
    session = requests.Session()

    while next_page and len(articles) < max_articles:
        LOGGER.info("Fetching %s", next_page)
        response = session.get(next_page, timeout=30)
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("articles", [])
        articles.extend(batch)
        next_page = payload.get("next_page")

    articles = articles[:max_articles]
    seen_ids = {int(article["id"]) for article in articles}

    for article_id in required_article_ids or []:
        if article_id in seen_ids:
            continue
        article = fetch_article(base_url, locale, article_id, session)
        articles.append(article)
        seen_ids.add(article_id)

    return articles


def detect_status(previous_hash: str | None, current_hash: str) -> str:
    if previous_hash is None:
        return STATUS_ADDED
    if previous_hash != current_hash:
        return STATUS_UPDATED
    return STATUS_SKIPPED


def article_state_record(
    article: dict,
    slug: str,
    content_hash: str,
    markdown_path: Path,
    previous_article_state: dict,
) -> dict:
    return {
        "slug": slug,
        "title": article.get("title") or "",
        "url": article.get("html_url") or "",
        "updated_at": article.get("updated_at") or "",
        "hash": content_hash,
        "markdown_path": str(markdown_path),
        "gemini_document_name": previous_article_state.get("gemini_document_name", ""),
    }


def write_markdown_articles(
    articles: Iterable[dict],
    base_url: str,
    output_dir: Path,
    previous_state: dict,
) -> list[ScrapedArticle]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[ScrapedArticle] = []
    known_articles = previous_state.setdefault("articles", {})

    for article in articles:
        article_id = int(article["id"])
        state_key = str(article_id)
        previous_article_state = known_articles.get(state_key, {})
        slug, markdown = article_to_markdown(article, base_url)
        path = output_dir / f"{slug}.md"
        content_hash = sha256_text(markdown)
        previous_hash = previous_article_state.get("hash")
        status = detect_status(previous_hash, content_hash)

        if status != STATUS_SKIPPED or not path.exists():
            path.write_text(markdown, encoding="utf-8")

        known_articles[state_key] = article_state_record(
            article=article,
            slug=slug,
            content_hash=content_hash,
            markdown_path=path,
            previous_article_state=previous_article_state,
        )

        results.append(
            ScrapedArticle(
                id=article_id,
                slug=slug,
                title=article.get("title") or "",
                url=article.get("html_url") or "",
                updated_at=article.get("updated_at") or "",
                content_hash=content_hash,
                markdown_path=path,
                status=status,
            )
        )

    return results
