from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify as md

NOISE_SELECTORS = "script, style, nav, footer, header, aside, form"
RELATIVE_URL_TAGS = {
    "a": "href",
    "img": "src",
}


def slugify(value: str, fallback: str) -> str:
    value = unescape(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or fallback


def normalize_article_url(base_url: str, html_url: str | None, article_id: int) -> str:
    if html_url:
        return html_url
    return urljoin(base_url.rstrip("/") + "/", f"hc/en-us/articles/{article_id}")


def remove_page_noise(soup: BeautifulSoup) -> None:
    for element in soup.select(NOISE_SELECTORS):
        element.decompose()


def normalize_links(soup: BeautifulSoup, base_url: str) -> None:
    for tag_name, attr in RELATIVE_URL_TAGS.items():
        for tag in soup.find_all(tag_name):
            if tag.get(attr):
                tag[attr] = urljoin(base_url.rstrip("/") + "/", tag[attr])


def html_to_markdown(soup: BeautifulSoup) -> str:
    markdown = md(str(soup), heading_style="ATX", bullets="-", code_language="", strip=["span"])
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    return markdown.strip()


def clean_markdown(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    remove_page_noise(soup)
    normalize_links(soup, base_url)
    return html_to_markdown(soup)


def article_frontmatter(title: str, article_url: str, updated_at: str) -> list[str]:
    safe_title = title.replace('"', "'")
    return [
        "---",
        f'title: "{safe_title}"',
        f'article_url: "{article_url}"',
        f'updated_at: "{updated_at}"',
        "---",
    ]


def article_to_markdown(article: dict, base_url: str) -> tuple[str, str]:
    article_id = int(article["id"])
    title = article.get("title") or f"Article {article_id}"
    slug = slugify(article.get("slug") or title, fallback=str(article_id))
    article_url = normalize_article_url(base_url, article.get("html_url"), article_id)
    updated_at = article.get("updated_at") or ""
    body = clean_markdown(article.get("body") or "", article_url)

    content = "\n".join(
        article_frontmatter(title, article_url, updated_at)
        + [
            "",
            f"Article URL: {article_url}",
            "",
            f"# {title}",
            "",
            body,
            "",
        ]
    )
    return slug, content
