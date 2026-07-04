from markdown_cleaner import article_to_markdown, clean_markdown, normalize_article_url, slugify


def test_slugify_keeps_readable_ascii_slug():
    assert slugify("How do I add a YouTube Video?", "fallback") == "how-do-i-add-a-youtube-video"


def test_slugify_uses_fallback_when_title_has_no_ascii_words():
    assert slugify("!!!", "12345") == "12345"


def test_normalize_article_url_prefers_zendesk_html_url():
    assert (
        normalize_article_url(
            "https://support.optisigns.com",
            "https://support.optisigns.com/hc/en-us/articles/123-real",
            123,
        )
        == "https://support.optisigns.com/hc/en-us/articles/123-real"
    )


def test_normalize_article_url_builds_fallback_from_base_url():
    assert (
        normalize_article_url("https://support.optisigns.com/", None, 123)
        == "https://support.optisigns.com/hc/en-us/articles/123"
    )


def test_clean_markdown_removes_page_chrome_and_resolves_relative_urls():
    html = """
    <nav>Navigation</nav>
    <h2>Steps</h2>
    <p>Open <a href="/hc/en-us/articles/42">the article</a>.</p>
    <img src="/attachments/example.png" alt="Example">
    <script>alert("tracking")</script>
    """

    markdown = clean_markdown(html, "https://support.optisigns.com/hc/en-us/articles/99")

    assert "Navigation" not in markdown
    assert "tracking" not in markdown
    assert "## Steps" in markdown
    assert "(https://support.optisigns.com/hc/en-us/articles/42)" in markdown
    assert "https://support.optisigns.com/attachments/example.png" in markdown


def test_clean_markdown_preserves_code_blocks():
    markdown = clean_markdown("<pre><code>print('hello')</code></pre>", "https://support.optisigns.com")

    assert "```" in markdown
    assert "print('hello')" in markdown


def test_article_to_markdown_includes_article_url_and_title():
    article = {
        "id": 123,
        "title": "Add YouTube",
        "slug": "add-youtube",
        "html_url": "https://support.optisigns.com/hc/en-us/articles/123",
        "updated_at": "2026-07-03T00:00:00Z",
        "body": "<h2>Steps</h2><p>Open the app.</p>",
    }

    slug, markdown = article_to_markdown(article, "https://support.optisigns.com")

    assert slug == "add-youtube"
    assert "Article URL: https://support.optisigns.com/hc/en-us/articles/123" in markdown
    assert "# Add YouTube" in markdown
    assert "## Steps" in markdown


def test_article_to_markdown_escapes_quotes_in_frontmatter():
    article = {
        "id": 456,
        "title": 'Use "Tagged" Playlists',
        "body": "<p>Body</p>",
    }

    slug, markdown = article_to_markdown(article, "https://support.optisigns.com")

    assert slug == "use-tagged-playlists"
    assert 'title: "Use \'Tagged\' Playlists"' in markdown
    assert "Article URL: https://support.optisigns.com/hc/en-us/articles/456" in markdown
