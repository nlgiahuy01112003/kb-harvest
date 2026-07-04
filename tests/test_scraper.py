from pathlib import Path

import pytest

import scraper
from scraper import fetch_articles, write_markdown_articles


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, pages):
        self.pages = list(pages)
        self.requested_urls = []

    def get(self, url, timeout):
        self.requested_urls.append((url, timeout))
        if not self.pages:
            raise AssertionError("Unexpected extra request")
        return FakeResponse(self.pages.pop(0))


def make_article(article_id=1, title="Add YouTube", body="<p>Use the app.</p>"):
    return {
        "id": article_id,
        "title": title,
        "slug": title.lower().replace(" ", "-"),
        "html_url": f"https://support.optisigns.com/hc/en-us/articles/{article_id}",
        "updated_at": "2026-07-03T00:00:00Z",
        "body": body,
    }


def test_fetch_articles_paginates_and_respects_max(monkeypatch):
    fake_session = FakeSession(
        [
            {
                "articles": [make_article(1), make_article(2)],
                "next_page": "https://support.optisigns.com/api/page-2",
            },
            {"articles": [make_article(3), make_article(4)], "next_page": None},
        ]
    )
    monkeypatch.setattr(scraper.requests, "Session", lambda: fake_session)

    articles = fetch_articles("https://support.optisigns.com", "en-us", max_articles=3)

    assert [article["id"] for article in articles] == [1, 2, 3]
    assert fake_session.requested_urls == [
        ("https://support.optisigns.com/api/v2/help_center/en-us/articles.json", 30),
        ("https://support.optisigns.com/api/page-2", 30),
    ]


def test_fetch_articles_stops_after_first_page_when_max_is_reached(monkeypatch):
    fake_session = FakeSession(
        [
            {
                "articles": [make_article(1), make_article(2), make_article(3)],
                "next_page": "https://support.optisigns.com/api/page-2",
            }
        ]
    )
    monkeypatch.setattr(scraper.requests, "Session", lambda: fake_session)

    articles = fetch_articles("https://support.optisigns.com", "en-us", max_articles=2)

    assert [article["id"] for article in articles] == [1, 2]
    assert len(fake_session.requested_urls) == 1


def test_fetch_articles_appends_required_articles_not_in_first_page(monkeypatch):
    fake_session = FakeSession(
        [
            {
                "articles": [make_article(1), make_article(2)],
                "next_page": "https://support.optisigns.com/api/page-2",
            },
            {"article": make_article(360051014713, title="How to use YouTube with OptiSigns")},
        ]
    )
    monkeypatch.setattr(scraper.requests, "Session", lambda: fake_session)

    articles = fetch_articles(
        "https://support.optisigns.com",
        "en-us",
        max_articles=2,
        required_article_ids=[360051014713],
    )

    assert [article["id"] for article in articles] == [1, 2, 360051014713]
    assert fake_session.requested_urls == [
        ("https://support.optisigns.com/api/v2/help_center/en-us/articles.json", 30),
        (
            "https://support.optisigns.com/api/v2/help_center/en-us/articles/360051014713.json",
            30,
        ),
    ]


def test_fetch_articles_does_not_refetch_required_article_already_seen(monkeypatch):
    fake_session = FakeSession(
        [
            {
                "articles": [make_article(360051014713), make_article(2)],
                "next_page": None,
            },
        ]
    )
    monkeypatch.setattr(scraper.requests, "Session", lambda: fake_session)

    articles = fetch_articles(
        "https://support.optisigns.com",
        "en-us",
        max_articles=2,
        required_article_ids=[360051014713],
    )

    assert [article["id"] for article in articles] == [360051014713, 2]
    assert len(fake_session.requested_urls) == 1


def test_fetch_articles_raises_http_errors(monkeypatch):
    class ErrorResponse(FakeResponse):
        def raise_for_status(self):
            raise RuntimeError("HTTP 500")

    class ErrorSession:
        def get(self, url, timeout):
            return ErrorResponse({})

    monkeypatch.setattr(scraper.requests, "Session", ErrorSession)

    with pytest.raises(RuntimeError, match="HTTP 500"):
        fetch_articles("https://support.optisigns.com", "en-us", max_articles=1)


def test_write_markdown_articles_marks_new_articles_added(tmp_path):
    state = {"articles": {}, "gemini": {"file_search_store_name": ""}}

    results = write_markdown_articles(
        [make_article(10)],
        "https://support.optisigns.com",
        tmp_path,
        state,
    )

    assert results[0].status == "added"
    assert results[0].markdown_path == tmp_path / "add-youtube.md"
    assert results[0].markdown_path.exists()
    assert state["articles"]["10"]["hash"]


def test_write_markdown_articles_marks_unchanged_articles_skipped(tmp_path):
    state = {"articles": {}, "gemini": {"file_search_store_name": ""}}
    article = make_article(11)

    first = write_markdown_articles([article], "https://support.optisigns.com", tmp_path, state)
    second = write_markdown_articles([article], "https://support.optisigns.com", tmp_path, state)

    assert first[0].status == "added"
    assert second[0].status == "skipped"


def test_write_markdown_articles_marks_content_changes_updated(tmp_path):
    state = {"articles": {}, "gemini": {"file_search_store_name": ""}}
    article = make_article(12, body="<p>Old body.</p>")
    changed_article = make_article(12, body="<p>New body.</p>")

    write_markdown_articles([article], "https://support.optisigns.com", tmp_path, state)
    results = write_markdown_articles([changed_article], "https://support.optisigns.com", tmp_path, state)

    assert results[0].status == "updated"
    assert "New body" in Path(results[0].markdown_path).read_text(encoding="utf-8")
