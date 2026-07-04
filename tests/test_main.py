import json
from pathlib import Path

import main
from scraper import ScrapedArticle
from state import sha256_text


def test_parse_required_article_ids_accepts_comma_separated_values():
    assert main.parse_required_article_ids("360051014713, 48626115821459") == [
        360051014713,
        48626115821459,
    ]


def test_parse_required_article_ids_ignores_empty_values():
    assert main.parse_required_article_ids("360051014713,, ") == [360051014713]


def test_main_scrapes_uploads_only_changed_articles_and_writes_logs(tmp_path, monkeypatch):
    markdown_dir = tmp_path / "markdown"
    state_path = tmp_path / "state.json"
    run_log_path = tmp_path / "run-log.json"
    calls = {
        "fetch": None,
        "removed": None,
        "uploaded_paths": None,
    }

    monkeypatch.setattr(main, "MARKDOWN_DIR", markdown_dir)
    monkeypatch.setattr(main, "STATE_PATH", state_path)
    monkeypatch.setattr(main, "RUN_LOG_PATH", run_log_path)
    monkeypatch.setenv("SUPPORT_BASE_URL", "https://support.optisigns.com")
    monkeypatch.setenv("SUPPORT_LOCALE", "en-us")
    monkeypatch.setenv("MAX_ARTICLES", "2")

    def fake_fetch_articles(base_url, locale, max_articles, required_article_ids):
        calls["fetch"] = (base_url, locale, max_articles, required_article_ids)
        return [{"id": 1}, {"id": 2}]

    def fake_write_markdown_articles(articles, base_url, output_dir, previous_state):
        output_dir.mkdir(parents=True, exist_ok=True)
        added_path = output_dir / "added.md"
        skipped_path = output_dir / "skipped.md"
        added_path.write_text("# Added", encoding="utf-8")
        skipped_path.write_text("# Skipped", encoding="utf-8")
        previous_state.setdefault("articles", {})
        previous_state["articles"]["1"] = {
            "slug": "added",
            "title": "Added",
            "url": "https://support.optisigns.com/a/1",
            "updated_at": "2026-07-03T00:00:00Z",
            "hash": sha256_text("# Added"),
            "markdown_path": str(added_path),
            "gemini_document_name": "",
        }
        previous_state["articles"]["2"] = {
            "slug": "skipped",
            "title": "Skipped",
            "url": "https://support.optisigns.com/a/2",
            "updated_at": "2026-07-03T00:00:00Z",
            "hash": sha256_text("# Skipped"),
            "markdown_path": str(skipped_path),
            "gemini_document_name": "documents/old-skipped",
        }
        return [
            ScrapedArticle(
                id=1,
                slug="added",
                title="Added",
                url="https://support.optisigns.com/a/1",
                updated_at="2026-07-03T00:00:00Z",
                content_hash=sha256_text("# Added"),
                markdown_path=added_path,
                status="added",
            ),
            ScrapedArticle(
                id=2,
                slug="skipped",
                title="Skipped",
                url="https://support.optisigns.com/a/2",
                updated_at="2026-07-03T00:00:00Z",
                content_hash=sha256_text("# Skipped"),
                markdown_path=skipped_path,
                status="skipped",
            ),
        ]

    monkeypatch.setattr(main, "fetch_articles", fake_fetch_articles)
    monkeypatch.setattr(main, "write_markdown_articles", fake_write_markdown_articles)
    monkeypatch.setattr(main, "get_client", lambda: object())
    monkeypatch.setattr(main, "ensure_file_search_store", lambda client, state: "stores/test")
    monkeypatch.setattr(main, "remove_documents", lambda client, names: calls.update(removed=names))
    monkeypatch.setattr(
        main,
        "upload_files",
        lambda client, store_name, paths: calls.update(uploaded_paths=paths) or ["documents/new-added"],
    )

    assert main.main() == 0

    state = json.loads(state_path.read_text(encoding="utf-8"))
    run_log = json.loads(run_log_path.read_text(encoding="utf-8"))
    assert calls["fetch"] == ("https://support.optisigns.com", "en-us", 2, [360051014713])
    assert calls["removed"] == []
    assert [Path(path).name for path in calls["uploaded_paths"]] == ["added.md"]
    assert state["articles"]["1"]["gemini_document_name"] == "documents/new-added"
    assert state["articles"]["2"]["gemini_document_name"] == "documents/old-skipped"
    assert run_log["added"] == 1
    assert run_log["updated"] == 0
    assert run_log["skipped"] == 1
    assert run_log["files_uploaded"] == 1
    assert run_log["gemini_file_search_store_name"] == "stores/test"


def test_main_skips_upload_when_everything_is_unchanged(tmp_path, monkeypatch):
    markdown_dir = tmp_path / "markdown"
    state_path = tmp_path / "state.json"
    run_log_path = tmp_path / "run-log.json"
    upload_called = False

    monkeypatch.setattr(main, "MARKDOWN_DIR", markdown_dir)
    monkeypatch.setattr(main, "STATE_PATH", state_path)
    monkeypatch.setattr(main, "RUN_LOG_PATH", run_log_path)
    monkeypatch.setattr(
        main,
        "fetch_articles",
        lambda base_url, locale, max_articles, required_article_ids: [{"id": 1}],
    )

    def fake_write_markdown_articles(articles, base_url, output_dir, previous_state):
        path = output_dir / "same.md"
        output_dir.mkdir(parents=True, exist_ok=True)
        path.write_text("# Same", encoding="utf-8")
        previous_state.setdefault("articles", {})["1"] = {
            "slug": "same",
            "title": "Same",
            "url": "https://support.optisigns.com/a/1",
            "updated_at": "2026-07-03T00:00:00Z",
            "hash": sha256_text("# Same"),
            "markdown_path": str(path),
            "gemini_document_name": "documents/same",
        }
        return [
            ScrapedArticle(
                id=1,
                slug="same",
                title="Same",
                url="https://support.optisigns.com/a/1",
                updated_at="2026-07-03T00:00:00Z",
                content_hash=sha256_text("# Same"),
                markdown_path=path,
                status="skipped",
            )
        ]

    def fake_upload_files(client, store_name, paths):
        nonlocal upload_called
        upload_called = True
        return []

    monkeypatch.setattr(main, "write_markdown_articles", fake_write_markdown_articles)
    monkeypatch.setattr(main, "get_client", lambda: object())
    monkeypatch.setattr(main, "ensure_file_search_store", lambda client, state: "stores/test")
    monkeypatch.setattr(main, "remove_documents", lambda client, names: None)
    monkeypatch.setattr(main, "upload_files", fake_upload_files)

    assert main.main() == 0

    run_log = json.loads(run_log_path.read_text(encoding="utf-8"))
    assert upload_called is False
    assert run_log["skipped"] == 1
    assert run_log["files_uploaded"] == 0


def test_main_uploads_skipped_article_when_gemini_document_is_missing(tmp_path, monkeypatch):
    markdown_dir = tmp_path / "markdown"
    state_path = tmp_path / "state.json"
    run_log_path = tmp_path / "run-log.json"
    calls = {"uploaded_paths": None}

    monkeypatch.setattr(main, "MARKDOWN_DIR", markdown_dir)
    monkeypatch.setattr(main, "STATE_PATH", state_path)
    monkeypatch.setattr(main, "RUN_LOG_PATH", run_log_path)
    monkeypatch.setattr(
        main,
        "fetch_articles",
        lambda base_url, locale, max_articles, required_article_ids: [{"id": 360051014713}],
    )

    def fake_write_markdown_articles(articles, base_url, output_dir, previous_state):
        path = output_dir / "how-to-use-youtube-with-optisigns.md"
        output_dir.mkdir(parents=True, exist_ok=True)
        path.write_text("# How to use YouTube with OptiSigns", encoding="utf-8")
        previous_state.setdefault("articles", {})["360051014713"] = {
            "slug": "how-to-use-youtube-with-optisigns",
            "title": "How to use YouTube with OptiSigns",
            "url": "https://support.optisigns.com/hc/en-us/articles/360051014713",
            "updated_at": "2026-06-18T05:00:56Z",
            "hash": sha256_text("# How to use YouTube with OptiSigns"),
            "markdown_path": str(path),
            "gemini_document_name": "",
        }
        return [
            ScrapedArticle(
                id=360051014713,
                slug="how-to-use-youtube-with-optisigns",
                title="How to use YouTube with OptiSigns",
                url="https://support.optisigns.com/hc/en-us/articles/360051014713",
                updated_at="2026-06-18T05:00:56Z",
                content_hash=sha256_text("# How to use YouTube with OptiSigns"),
                markdown_path=path,
                status="skipped",
            )
        ]

    monkeypatch.setattr(main, "write_markdown_articles", fake_write_markdown_articles)
    monkeypatch.setattr(main, "get_client", lambda: object())
    monkeypatch.setattr(main, "ensure_file_search_store", lambda client, state: "stores/test")
    monkeypatch.setattr(main, "remove_documents", lambda client, names: None)
    monkeypatch.setattr(
        main,
        "upload_files",
        lambda client, store_name, paths: calls.update(uploaded_paths=paths)
        or ["documents/youtube"],
    )

    assert main.main() == 0

    state = json.loads(state_path.read_text(encoding="utf-8"))
    run_log = json.loads(run_log_path.read_text(encoding="utf-8"))
    assert [Path(path).name for path in calls["uploaded_paths"]] == [
        "how-to-use-youtube-with-optisigns.md"
    ]
    assert state["articles"]["360051014713"]["gemini_document_name"] == "documents/youtube"
    assert run_log["skipped"] == 1
    assert run_log["files_uploaded"] == 1
    assert run_log["estimated_chunks"] >= 1
