import json

from scraper import ScrapedArticle
from scripts import dry_run_scrape
from state import sha256_text


def test_dry_run_scrape_includes_required_article_ids(tmp_path, monkeypatch):
    calls = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SUPPORT_BASE_URL", "https://support.optisigns.com")
    monkeypatch.setenv("SUPPORT_LOCALE", "en-us")
    monkeypatch.setenv("MAX_ARTICLES", "2")

    def fake_fetch_articles(base_url, locale, max_articles, required_article_ids):
        calls["fetch"] = (base_url, locale, max_articles, required_article_ids)
        return [{"id": 1}]

    def fake_write_markdown_articles(articles, base_url, output_dir, previous_state):
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "article.md"
        path.write_text("# Article", encoding="utf-8")
        return [
            ScrapedArticle(
                id=1,
                slug="article",
                title="Article",
                url="https://support.optisigns.com/a/1",
                updated_at="2026-07-03T00:00:00Z",
                content_hash=sha256_text("# Article"),
                markdown_path=path,
                status="added",
            )
        ]

    monkeypatch.setattr(dry_run_scrape, "fetch_articles", fake_fetch_articles)
    monkeypatch.setattr(dry_run_scrape, "write_markdown_articles", fake_write_markdown_articles)

    assert dry_run_scrape.main() == 0

    run_log = json.loads((tmp_path / "data" / "run-log.json").read_text(encoding="utf-8"))
    assert calls["fetch"] == ("https://support.optisigns.com", "en-us", 2, [360051014713])
    assert run_log["mode"] == "dry_run_scrape_only"
    assert run_log["required_article_ids"] == [360051014713]
    assert run_log["files_uploaded"] == 0
