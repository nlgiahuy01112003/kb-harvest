# Section 2: Coding And Deploying

## 4. Rebuild Step By Step

Create the project:

```bash
mkdir kb-harvest
cd kb-harvest
git init
python3 -m venv .venv
source .venv/bin/activate
```

Create required folders and placeholder files:

```bash
mkdir -p data/markdown scripts tests .github/workflows screenshots
touch data/markdown/.gitkeep
```

Create `requirements.txt`:

```txt
beautifulsoup4==4.12.3
google-genai==2.10.0
markdownify==0.13.1
python-dotenv==1.0.1
requests==2.32.3
pytest==8.3.2
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.gitignore`:

```gitignore
.env
.env.*
!.env.sample
__pycache__/
.pytest_cache/
.venv/
data/markdown/*.md
!data/markdown/.gitkeep
data/state.json
data/run-log.json
screenshots/*.png
*.pyc
```

Create `.dockerignore`:

```txt
.env
.git
.github
.pytest_cache
.ruff_cache
.venv
__pycache__
data/markdown/*.md
data/state.json
data/run-log.json
screenshots/*.png
```

Create `pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

Create `.env.sample`:

```txt
GEMINI_API_KEY=REPLACE_ME
# API_KEY=REPLACE_ME
GEMINI_FILE_SEARCH_STORE_NAME=
SUPPORT_BASE_URL=https://support.optisigns.com
SUPPORT_LOCALE=en-us
MAX_ARTICLES=35
SUPPORT_REQUIRED_ARTICLE_IDS=360051014713
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=models/gemini-embedding-001
```

Why the required article ID exists:

```txt
The assignment asks the sample question "How do I add a YouTube video?"
The correct OptiSigns article is older than the newest article page, so max_articles=35 alone can miss it.
SUPPORT_REQUIRED_ARTICLE_IDS guarantees the sample-answer source is always in the knowledge base.
```

Exact implementation order:

```txt
1. requirements.txt
2. .gitignore
3. .dockerignore
4. pytest.ini
5. .env.sample
6. state.py
7. markdown_cleaner.py
8. scraper.py
9. gemini_uploader.py
10. main.py
11. ask_gemini.py
12. scripts/dry_run_scrape.py
13. scripts/check_no_secrets.py
14. scripts/check_deliverables.py
15. scripts/fetch_github_actions_data.py
16. Dockerfile
17. .github/workflows/daily-sync.yml
18. .github/workflows/ci.yml
19. tests/
20. Run verification commands
```

Why this order:

```txt
Start with config and state helpers, then Markdown cleaning, then Zendesk scraping, then Gemini upload, then orchestration. After the core path works, add Docker, GitHub Actions, safety scripts, and tests.
```

Verification checkpoint after each file:

```txt
After every Python file:
python3 -m compileall <file>

After every core module:
pytest tests/<matching_test_file>.py -q

After GitHub/Docker files:
docker build -t kb-harvest .
python3 scripts/check_deliverables.py

Before commit:
pytest -q
python3 scripts/check_no_secrets.py
git status --short
```

### 4.1 Configuration Files Explained

`requirements.txt`

Purpose:

```txt
Pins the Python dependencies needed by local runs, Docker, CI, and GitHub Actions.
```

Why each dependency exists:

```txt
beautifulsoup4  -> parse and clean Zendesk article HTML
markdownify     -> convert cleaned HTML into Markdown
requests        -> call Zendesk Help Center API
google-genai    -> create File Search Store, upload Markdown, ask Gemini
python-dotenv   -> load local .env during development
pytest          -> run bonus tests
```

Verify:

```bash
pip install -r requirements.txt
python3 -m compileall .
```

`.gitignore`

Purpose:

```txt
Prevents local secrets and generated data from being committed.
```

Important ignored files:

```txt
.env
.venv/
data/markdown/*.md
data/state.json
data/run-log.json
screenshots/*.png
```

Why generated Markdown is ignored:

```txt
The assignment asks for source code in GitHub. Generated Markdown is produced by the job and uploaded as GitHub Actions artifacts, not committed as source.
```

`.dockerignore`

Purpose:

```txt
Keeps the Docker build context small and prevents local secrets/generated files from being copied into the image.
```

Important difference from `.gitignore`:

```txt
.gitignore controls git tracking.
.dockerignore controls what Docker can COPY into the image.
Both are needed.
```

`pytest.ini`

Purpose:

```txt
Makes pytest consistently discover tests and import local modules.
```

Settings:

```txt
pythonpath = .
testpaths = tests
```

`.env.sample`

Purpose:

```txt
Documents required environment variables without exposing real secrets.
```

Rules:

```txt
Commit .env.sample.
Never commit .env.
Put real GEMINI_API_KEY in local .env or GitHub Actions repository secrets.
```

Verify config safety:

```bash
python3 scripts/check_no_secrets.py
git status --short
```

## 5. `state.py`

Purpose:

- Keep a stable local record of article hashes.
- Store Gemini File Search Store name.
- Store Gemini document names for uploaded articles.

When to write this file:

```txt
Write this first after config files. Almost every other file needs either JSON state, SHA-256 hashing, or JSON output.
```

Dependencies:

```txt
Standard library only:
- json
- hashlib
- pathlib.Path
- typing.Any
```

Input and output:

```txt
Input:
- data/state.json path
- Markdown string to hash
- JSON payload for run-log

Output:
- Python dict state object
- saved data/state.json
- saved data/run-log.json
- deterministic SHA-256 hash string
```

Important functions:

`load_state(path)`

- If the file does not exist, returns a default dictionary.
- Ensures expected keys exist.

`save_state(path, state)`

- Writes state as formatted JSON.
- Creates parent folders if needed.

`sha256_text(value)`

- Hashes Markdown content.
- Used for delta detection.

`write_json(path, payload)`

- Writes `run-log.json`.

Why this matters:

```txt
The daily job can compare today’s article content with the previous run and upload only changed files.
```

How to verify after writing:

```bash
python3 -m compileall state.py
pytest tests/test_state.py -q
```

Common mistake:

```txt
Do not return DEFAULT_STATE directly. Return a copied/default JSON object so tests or later code do not mutate the module-level default by accident.
```

## 6. `markdown_cleaner.py`

Purpose:

- Convert Zendesk article HTML to clean Markdown.

When to write this file:

```txt
Write after state.py and before scraper.py. The scraper depends on this file to convert each Zendesk article body into Markdown.
```

Dependencies:

```txt
External:
- beautifulsoup4
- markdownify

Standard library:
- re
- urllib.parse.urljoin
```

Input and output:

```txt
Input:
- one Zendesk article dictionary
- article body HTML
- support base URL

Output:
- filename-safe slug
- final Markdown content with frontmatter and Article URL line
```

Important functions:

`slugify(value, fallback)`

- Converts article titles/slugs into safe filenames.
- Example:

```txt
"How do I add a YouTube Video?" -> "how-do-i-add-a-youtube-video"
```

`normalize_article_url(base_url, html_url, article_id)`

- Uses Zendesk `html_url` if present.
- Falls back to a predictable support article URL.

`clean_markdown(html, base_url)`

- Parses HTML with BeautifulSoup.
- Removes unwanted layout tags.
- Normalizes `href` and `src` links.
- Converts HTML to Markdown with `markdownify`.
- Collapses excessive blank lines.

`article_to_markdown(article, base_url)`

- Creates final Markdown file content.
- Adds frontmatter.
- Adds `Article URL:` line for citations.
- Adds `# Article title`.

Why this matters:

```txt
Gemini should retrieve clean article content, not website navigation, ads, scripts, or sidebars.
```

How to verify after writing:

```bash
python3 -m compileall markdown_cleaner.py
pytest tests/test_markdown_cleaner.py -q
```

Common mistakes:

```txt
Do not use regex alone to parse HTML.
Do not remove headings or links, because retrieval quality depends on article structure.
Do not forget the Article URL line, because citations depend on it.
```

## 7. `scraper.py`

Purpose:

- Fetch articles from Zendesk.
- Write Markdown files.
- Detect whether each article is added, updated, or skipped.

When to write this file:

```txt
Write after markdown_cleaner.py. At this point, the project can fetch raw articles and convert them into Markdown files.
```

Dependencies:

```txt
External:
- requests

Internal:
- markdown_cleaner.article_to_markdown
- state.sha256_text
```

Input and output:

```txt
Input:
- SUPPORT_BASE_URL
- SUPPORT_LOCALE
- MAX_ARTICLES
- SUPPORT_REQUIRED_ARTICLE_IDS
- previous state dictionary

Output:
- data/markdown/<slug>.md files
- updated state["articles"]
- list[ScrapedArticle]
```

Important objects/functions:

`ScrapedArticle`

- Dataclass that describes one processed article.
- Fields include:

```txt
id
slug
title
url
updated_at
content_hash
markdown_path
status
```

`_articles_endpoint(base_url, locale)`

- Builds:

```txt
https://support.optisigns.com/api/v2/help_center/en-us/articles.json
```

`fetch_article(base_url, locale, article_id, session)`

- Fetches one specific Zendesk article by ID.
- Used for required sample-question articles.

`fetch_articles(base_url, locale, max_articles, required_article_ids=None)`

- Uses `requests.Session`.
- Follows Zendesk `next_page`.
- Stops after `max_articles`.
- Appends any required articles that were not already fetched.

`write_markdown_articles(...)`

- Converts each article to Markdown.
- Computes hash.
- Compares against previous state.
- Writes file if article is new/updated or file does not exist.
- Updates state with article metadata.

Status logic:

```txt
No previous hash     -> added
Different hash       -> updated
Same hash            -> skipped
```

How to verify after writing:

```bash
python3 -m compileall scraper.py
pytest tests/test_scraper.py -q
```

Common mistakes:

```txt
Do not only scrape the newest page. Follow Zendesk next_page until max_articles is reached.
Do not rely only on updated_at. Hash the cleaned Markdown because it represents the actual indexed content.
Do not forget SUPPORT_REQUIRED_ARTICLE_IDS, or the required YouTube question may retrieve the wrong article.
```

## 8. `gemini_uploader.py`

Purpose:

- Own every Gemini API operation.

When to write this file:

```txt
Write after the scraper can produce Markdown files. This file is the bridge between local Markdown and Gemini File Search.
```

Dependencies:

```txt
External:
- google-genai

Internal:
- state.load_state
```

Input and output:

```txt
Input:
- GEMINI_API_KEY or API_KEY
- Markdown file paths
- Gemini File Search Store name
- user question for ask_gemini.py

Output:
- Gemini File Search Store name
- uploaded Gemini document names
- text answer from Gemini
```

Constants:

```txt
DEFAULT_MODEL = gemini-2.5-flash
DEFAULT_EMBEDDING_MODEL = models/gemini-embedding-001
CHUNK_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 100
```

`SYSTEM_PROMPT`

Uses the required prompt verbatim:

```txt
You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply.
```

Important functions:

`estimate_chunks(paths, chunk_tokens, overlap_tokens)`

- Gives an approximate chunk count for logging.
- Gemini performs actual chunking/indexing.
- The estimate is for reporting.

`get_client()`

- Reads `GEMINI_API_KEY` or `API_KEY`.
- Returns `genai.Client`.

`resolve_store_name(state_path)`

- Gets File Search Store name from env or `data/state.json`.
- Used by the terminal bot and upload workflow.

`ensure_file_search_store(client, state)`

- Reuses an existing store if available.
- Otherwise creates a Gemini File Search Store.
- Saves store name into state.

`remove_documents(client, document_names)`

- Removes stale Gemini documents before uploading updated articles.
- Prevents duplicate/old content from staying searchable.

`upload_files(client, store_name, paths)`

- Uploads Markdown files to Gemini File Search Store.
- Uses whitespace chunking:

```txt
512 max tokens per chunk
100 overlap tokens
```

`ask_with_file_search(client, store_name, question)`

- Calls `client.models.generate_content`.
- Attaches File Search tool:

```python
types.Tool(
    file_search=types.FileSearch(
        file_search_store_names=[store_name],
        top_k=6,
    )
)
```

Why this matters:

```txt
The assignment requires API upload, not UI drag-and-drop.
```

How to verify after writing:

```bash
python3 -m compileall gemini_uploader.py
pytest tests/test_gemini_uploader.py -q
```

Common mistakes:

```txt
Do not hard-code the API key.
Do not create a new File Search Store every run unless no store exists.
For updated articles, remove old Gemini document names first to avoid stale answers.
```

## 9. `main.py`

Purpose:

- Run the whole required job once.

When to write this file:

```txt
Write after state.py, scraper.py, and gemini_uploader.py exist. main.py should orchestrate those modules, not contain all implementation details itself.
```

Dependencies:

```txt
External:
- python-dotenv

Internal:
- scraper
- state
- gemini_uploader
```

Input and output:

```txt
Input:
- environment variables
- data/state.json if it exists
- Zendesk article data from scraper.py

Output:
- data/markdown/*.md
- data/state.json
- data/run-log.json
- uploaded Gemini documents
- process exit code 0 on success
```

Flow:

```txt
load .env
load data/state.json
fetch Zendesk articles
write Markdown
find added/updated articles
create/reuse Gemini File Search Store
delete stale Gemini docs for updated articles
upload changed Markdown files
write data/run-log.json
save state
exit 0
```

Important paths:

```txt
data/markdown/
data/state.json
data/run-log.json
```

Run log fields:

```txt
run_at
support_base_url
locale
articles_seen
added
updated
skipped
files_uploaded
uploaded_document_names
estimated_chunks
gemini_file_search_store_name
```

Why `main.py` exits:

```txt
This is a scheduled job, not a web server.
Docker and GitHub Actions should finish after the sync.
```

How to verify after writing:

```bash
python3 -m compileall main.py
pytest tests/test_main.py -q
```

Real run verification:

```bash
python3 main.py
cat data/run-log.json
```

Common mistakes:

```txt
Do not turn main.py into a Flask/FastAPI server. The assignment asks for a job that runs once and exits.
Do not upload skipped files. Only added/updated files should be uploaded.
Do not save state only at the end if store creation happens earlier; save once after store creation so ask_gemini.py can resolve the store.
```

## 10. `ask_gemini.py`

Purpose:

- Quick sanity-check CLI for the assistant.

When to write this file:

```txt
Write after gemini_uploader.py. This file is not the daily job; it is a local test helper for asking questions against the uploaded Gemini File Search Store.
```

Dependencies:

```txt
External:
- python-dotenv

Internal:
- gemini_uploader.ask_with_file_search
- gemini_uploader.get_client
- gemini_uploader.resolve_store_name
```

Input and output:

```txt
Input:
- command-line question
- GEMINI_API_KEY or API_KEY
- GEMINI_FILE_SEARCH_STORE_NAME or data/state.json

Output:
- terminal answer text with Article URL citations when retrieved
```

Run:

```bash
python3 ask_gemini.py "How do I add a YouTube video?"
```

It:

1. Loads `.env`.
2. Resolves Gemini File Search Store.
3. Calls `ask_with_file_search`.
4. Prints the answer.

Use this output for the required screenshot if Google AI Studio does not expose your API-created File Search Store in the UI.

How to verify after writing:

```bash
python3 -m compileall ask_gemini.py
python3 ask_gemini.py "How do I add a YouTube video?"
```

Common mistake:

```txt
If data/state.json is deleted and GEMINI_FILE_SEARCH_STORE_NAME is not set, ask_gemini.py cannot know which Gemini store to query. Fix by running python3 main.py once or setting GEMINI_FILE_SEARCH_STORE_NAME in .env.
```

## 11. Local Bot Check

Use the CLI helper to ask the uploaded Gemini File Search Store:

```bash
python3 ask_gemini.py "How do I add a YouTube video?"
```

The script loads `.env`, resolves `GEMINI_FILE_SEARCH_STORE_NAME` from the environment or `data/state.json`, asks Gemini with the File Search tool, and prints the answer. Use this output or Google AI Studio for the required screenshot.

## 12. Dockerfile

Required behavior:

```dockerfile
CMD ["python", "main.py"]
```

When to write this file:

```txt
Write after main.py can run locally. Docker should package the same run-once job, not change behavior.
```

Input and output:

```txt
Input:
- repository source code
- requirements.txt
- runtime environment variables passed by docker run

Output:
- Docker image
- one sync run
- process exits after main.py finishes
```

Build:

```bash
docker build -t kb-harvest .
```

Run with `.env`:

```bash
docker run --env-file .env kb-harvest
```

Run in prompt-style form:

```bash
docker run -e API_KEY=REPLACE_ME kb-harvest
```

Why this passes:

```txt
The container runs the scraper/uploader once and exits 0.
```

How to verify after writing:

```bash
docker build -t kb-harvest .
docker run --env-file .env kb-harvest
```

Common mistakes:

```txt
Do not copy .env into the image.
Do not run a web server command.
Do not forget to pass GEMINI_API_KEY or API_KEY at runtime.
```

## 13. GitHub Actions Daily Job

File:

```txt
.github/workflows/daily-sync.yml
```

Triggers:

```txt
Manual workflow_dispatch
Daily cron: 0 2 * * *
```

When to write this file:

```txt
Write after local main.py and Docker behavior are working. GitHub Actions should run the same command as local: python main.py.
```

Inputs and secrets:

```txt
workflow_dispatch input:
- max_articles
- dry_run_scrape_only

repository secrets:
- GEMINI_API_KEY
- GEMINI_FILE_SEARCH_STORE_NAME
```

Main steps:

1. Check out repository.
2. Set up Python.
3. Install dependencies.
4. Restore cached `data/state.json`.
5. Validate `GEMINI_API_KEY`.
6. Run `python main.py`.
7. Add `run-log.json` to Actions summary.
8. Upload `run-log` artifact.
9. Upload `sync-state` artifact.
10. Upload `generated-markdown` artifact.

Why cache state:

```txt
GitHub runners are fresh every time.
Caching state lets the workflow know what was uploaded previously.
```

Artifact behavior:

```txt
data/markdown/*.md is uploaded as generated-markdown.
data/state.json is uploaded as sync-state.
data/run-log.json is uploaded as run-log.
These files are not committed to git.
```

How to verify after writing:

```txt
1. Push workflow to GitHub.
2. Open Actions -> Daily Knowledge Sync.
3. Run workflow manually.
4. Check the run summary for data/run-log.json.
5. Download generated-markdown, run-log, and sync-state artifacts.
```

Common mistakes:

```txt
Do not expect GitHub Actions to see your local .env.
Do not commit generated Markdown/state/log files.
Do not use Render cron here if the chosen cloud job is GitHub Actions.
```

## 14. CI Workflow

File:

```txt
.github/workflows/ci.yml
```

Checks:

```txt
compileall
secret scan
deliverable structure check
pytest
docker build
```

When to write this file:

```txt
Write after tests and safety scripts exist. CI proves the repository is safe to review before running real API jobs.
```

The secret scan catches:

```txt
.env committed by mistake
data/state.json committed by mistake
data/run-log.json committed by mistake
key-shaped strings in tracked files
```

How to verify after writing:

```bash
python3 -m compileall main.py scraper.py gemini_uploader.py markdown_cleaner.py state.py ask_gemini.py tests scripts
python3 scripts/check_no_secrets.py
python3 scripts/check_deliverables.py
pytest -q
docker build -t kb-harvest .
```

Common mistakes:

```txt
Do not require GEMINI_API_KEY for CI tests. CI should be able to run without paid/secret API calls.
Tests should mock external services.
```

## 15. Tests

When to write test files:

```txt
Write tests after each module or immediately after the core pipeline works. The goal is to verify our code behavior without real Zendesk/Gemini network calls.
```

`tests/test_markdown_cleaner.py`

- Verifies slug generation.
- Verifies article Markdown includes:

```txt
Article URL
title
heading
```

`tests/test_scraper.py`

- Verifies Zendesk pagination.
- Verifies HTTP errors are surfaced.
- Verifies added, updated, and skipped article detection.

`tests/test_state.py`

- Verifies state defaults, JSON writes, and hash stability.

`tests/test_gemini_uploader.py`

- Verifies chunk estimation, store resolution, upload configuration, document deletion, and prompt/tool wiring without calling the real Gemini API.

`tests/test_main.py`

- Verifies `main.py` uploads only changed files and writes run logs.

`tests/test_dry_run_scrape.py`

- Verifies dry-run parsing and that scrape-only mode does not require Gemini upload.

`tests/test_fetch_github_actions_data.py`

- Verifies GitHub artifact fetch helper behavior without calling the real GitHub API.

Run:

```bash
pytest -q
```

Common testing rules:

```txt
Do not call real Zendesk or Gemini in tests.
Use fake sessions/clients for API behavior.
Keep tests focused on behavior: Markdown shape, status detection, upload config, run-log fields.
```

## 16. Helper Scripts

These scripts are not the core pipeline, but they make the project safer and easier to review.

`scripts/dry_run_scrape.py`

Purpose:

```txt
Scrape Zendesk and write Markdown without uploading to Gemini.
Use this when you want to test article ingestion safely without spending Gemini upload calls.
```

Run:

```bash
python3 scripts/dry_run_scrape.py
```

Expected output:

```txt
data/markdown/*.md
data/run-log.json with "mode": "dry_run_scrape_only"
files_uploaded = 0
```

`scripts/check_no_secrets.py`

Purpose:

```txt
Prevent accidental commits of .env, local state, run logs, or key-shaped strings.
```

Run:

```bash
python3 scripts/check_no_secrets.py
```

Expected output:

```txt
Secret safety check passed.
```

`scripts/check_deliverables.py`

Purpose:

```txt
Print an advisory checklist for the take-home deliverables:
Markdown count, main.py, Dockerfile, GitHub Actions, README link, run-log, .env safety, tests, screenshot.
```

Run:

```bash
python3 scripts/check_deliverables.py
```

Note:

```txt
This script prints TODO items but does not fail CI. It is for review readiness.
```

`scripts/fetch_github_actions_data.py`

Purpose:

```txt
Download the latest successful GitHub Actions artifacts back to local data/.
Use this when the cloud run has newer generated Markdown or run-log files than your local machine.
```

Run:

```bash
python3 scripts/fetch_github_actions_data.py
```

If GitHub API requires authentication:

```bash
export GH_TOKEN=YOUR_GITHUB_TOKEN
python3 scripts/fetch_github_actions_data.py
```

Expected local output:

```txt
data/markdown/*.md
data/run-log.json
data/state.json
```

## 17. Code It Yourself Order

If you need to code the project again from beginning to end, write files in this order. Each block below is intentionally close to the final implementation, but the goal is to understand and retype it yourself.

### 17.1 `state.py`

Write this first because every other module needs state, JSON output, or hashing.

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_STATE = {
    "articles": {},
    "gemini": {
        "file_search_store_name": "",
    },
}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_STATE))

    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)

    state.setdefault("articles", {})
    state.setdefault("gemini", {})
    state["gemini"].setdefault("file_search_store_name", "")
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
```

Key idea:

```txt
State is the memory of the daily job. Without it, every run looks like the first run.
```

### 17.2 `markdown_cleaner.py`

This file turns Zendesk article HTML into clean Markdown.

```python
from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify as md


def slugify(value: str, fallback: str) -> str:
    value = unescape(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or fallback


def normalize_article_url(base_url: str, html_url: str | None, article_id: int) -> str:
    if html_url:
        return html_url
    return urljoin(base_url.rstrip("/") + "/", f"hc/en-us/articles/{article_id}")


def clean_markdown(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")

    for element in soup.select("script, style, nav, footer, header, aside, form"):
        element.decompose()

    for tag in soup.find_all(["a", "img"]):
        attr = "href" if tag.name == "a" else "src"
        if tag.get(attr):
            tag[attr] = urljoin(base_url.rstrip("/") + "/", tag[attr])

    markdown = md(
        str(soup),
        heading_style="ATX",
        bullets="-",
        code_language="",
        strip=["span"],
    )
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    return markdown.strip()


def article_to_markdown(article: dict, base_url: str) -> tuple[str, str]:
    article_id = int(article["id"])
    title = article.get("title") or f"Article {article_id}"
    slug = slugify(article.get("slug") or title, fallback=str(article_id))
    article_url = normalize_article_url(base_url, article.get("html_url"), article_id)
    updated_at = article.get("updated_at") or ""
    body = clean_markdown(article.get("body") or "", article_url)

    content = "\n".join(
        [
            "---",
            f'title: "{title.replace(chr(34), chr(39))}"',
            f'article_url: "{article_url}"',
            f'updated_at: "{updated_at}"',
            "---",
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
```

Key idea:

```txt
Gemini can cite "Article URL:" because every Markdown file includes that line.
```

### 17.3 `scraper.py`

This file gets article data from Zendesk and decides whether each article changed.

```python
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
    response = session.get(_article_endpoint(base_url, locale, article_id), timeout=30)
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
        articles.extend(payload.get("articles", []))
        next_page = payload.get("next_page")

    articles = articles[:max_articles]
    seen_ids = {int(article["id"]) for article in articles}
    for article_id in required_article_ids or []:
        if article_id not in seen_ids:
            articles.append(fetch_article(base_url, locale, article_id, session))
            seen_ids.add(article_id)
    return articles


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

        if previous_hash is None:
            status = "added"
        elif previous_hash != content_hash:
            status = "updated"
        else:
            status = "skipped"

        if status != "skipped" or not path.exists():
            path.write_text(markdown, encoding="utf-8")

        known_articles[state_key] = {
            "slug": slug,
            "title": article.get("title") or "",
            "url": article.get("html_url") or "",
            "updated_at": article.get("updated_at") or "",
            "hash": content_hash,
            "markdown_path": str(path),
            "gemini_document_name": previous_article_state.get("gemini_document_name", ""),
        }

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
```

Key idea:

```txt
Hash the cleaned Markdown, not raw HTML, because the final uploaded content is Markdown.
```

### 17.4 `gemini_uploader.py`

This is the Gemini integration. Write it after the scraper works locally.

```python
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types

from state import load_state

LOGGER = logging.getLogger(__name__)
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"
CHUNK_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 100

SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""


def estimate_chunks(
    paths: list[Path],
    chunk_tokens: int = CHUNK_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> int:
    stride = max(1, chunk_tokens - overlap_tokens)
    total = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        token_count = max(1, int(len(re.findall(r"\S+", text)) * 1.35))
        total += max(1, ((token_count - 1) // stride) + 1)
    return total


def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required. API_KEY is also accepted.")
    return genai.Client(api_key=api_key)


def resolve_store_name(state_path: Path) -> str:
    state = load_state(state_path)
    store_name = os.getenv("GEMINI_FILE_SEARCH_STORE_NAME") or state["gemini"].get(
        "file_search_store_name"
    )
    if not store_name:
        raise RuntimeError("Run python3 main.py first, or set GEMINI_FILE_SEARCH_STORE_NAME.")
    return store_name


def ensure_file_search_store(client: genai.Client, state: dict) -> str:
    existing = os.getenv("GEMINI_FILE_SEARCH_STORE_NAME") or state.get("gemini", {}).get(
        "file_search_store_name"
    )
    if existing:
        return existing

    store = client.file_search_stores.create(
        config={
            "display_name": os.getenv("GEMINI_STORE_DISPLAY_NAME", "OptiSigns Support Articles"),
            "embedding_model": os.getenv("GEMINI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        }
    )
    state.setdefault("gemini", {})["file_search_store_name"] = store.name
    LOGGER.info("Created Gemini File Search Store: %s", store.name)
    return store.name


def _wait_for_operation(client: genai.Client, operation, timeout_seconds: int = 300):
    deadline = time.time() + timeout_seconds
    while not getattr(operation, "done", False):
        if time.time() > deadline:
            raise TimeoutError("Gemini File Search upload did not finish in time.")
        time.sleep(5)
        operation = client.operations.get(operation)
    return operation


def remove_documents(client: genai.Client, document_names: list[str]) -> None:
    for document_name in document_names:
        if not document_name:
            continue
        try:
            client.file_search_stores.documents.delete(name=document_name)
        except Exception as exc:
            LOGGER.warning("Could not remove %s: %s", document_name, exc)


def upload_files(client: genai.Client, store_name: str, paths: list[Path]) -> list[str]:
    document_names: list[str] = []
    for path in paths:
        operation = client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store_name,
            file=path,
            config={
                "display_name": path.name,
                "mime_type": "text/markdown",
                "chunking_config": {
                    "white_space_config": {
                        "max_tokens_per_chunk": CHUNK_TOKENS,
                        "max_overlap_tokens": CHUNK_OVERLAP_TOKENS,
                    }
                },
            },
        )
        operation = _wait_for_operation(client, operation)
        response = getattr(operation, "response", None)
        document_names.append(getattr(response, "document_name", "") if response else "")
    return document_names


def ask_with_file_search(client: genai.Client, store_name: str, question: str) -> str:
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
        contents=question,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store_name],
                        top_k=6,
                    )
                )
            ],
        ),
    )
    return response.text or ""
```

Key idea:

```txt
The upload happens by API. This is the core requirement for the vector-store section.
```

### 17.5 `main.py`

This ties everything together.

```python
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from gemini_uploader import (
    ensure_file_search_store,
    estimate_chunks,
    get_client,
    remove_documents,
    upload_files,
)
from scraper import fetch_articles, write_markdown_articles
from state import load_state, save_state, write_json

DATA_DIR = Path("data")
MARKDOWN_DIR = DATA_DIR / "markdown"
STATE_PATH = DATA_DIR / "state.json"
RUN_LOG_PATH = DATA_DIR / "run-log.json"
DEFAULT_REQUIRED_ARTICLE_IDS = "360051014713"


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def parse_required_article_ids(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def main() -> int:
    load_dotenv()
    configure_logging()
    logger = logging.getLogger("main")

    base_url = os.getenv("SUPPORT_BASE_URL", "https://support.optisigns.com")
    locale = os.getenv("SUPPORT_LOCALE", "en-us")
    max_articles = int(os.getenv("MAX_ARTICLES", "35"))
    required_article_ids = parse_required_article_ids(
        os.getenv("SUPPORT_REQUIRED_ARTICLE_IDS", DEFAULT_REQUIRED_ARTICLE_IDS)
    )
    state = load_state(STATE_PATH)

    articles = fetch_articles(
        base_url=base_url,
        locale=locale,
        max_articles=max_articles,
        required_article_ids=required_article_ids,
    )
    scraped = write_markdown_articles(
        articles=articles,
        base_url=base_url,
        output_dir=MARKDOWN_DIR,
        previous_state=state,
    )

    changed = [article for article in scraped if article.status in {"added", "updated"}]
    upload_paths = [article.markdown_path for article in changed]

    client = get_client()
    store_name = ensure_file_search_store(client, state)
    save_state(STATE_PATH, state)

    uploaded_document_names: list[str] = []
    if upload_paths:
        stale_document_names = [
            state["articles"].get(str(article.id), {}).get("gemini_document_name", "")
            for article in changed
            if article.status == "updated"
        ]
        remove_documents(client, stale_document_names)
        uploaded_document_names = upload_files(client, store_name, upload_paths)
        for article, document_name in zip(changed, uploaded_document_names, strict=True):
            state["articles"][str(article.id)]["gemini_document_name"] = document_name
    else:
        logger.info("No article changes detected; upload skipped.")

    counts = {
        "added": sum(1 for article in scraped if article.status == "added"),
        "updated": sum(1 for article in scraped if article.status == "updated"),
        "skipped": sum(1 for article in scraped if article.status == "skipped"),
    }
    run_log = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "support_base_url": base_url,
        "locale": locale,
        "required_article_ids": required_article_ids,
        "articles_seen": len(scraped),
        **counts,
        "files_uploaded": len(uploaded_document_names),
        "uploaded_document_names": uploaded_document_names,
        "estimated_chunks": estimate_chunks(upload_paths) if upload_paths else 0,
        "gemini_file_search_store_name": store_name,
    }

    write_json(RUN_LOG_PATH, run_log)
    save_state(STATE_PATH, state)
    logger.info(
        "Run complete: added=%s updated=%s skipped=%s uploaded=%s estimated_chunks=%s",
        counts["added"],
        counts["updated"],
        counts["skipped"],
        len(uploaded_document_names),
        run_log["estimated_chunks"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 17.6 `ask_gemini.py`

```python
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from gemini_uploader import ask_with_file_search, get_client, resolve_store_name

STATE_PATH = Path("data") / "state.json"


def main() -> int:
    load_dotenv()
    question = " ".join(os.sys.argv[1:]) or "How do I add a YouTube video?"
    answer = ask_with_file_search(get_client(), resolve_store_name(STATE_PATH), question)
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 17.7 `Dockerfile`

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### 17.8 Minimal Test File

Start with this test, then add more if time permits.

```python
from markdown_cleaner import article_to_markdown, slugify


def test_slugify_keeps_readable_ascii_slug():
    assert slugify("How do I add a YouTube Video?", "fallback") == "how-do-i-add-a-youtube-video"


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
```

### 17.9 GitHub Actions Code

Create `.github/workflows/daily-sync.yml`:

```yaml
name: Daily Knowledge Sync

on:
  workflow_dispatch:
  schedule:
    - cron: "0 2 * * *"

permissions:
  contents: read
  actions: read

jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: python -m pip install -r requirements.txt
      - uses: actions/cache@v4
        with:
          path: data/state.json
          key: kb-harvest-state-${{ github.run_id }}
          restore-keys: |
            kb-harvest-state-
      - run: python main.py
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GEMINI_FILE_SEARCH_STORE_NAME: ${{ secrets.GEMINI_FILE_SEARCH_STORE_NAME }}
          MAX_ARTICLES: "35"
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: run-log
          path: data/run-log.json
          if-no-files-found: ignore
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: sync-state
          path: data/state.json
          if-no-files-found: ignore
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: generated-markdown
          path: data/markdown/*.md
          if-no-files-found: ignore
```

### 17.10 Final Build Commands

Run these in order:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env
python3 main.py
python3 ask_gemini.py "How do I add a YouTube video?"
pytest -q
docker build -t kb-harvest .
docker run --env-file .env kb-harvest
```

## 18. Deep Code Walkthrough

Use this section when you need to explain the code in an interview. The goal is not to memorize every line; it is to understand why each module exists and what data it receives/returns.

### 18.1 Data Shape From Zendesk

The Zendesk API returns article dictionaries. The fields this project cares about are:

```python
{
    "id": 360051014713,
    "title": "How to use YouTube with OptiSigns",
    "slug": "How-to-use-YouTube-with-OptiSigns",
    "html_url": "https://support.optisigns.com/hc/en-us/articles/360051014713-...",
    "updated_at": "2026-06-18T05:00:56Z",
    "body": "<p>Putting YouTube video on your digital signs...</p>",
}
```

How it moves through the project:

```txt
Zendesk dict
  -> article_to_markdown(article, base_url)
  -> (slug, markdown_text)
  -> data/markdown/<slug>.md
  -> hash(markdown_text)
  -> status added/updated/skipped
  -> Gemini upload if added/updated
```

Why this shape is good:

```txt
The API gives article body separately from website navigation.
That means cleaning is easier than scraping a rendered support page.
```

### 18.2 `state.py` Explained

`DEFAULT_STATE`

```python
DEFAULT_STATE = {
    "articles": {},
    "gemini": {
        "file_search_store_name": "",
    },
}
```

This is the minimum state file. `articles` stores one entry per Zendesk article. `gemini.file_search_store_name` stores the File Search Store created by Gemini.

Example after a run:

```json
{
  "articles": {
    "360051014713": {
      "slug": "how-to-use-youtube-with-optisigns",
      "title": "How to use YouTube with OptiSigns",
      "url": "https://support.optisigns.com/hc/en-us/articles/360051014713-How-to-use-YouTube-with-OptiSigns",
      "updated_at": "2026-06-18T05:00:56Z",
      "hash": "abc123...",
      "markdown_path": "data/markdown/how-to-use-youtube-with-optisigns.md",
      "gemini_document_name": "fileSearchStores/.../documents/..."
    }
  },
  "gemini": {
    "file_search_store_name": "fileSearchStores/..."
  }
}
```

`load_state(path)`

```txt
Input:  Path("data/state.json")
Output: dict with articles and gemini keys
```

Important behavior:

```txt
If state.json is missing, return a fresh default state.
If an old state file misses a key, add the key.
Do not return DEFAULT_STATE directly, because mutating it would affect future calls.
```

That is why the code uses:

```python
return json.loads(json.dumps(DEFAULT_STATE))
```

This creates a deep copy using JSON serialization.

`sha256_text(value)`

```txt
Input:  Markdown text
Output: SHA-256 hex string
```

Why hash Markdown:

```txt
The uploaded content is Markdown, so the hash should represent exactly what Gemini receives.
If raw HTML changes but cleaned Markdown is the same, re-upload is unnecessary.
```

### 18.3 `markdown_cleaner.py` Explained

`slugify(value, fallback)`

Purpose:

```txt
Turn a title or Zendesk slug into a safe filename.
```

Examples:

```txt
"How do I add a YouTube Video?" -> "how-do-i-add-a-youtube-video"
"!!!" -> fallback value, usually article ID
```

Main regex:

```python
re.sub(r"[^a-z0-9]+", "-", value)
```

Meaning:

```txt
Any run of non-lowercase-letter/non-number characters becomes "-".
```

`clean_markdown(html, base_url)`

This function has three phases:

1. Parse HTML:

```python
soup = BeautifulSoup(html or "", "html.parser")
```

2. Remove page chrome:

```python
for element in soup.select("script, style, nav, footer, header, aside, form"):
    element.decompose()
```

This protects the knowledge base from irrelevant text like navigation, forms, scripts, and layout.

3. Normalize links/images:

```python
for tag in soup.find_all(["a", "img"]):
    attr = "href" if tag.name == "a" else "src"
    if tag.get(attr):
        tag[attr] = urljoin(base_url.rstrip("/") + "/", tag[attr])
```

Why:

```txt
Support articles often contain relative URLs like /hc/en-us/articles/...
Gemini citations and Markdown should preserve full usable links.
```

4. Convert to Markdown:

```python
markdown = md(
    str(soup),
    heading_style="ATX",
    bullets="-",
    code_language="",
    strip=["span"],
)
```

Why these options:

```txt
ATX headings become #, ##, ###.
Bullets are consistent with "-".
span tags are usually styling wrappers, not meaningful content.
```

`article_to_markdown(article, base_url)`

Output format:

```markdown
---
title: "How to use YouTube with OptiSigns"
article_url: "https://support.optisigns.com/..."
updated_at: "2026-06-18T05:00:56Z"
---

Article URL: https://support.optisigns.com/...

# How to use YouTube with OptiSigns

Clean article body...
```

Why both frontmatter and `Article URL:` line:

```txt
Frontmatter is useful metadata for humans/scripts.
The visible Article URL line is easy for Gemini to retrieve and cite.
```

### 18.4 `scraper.py` Explained

`ScrapedArticle`

This dataclass is the structured result after converting one Zendesk article:

```python
ScrapedArticle(
    id=360051014713,
    slug="how-to-use-youtube-with-optisigns",
    title="How to use YouTube with OptiSigns",
    url="https://support.optisigns.com/...",
    updated_at="2026-06-18T05:00:56Z",
    content_hash="abc123...",
    markdown_path=Path("data/markdown/how-to-use-youtube-with-optisigns.md"),
    status="added",
)
```

Why a dataclass:

```txt
It makes the output of write_markdown_articles explicit.
main.py can count statuses and choose upload paths without guessing dictionary keys.
```

`fetch_articles(...)`

This function does two jobs:

1. Fetch the newest `max_articles` from Zendesk pagination.
2. Append important older articles from `required_article_ids`.

Flow:

```txt
next_page = articles endpoint
while next_page and len(articles) < max_articles:
    GET next_page
    append payload["articles"]
    next_page = payload["next_page"]

trim to max_articles
for each required ID:
    if not already seen:
        fetch single article endpoint
        append it
```

Why `required_article_ids` matters:

```txt
The assignment sample asks about YouTube.
The correct YouTube article is older, so it may not appear in the first 35 newest articles.
The required ID makes the demo answer reliable.
```

`write_markdown_articles(...)`

Inputs:

```txt
articles:       Zendesk article dictionaries
base_url:       https://support.optisigns.com
output_dir:     data/markdown
previous_state: loaded state dictionary
```

Status decision:

```python
if previous_hash is None:
    status = "added"
elif previous_hash != content_hash:
    status = "updated"
else:
    status = "skipped"
```

Why still write if skipped file is missing:

```python
if status != "skipped" or not path.exists():
    path.write_text(markdown, encoding="utf-8")
```

Explanation:

```txt
In GitHub Actions, Markdown files come from the current run, not from git.
If state says skipped but the local file is absent, write it so artifacts are complete.
```

### 18.5 `gemini_uploader.py` Explained

`SYSTEM_PROMPT`

This must match the assignment exactly. It is the behavior contract:

```txt
Helpful, factual, concise.
Only uploaded docs.
Max 5 bullets.
Cite up to 3 Article URL lines.
```

`estimate_chunks(paths)`

This is not real tokenization. It is a reporting estimate:

```python
token_count = max(1, int(len(re.findall(r"\S+", text)) * 1.35))
```

Why multiply by `1.35`:

```txt
Words are not the same as model tokens.
The multiplier gives a rough approximation for run-log reporting.
Gemini still performs the real chunking/indexing.
```

`get_client()`

Reads either:

```txt
GEMINI_API_KEY
API_KEY
```

Why support `API_KEY`:

```txt
The take-home Docker requirement says docker run -e API_KEY=... should work.
```

`ensure_file_search_store(client, state)`

Decision tree:

```txt
If GEMINI_FILE_SEARCH_STORE_NAME env var exists:
    use it
Else if state has file_search_store_name:
    use it
Else:
    create a new Gemini File Search Store
    save store.name into state
```

Why:

```txt
First run can bootstrap itself.
Future runs reuse the same store.
GitHub Actions can also force a known store through secrets.
```

`remove_documents(client, document_names)`

Why delete first on updates:

```txt
If an article changed and you upload the new copy without deleting the old copy,
Gemini may retrieve stale information from both versions.
```

The function catches exceptions because deletion should not destroy the whole run if a stale document was already removed:

```python
except Exception as exc:
    LOGGER.warning("Could not remove %s: %s", document_name, exc)
```

`upload_files(client, store_name, paths)`

Important upload config:

```python
config={
    "display_name": path.name,
    "mime_type": "text/markdown",
    "chunking_config": {
        "white_space_config": {
            "max_tokens_per_chunk": 512,
            "max_overlap_tokens": 100,
        }
    },
}
```

Why chunk overlap:

```txt
If an answer spans the boundary between two chunks, overlap helps retrieval include enough context.
```

`_wait_for_operation(...)`

Gemini uploads are async operations. The script polls until:

```txt
operation.done == True
```

Then it reads:

```python
operation.response.document_name
```

That document name is saved into state so updated articles can delete the old Gemini document next time.

`ask_with_file_search(...)`

This is only for testing the assistant:

```python
tools=[
    types.Tool(
        file_search=types.FileSearch(
            file_search_store_names=[store_name],
            top_k=6,
        )
    )
]
```

Meaning:

```txt
Gemini answers the question with retrieval from the uploaded File Search Store.
top_k=6 asks Gemini to retrieve up to six relevant chunks.
```

### 18.6 `main.py` Explained

`main.py` is the orchestrator. It should be readable as a story:

```txt
Load config.
Load state.
Scrape articles.
Write Markdown.
Find changed Markdown files.
Open Gemini client.
Create or reuse store.
Delete stale documents for updated files.
Upload changed files.
Write log.
Save state.
Exit.
```

`parse_required_article_ids(value)`

Input:

```txt
"360051014713,48626115821459"
```

Output:

```python
[360051014713, 48626115821459]
```

Why it exists:

```txt
Environment variables are strings.
The scraper expects integer article IDs.
```

`changed`

```python
changed = [article for article in scraped if article.status in {"added", "updated"}]
```

Only these should upload. Skipped articles already exist in Gemini.

`stale_document_names`

```python
stale_document_names = [
    state["articles"].get(str(article.id), {}).get("gemini_document_name", "")
    for article in changed
    if article.status == "updated"
]
```

Only updated articles need stale document deletion. New articles have no previous Gemini document.

`zip(changed, uploaded_document_names, strict=True)`

Why `strict=True`:

```txt
If Gemini returns fewer/more document names than uploaded files, fail loudly.
Silent mismatch would corrupt state.
```

`run_log`

This is the proof artifact for the daily job:

```json
{
  "articles_seen": 36,
  "added": 1,
  "updated": 0,
  "skipped": 35,
  "files_uploaded": 1,
  "estimated_chunks": 2
}
```

What to show reviewers:

```txt
The job logs exactly how many articles were added, updated, skipped, uploaded, and chunked.
```

### 18.7 `ask_gemini.py` Explained

This script is intentionally small:

```txt
Load local .env.
Read the user question from command-line args.
Resolve store name.
Ask Gemini with File Search.
Print the answer.
```

Example:

```bash
python3 ask_gemini.py "How do I add a YouTube video?"
```

Expected citation:

```txt
Article URL: https://support.optisigns.com/hc/en-us/articles/360051014713-How-to-use-YouTube-with-OptiSigns
```

If the answer cites the YouTube Dashboard article instead:

```txt
Run python3 main.py again.
Confirm SUPPORT_REQUIRED_ARTICLE_IDS includes 360051014713.
Confirm data/markdown/how-to-use-youtube-with-optisigns.md exists.
```

### 18.8 GitHub Actions Explained

Why `daily-sync.yml` uses cache:

```txt
GitHub runners start empty.
data/state.json is ignored by git.
The cache restores previous hashes and Gemini document names.
```

Why upload Markdown artifacts:

```txt
Generated Markdown is ignored by git to keep the repo clean.
Artifacts let reviewers download exactly what the job generated.
```

Cloud data model:

```txt
Gemini File Search Store:
  Canonical knowledge base used by ask_gemini.py.

GitHub Actions generated-markdown artifact:
  Cloud copy of Markdown files from the latest workflow run.

GitHub Actions run-log artifact:
  Cloud copy of counts and upload summary.

GitHub Actions sync-state artifact/cache:
  Cloud copy of hashes, Gemini document names, and store metadata.

Local data/:
  Temporary rebuild/debug output only. It is ignored by git.
```

Important:

```txt
ask_gemini.py does not answer from local data/markdown files.
It answers from the Gemini cloud File Search Store.
If local data/ is deleted but GEMINI_FILE_SEARCH_STORE_NAME is set, asking can still work.
```

Why there is a dry-run option:

```txt
It lets you prove scraping and Markdown generation without spending Gemini quota or needing secrets.
It still includes required seed article IDs, so generated Markdown matches the sample-question coverage.
```

### 18.9 Tests Explained

Test philosophy:

```txt
Tests should not call Zendesk or Gemini.
Network and Gemini calls are mocked/faked.
The tests verify our code behavior, not third-party availability.
```

Most important test categories:

```txt
Markdown cleaner:
  - Removes nav/scripts
  - Preserves headings/code blocks
  - Normalizes links

Scraper:
  - Follows pagination
  - Adds required YouTube article
  - Detects added/updated/skipped

Gemini uploader:
  - Builds chunking config
  - Resolves store name
  - Handles upload operations
  - Attaches File Search tool

Main:
  - Uploads only changed files
  - Writes run-log fields
```

### 18.10 Common Mistakes And Fixes

Wrong answer for YouTube sample:

```txt
Cause: correct YouTube article missing from Gemini store.
Fix: keep SUPPORT_REQUIRED_ARTICLE_IDS=360051014713 and rerun main.py.
```

`GEMINI_FILE_SEARCH_STORE_NAME` empty:

```txt
First run can create it automatically.
After first run, check data/state.json or data/run-log.json.
For GitHub Actions, add it as a repository secret once known.
```

All files upload every run:

```txt
Cause: state is missing or not restored.
Fix: locally keep data/state.json; in GitHub Actions, use cache restore for data/state.json.
```

Docker exits with missing key:

```txt
Cause: no GEMINI_API_KEY/API_KEY passed.
Fix: docker run --env-file .env kb-harvest
or:  docker run -e API_KEY=... kb-harvest
```

Secret scanner fails:

```txt
Cause: .env, run-log, state, or key-like text got tracked.
Fix: remove tracked secret files with git rm --cached and rotate exposed keys if needed.
```

### 18.11 Exact Rebuild Verification Order

After writing each major module, verify in small steps:

```bash
# 1. Confirm syntax early
python3 -m compileall state.py markdown_cleaner.py scraper.py

# 2. Confirm Markdown conversion logic
pytest tests/test_markdown_cleaner.py -q

# 3. Confirm scraper logic without network
pytest tests/test_scraper.py -q

# 4. Confirm Gemini helper logic without API calls
pytest tests/test_gemini_uploader.py -q

# 5. Confirm full offline test suite
pytest -q

# 6. Confirm no committed secrets
python3 scripts/check_no_secrets.py

# 7. Run real sync only when .env is ready
python3 main.py

# 8. Ask sample question
python3 ask_gemini.py "How do I add a YouTube video?"

# 9. Build container
docker build -t kb-harvest .

# 10. Run container once
docker run --env-file .env kb-harvest
```

## 19. Current Code Walkthrough After Refactor

This section matches the current code exactly. Use this part when live-coding or explaining the final repository.

### 19.1 End-To-End Runtime Flow

When I run:

```bash
python3 main.py
```

the project executes this flow:

```txt
1. Load .env
2. Read runtime config from environment variables
3. Load data/state.json if it exists
4. Fetch articles from Zendesk Help Center API
5. Force-include required article IDs, especially the YouTube article
6. Convert each article body from HTML to clean Markdown
7. Hash each Markdown file with SHA-256
8. Compare new hash with previous state hash
9. Mark each article as added, updated, or skipped
10. Create or reuse a Gemini File Search Store
11. Upload only added/updated Markdown files
12. Delete stale Gemini documents for updated articles
13. Save new document names in state
14. Write data/run-log.json
15. Exit 0
```

The local asking flow is separate:

```bash
python3 ask_gemini.py "How do I add a YouTube video?"
```

That flow is:

```txt
1. Load .env
2. Resolve GEMINI_FILE_SEARCH_STORE_NAME from env or data/state.json
3. Create Gemini client
4. Send user question to Gemini
5. Attach File Search tool with the store name
6. Gemini retrieves relevant uploaded Markdown chunks
7. Gemini answers using the system prompt and cites Article URL lines
```

GitHub Actions daily flow:

```txt
1. Schedule triggers daily-sync.yml at 02:00 UTC
2. Checkout repo
3. Install Python dependencies
4. Restore cached data/state.json
5. Run python main.py with GitHub secrets
6. Upload artifacts:
   - generated-markdown
   - run-log
   - sync-state
7. Next run restores previous state and uploads only deltas
```

### 19.2 Library Explanation

`requests`

Purpose:

```txt
Used to call Zendesk Help Center API endpoints.
```

Why I chose it:

```txt
The task needs simple HTTP GET requests, pagination, timeout handling, and raise_for_status().
requests is straightforward and easy to explain.
```

Where used:

```txt
scraper.py
```

Important call:

```python
response = session.get(next_page, timeout=30)
response.raise_for_status()
payload = response.json()
```

Explanation:

```txt
session.get() sends the HTTP request.
timeout=30 prevents hanging forever.
raise_for_status() fails fast on HTTP errors.
response.json() converts Zendesk JSON into Python dictionaries.
```

`beautifulsoup4`

Purpose:

```txt
Parses Zendesk article HTML before converting to Markdown.
```

Why I chose it:

```txt
Zendesk body content is HTML. BeautifulSoup lets me remove unwanted HTML elements safely instead of using fragile regex.
```

Where used:

```txt
markdown_cleaner.py
```

Important call:

```python
soup = BeautifulSoup(html or "", "html.parser")
```

`markdownify`

Purpose:

```txt
Converts cleaned HTML into Markdown.
```

Why I chose it:

```txt
It preserves headings, links, lists, code blocks, and tables better than hand-written string replacement.
```

Important call:

```python
markdown = md(str(soup), heading_style="ATX", bullets="-", code_language="", strip=["span"])
```

Explanation:

```txt
heading_style="ATX" creates Markdown headings like # and ##.
bullets="-" normalizes bullet lists.
strip=["span"] removes unnecessary inline span tags.
```

`google-genai`

Purpose:

```txt
Talks to Gemini API.
Creates/reuses File Search Store.
Uploads Markdown files.
Asks Gemini with File Search retrieval.
```

Where used:

```txt
gemini_uploader.py
```

Important objects:

```txt
genai.Client
types.GenerateContentConfig
types.Tool
types.FileSearch
```

`python-dotenv`

Purpose:

```txt
Loads local .env during development.
```

Why needed:

```txt
The API key should not be committed. Locally, .env stores it. In GitHub Actions, repository secrets provide it.
```

Where used:

```txt
main.py
ask_gemini.py
scripts/dry_run_scrape.py
```

`pytest`

Purpose:

```txt
Bonus tests and safety checks.
```

What the tests cover:

```txt
Markdown cleaning
Zendesk scraper behavior
Required YouTube article inclusion
State loading/saving
Gemini upload configuration
main.py orchestration
GitHub Actions artifact fetcher
```

Standard library modules:

```txt
os        -> read environment variables
pathlib   -> clean filesystem paths
json      -> read/write state and run logs
hashlib   -> SHA-256 hashes
logging   -> structured logs
datetime  -> UTC run timestamp
dataclass -> simple config/data objects
zipfile   -> extract GitHub Actions artifacts
urllib    -> call GitHub API without adding another dependency
```

### 19.3 `main.py` Function-By-Function

`SyncConfig`

Code role:

```txt
Holds runtime settings for one sync run.
```

Fields:

```txt
support_base_url       -> https://support.optisigns.com
support_locale         -> en-us
max_articles           -> how many newest Zendesk articles to pull
required_article_ids   -> extra important articles always included
```

Why use a dataclass:

```txt
It groups config into one readable object. This makes run_sync(config) easy to test and explain.
```

`SyncConfig.from_env()`

Purpose:

```txt
Reads environment variables and builds the config object.
```

Live explanation:

```txt
I keep env parsing in one place. The rest of the code receives a normal Python object and does not need to know where values came from.
```

`configure_logging()`

Purpose:

```txt
Sets log level and log format.
```

Why:

```txt
In local runs and GitHub Actions logs, I want readable lines showing what the job did.
```

`parse_required_article_ids(value)`

Purpose:

```txt
Converts a comma-separated string into a list of integers.
```

Example:

```txt
"360051014713,48626115821459" -> [360051014713, 48626115821459]
```

Why important:

```txt
The newest 35 articles may not include the exact YouTube article required by the assessment, so I force-include it by ID.
```

`upload_changed_articles(client, store_name, changed_articles, state)`

Purpose:

```txt
Uploads only added/updated articles to Gemini.
```

Detailed steps:

```txt
1. If no changed articles, return empty list.
2. For updated articles, collect previous Gemini document names.
3. Delete stale Gemini documents.
4. Upload changed Markdown files.
5. Save new Gemini document names back into state.
6. Return uploaded document names.
```

Why delete stale documents:

```txt
If an article changes, the old content should not remain searchable. Deleting the old document avoids conflicting answers.
```

`count_article_statuses(scraped_articles)`

Purpose:

```txt
Counts how many articles were added, updated, and skipped.
```

Why:

```txt
The take-home explicitly asks the daily job to log added, updated, and skipped counts.
```

`changed_markdown_paths(scraped_articles)`

Purpose:

```txt
Returns paths for articles with status added or updated.
```

Why:

```txt
Only changed files need estimated chunk counts and upload.
```

`build_run_log(config, scraped_articles, uploaded_document_names, store_name)`

Purpose:

```txt
Creates the JSON object saved to data/run-log.json.
```

Fields explained:

```txt
run_at                         -> UTC timestamp
support_base_url               -> source site
locale                         -> Zendesk locale
required_article_ids           -> forced included articles
articles_seen                  -> total articles processed
added / updated / skipped      -> delta results
files_uploaded                 -> how many files uploaded to Gemini
uploaded_document_names        -> Gemini document IDs
estimated_chunks               -> approximate chunk count
gemini_file_search_store_name  -> Gemini store used by ask_gemini.py
```

`run_sync(config)`

Purpose:

```txt
The main orchestration function.
```

Detailed flow:

```txt
1. Load state.
2. Fetch articles from Zendesk.
3. Write Markdown and update article state.
4. Filter changed articles.
5. Create/reuse Gemini File Search Store.
6. Save state once after store creation.
7. Upload changed articles.
8. Build run log.
9. Write run log.
10. Save final state.
11. Return run log.
```

Why return run log:

```txt
It makes the function easier to test and easier to reuse in the future.
```

`main()`

Purpose:

```txt
Small CLI entry point.
```

Detailed flow:

```txt
1. load_dotenv()
2. configure_logging()
3. run_sync(SyncConfig.from_env())
4. return 0
```

Why keep `main()` small:

```txt
For live coding, the entry point should be easy to read. The real work is separated into named functions.
```

### 19.4 `scraper.py` Function-By-Function

`ScrapedArticle`

Purpose:

```txt
Represents the normalized result for one article after Markdown conversion and delta detection.
```

Fields:

```txt
id             -> Zendesk article ID
slug           -> filename-safe slug
title          -> article title
url            -> article URL
updated_at     -> Zendesk updated timestamp
content_hash   -> SHA-256 hash of Markdown content
markdown_path  -> local Markdown path
status         -> added, updated, or skipped
```

`STATUS_ADDED`, `STATUS_UPDATED`, `STATUS_SKIPPED`

Purpose:

```txt
Avoid hard-coded magic strings across the codebase.
```

`_articles_endpoint(base_url, locale)`

Purpose:

```txt
Builds the Zendesk list endpoint.
```

Example:

```txt
https://support.optisigns.com/api/v2/help_center/en-us/articles.json
```

`_article_endpoint(base_url, locale, article_id)`

Purpose:

```txt
Builds the endpoint for one required article.
```

Example:

```txt
https://support.optisigns.com/api/v2/help_center/en-us/articles/360051014713.json
```

`fetch_article(...)`

Purpose:

```txt
Fetches one specific article by ID.
```

Why:

```txt
The required YouTube sample article may be older than the newest MAX_ARTICLES results.
```

`fetch_articles(...)`

Purpose:

```txt
Fetches paginated newest Zendesk articles and appends required articles if missing.
```

Detailed flow:

```txt
1. Start at articles.json endpoint.
2. While next_page exists and count is below max_articles:
   - GET page
   - parse JSON
   - extend articles list
   - follow next_page
3. Trim to max_articles.
4. Build set of seen IDs.
5. Fetch required IDs if not already seen.
6. Return article dictionaries.
```

`detect_status(previous_hash, current_hash)`

Purpose:

```txt
Decides whether an article is added, updated, or skipped.
```

Logic:

```txt
No previous hash       -> added
Different hash         -> updated
Same hash              -> skipped
```

`article_state_record(...)`

Purpose:

```txt
Builds the state dictionary for one article.
```

Why separate it:

```txt
It keeps write_markdown_articles readable and makes state shape easy to explain.
```

`write_markdown_articles(...)`

Purpose:

```txt
Converts fetched articles to Markdown, writes files, updates state, returns ScrapedArticle objects.
```

Detailed flow:

```txt
1. Ensure output directory exists.
2. For each article:
   - get article ID
   - read previous article state
   - convert HTML body to Markdown
   - calculate SHA-256 hash
   - compare hash to previous state
   - write file if added/updated or missing locally
   - update state
   - append ScrapedArticle result
3. Return all ScrapedArticle results.
```

### 19.5 `markdown_cleaner.py` Function-By-Function

`slugify(value, fallback)`

Purpose:

```txt
Converts article titles/slugs into safe filenames.
```

Example:

```txt
"How to Use YouTube with OptiSigns!" -> "how-to-use-youtube-with-optisigns"
```

`normalize_article_url(base_url, html_url, article_id)`

Purpose:

```txt
Ensures every Markdown file has a stable article URL.
```

Logic:

```txt
If Zendesk gives html_url, use it.
Otherwise build a fallback support URL from the article ID.
```

`remove_page_noise(soup)`

Purpose:

```txt
Removes tags that should not become Markdown content.
```

Removed tags:

```txt
script, style, nav, footer, header, aside, form
```

`normalize_links(soup, base_url)`

Purpose:

```txt
Converts relative links and image paths to absolute URLs.
```

Why:

```txt
The uploaded Markdown should still be useful even outside the original Zendesk page.
```

`html_to_markdown(soup)`

Purpose:

```txt
Converts cleaned HTML to Markdown and normalizes whitespace.
```

`clean_markdown(html, base_url)`

Purpose:

```txt
The main cleaning pipeline.
```

Detailed flow:

```txt
1. Parse HTML with BeautifulSoup.
2. Remove noisy tags.
3. Normalize links.
4. Convert to Markdown.
5. Return clean Markdown text.
```

`article_frontmatter(title, article_url, updated_at)`

Purpose:

```txt
Creates metadata at the top of every Markdown file.
```

Output:

```txt
---
title: "..."
article_url: "..."
updated_at: "..."
---
```

`article_to_markdown(article, base_url)`

Purpose:

```txt
Converts one Zendesk article dictionary into a filename slug and full Markdown content.
```

Detailed output structure:

```txt
YAML frontmatter
Article URL: ...
# Article title
Cleaned article body
```

Why include `Article URL:`:

```txt
The system prompt requires cited Article URL lines. Putting a clear Article URL line inside each uploaded Markdown file makes citation easier.
```

### 19.6 `gemini_uploader.py` Function-By-Function

`SYSTEM_PROMPT`

Purpose:

```txt
Defines the assistant behavior exactly as required by the take-home.
```

Important constraints:

```txt
Helpful, factual, concise.
Only answer using uploaded docs.
Max 5 bullet points.
Cite up to 3 Article URL lines.
```

`estimate_chunks(paths, chunk_tokens=512, overlap_tokens=100)`

Purpose:

```txt
Estimates how many chunks will be embedded/uploaded.
```

Why estimate:

```txt
Gemini performs the real chunking. The run log still needs an understandable chunk count, so I estimate by word count.
```

`get_client()`

Purpose:

```txt
Creates Gemini API client from GEMINI_API_KEY or API_KEY.
```

Security:

```txt
The key is read from environment variables, never hard-coded.
```

`resolve_store_name(state_path)`

Purpose:

```txt
Finds the File Search Store name for ask_gemini.py.
```

Lookup order:

```txt
1. GEMINI_FILE_SEARCH_STORE_NAME
2. data/state.json -> gemini.file_search_store_name
```

`ensure_file_search_store(client, state)`

Purpose:

```txt
Reuses an existing Gemini File Search Store or creates one.
```

Why:

```txt
First run can create the store automatically. Later runs should reuse the same store for incremental updates.
```

`_wait_for_operation(client, operation, timeout_seconds=300)`

Purpose:

```txt
Gemini upload is asynchronous. This polls until the upload operation is done.
```

`remove_documents(client, document_names)`

Purpose:

```txt
Deletes old Gemini documents for updated articles.
```

Why catch exceptions:

```txt
If a stale document was already removed, the sync should warn but continue.
```

`upload_files(client, store_name, paths)`

Purpose:

```txt
Uploads Markdown files to Gemini File Search Store.
```

Important config:

```txt
mime_type: text/markdown
max_tokens_per_chunk: 512
max_overlap_tokens: 100
```

`ask_with_file_search(client, store_name, question)`

Purpose:

```txt
Asks Gemini with File Search enabled.
```

Detailed flow:

```txt
1. Pick model from GEMINI_MODEL or default gemini-2.5-flash.
2. Send the question.
3. Attach system prompt.
4. Attach File Search tool pointing to the store.
5. Return Gemini text answer.
```

### 19.7 `state.py` Function-By-Function

`DEFAULT_STATE`

Purpose:

```txt
Defines the state shape when data/state.json does not exist.
```

Shape:

```json
{
  "articles": {},
  "gemini": {
    "file_search_store_name": ""
  }
}
```

`load_state(path)`

Purpose:

```txt
Reads JSON state from disk or returns DEFAULT_STATE.
```

Why it normalizes keys:

```txt
Older or partial state files still work because missing articles/gemini keys are added.
```

`save_state(path, state)`

Purpose:

```txt
Writes state as readable indented JSON.
```

`sha256_text(value)`

Purpose:

```txt
Hashes Markdown content for delta detection.
```

Why SHA-256:

```txt
It is deterministic, stable, and simple. If the Markdown changes, the hash changes.
```

`write_json(path, payload)`

Purpose:

```txt
Writes run logs and other JSON artifacts consistently.
```

### 19.8 `ask_gemini.py` Function-By-Function

`STATE_PATH`

Purpose:

```txt
Points to data/state.json.
```

`main()`

Purpose:

```txt
Tiny CLI wrapper for local sanity checks.
```

Detailed flow:

```txt
1. Load .env.
2. Read question from command-line args.
3. Resolve File Search Store name.
4. Create Gemini client.
5. Ask Gemini with File Search.
6. Print answer.
```

Failure case:

```txt
If no store exists, it prints a friendly message:
Run python3 main.py first, or set GEMINI_FILE_SEARCH_STORE_NAME.
```

### 19.9 `scripts/fetch_github_actions_data.py` Function-By-Function

Purpose of the script:

```txt
Downloads the latest GitHub Actions artifacts into local data/.
```

Why useful:

```txt
GitHub Actions may run in the cloud and generate newer Markdown/state/log files than local. This script lets local code mirror the latest cloud-generated artifacts.
```

`infer_repo(remote_url=None)`

Purpose:

```txt
Infers owner/repo from git origin URL.
```

Supports:

```txt
git@github.com:owner/repo.git
https://github.com/owner/repo.git
```

`github_request(url, token=None)`

Purpose:

```txt
Makes GitHub REST API requests.
```

Why use standard library:

```txt
It avoids adding another dependency just for artifact download.
```

`resolve_github_token()`

Purpose:

```txt
Finds a token for private artifact download.
```

Lookup order:

```txt
1. GITHUB_TOKEN
2. GH_TOKEN
3. gh auth token if GitHub CLI is installed
```

`successful_runs(repo, workflow, branch, token)`

Purpose:

```txt
Lists recent successful workflow runs.
```

`list_run_artifacts(repo, run_id, token)`

Purpose:

```txt
Lists non-expired artifacts for a workflow run.
```

`download_artifact(repo, artifact_id, token, destination)`

Purpose:

```txt
Downloads one artifact zip file.
```

`_extract_single_file(zip_path, output_path)`

Purpose:

```txt
Extracts run-log.json or state.json from an artifact zip.
```

`_extract_markdown(zip_path, output_dir)`

Purpose:

```txt
Extracts all .md files into data/markdown.
```

`build_minimal_state(output_dir)`

Purpose:

```txt
If sync-state artifact is missing, rebuild a minimal data/state.json from run-log and Markdown frontmatter.
```

Why:

```txt
ask_gemini.py mainly needs the Gemini File Search Store name. The minimal state is enough for local asking.
```

`find_latest_run_with_required_artifacts(...)`

Purpose:

```txt
Finds the newest successful workflow run that has generated-markdown and run-log artifacts.
```

Why not require sync-state:

```txt
Some dry runs or older runs may not include sync-state. The script can rebuild minimal state locally if needed.
```

`extract_artifact(artifact_name, zip_path, output_dir)`

Purpose:

```txt
Routes each artifact to the right extraction behavior.
```

`fetch_artifacts(...)`

Purpose:

```txt
High-level orchestration for artifact download.
```

Detailed flow:

```txt
1. Find latest valid workflow run.
2. Create local data directory.
3. Download each artifact zip.
4. Extract Markdown, run-log, and state.
5. Rebuild minimal state if sync-state is missing.
6. Return a JSON summary.
```

### 19.10 How To Present The Code In 10 Minutes

Use this order:

```txt
1. README.md
   Show the flow diagram and checklist.

2. main.py
   Explain that this is the orchestrator and run-once job.

3. scraper.py
   Explain Zendesk API, pagination, required article ID, and delta status.

4. markdown_cleaner.py
   Explain HTML cleanup and Markdown conversion.

5. gemini_uploader.py
   Explain File Search Store creation, upload config, chunking, and ask flow.

6. .github/workflows/daily-sync.yml
   Explain daily cloud automation and artifacts.

7. tests/
   Explain bonus tests and no real API calls in tests.
```

Short verbal version:

```txt
The repo is centered around main.py. main.py loads config, fetches support articles through the Zendesk API, converts the HTML bodies to clean Markdown, hashes the Markdown to detect deltas, then uploads only added or updated files to Gemini File Search. State is stored in data/state.json, and each run writes data/run-log.json with added, updated, skipped, uploaded, and estimated chunk counts. GitHub Actions runs the same job daily and uploads artifacts so the latest generated data is inspectable.
```
