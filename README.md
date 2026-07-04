# kb-harvest

OptiBot mini-clone take-home: scrape OptiSigns support articles, normalize them to Markdown, upload changed files to Gemini File Search by API, and ask grounded support questions from the terminal.

## Flow

```mermaid
flowchart LR
  A[Zendesk Help Center API] --> B[Scraper]
  B --> C[Clean Markdown files]
  C --> D[SHA-256 delta check]
  D -->|added or updated| E[Gemini File Search upload]
  D -->|unchanged| F[Skip upload]
  E --> G[data/run-log.json]
  F --> G
  G --> H[GitHub Actions artifacts]
  E --> I[ask_gemini.py answers with citations]
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.sample .env
```

Fill `.env` with `GEMINI_API_KEY`. `GEMINI_FILE_SEARCH_STORE_NAME` is optional; if blank, `main.py` creates a store and saves it in `data/state.json`.

Check that commands are using the virtual environment:

```bash
which python
which pytest
```

Expected paths should start with this project path, for example `.venv/bin/python`. If `pytest` points to `/usr/bin/pytest`, reactivate the venv or use `.venv/bin/python -m pytest -q`.

## Run

Run one full scrape/upload sync:

```bash
python main.py
```

Ask the bot:

```bash
python ask_gemini.py "How do I add a YouTube video?"
```

Fetch the latest GitHub Actions-generated data back to local:

```bash
python scripts/fetch_github_actions_data.py
```

GitHub Actions artifacts require authentication through the GitHub API. If you see `401 Requires authentication`, create a GitHub token and export it before running the script:

```bash
export GH_TOKEN=REPLACE_WITH_TOKEN
python scripts/fetch_github_actions_data.py
```

For a fine-grained token:

```txt
Repository access: only nlgiahuy01112003/kb-harvest
Permissions: Actions read-only, Metadata read-only
```

`GH_TOKEN` is only for local artifact download. It is not the Gemini API key. Prefer `export GH_TOKEN=...` in the terminal. If you put it in `.env`, load it with `set -a && source .env && set +a`, and never commit `.env`.

## Docker

```bash
docker build -t kb-harvest .
docker run --env-file .env kb-harvest
```

Prompt-compatible run:

```bash
docker run -e API_KEY=REPLACE_ME kb-harvest
```

## Daily Job

GitHub Actions workflow: `.github/workflows/daily-sync.yml`

Schedule: daily at `02:00 UTC`

Last run logs: https://github.com/nlgiahuy01112003/kb-harvest/actions

Required GitHub Actions configuration:

```txt
Secret:   GEMINI_API_KEY
Variable: GEMINI_FILE_SEARCH_STORE_NAME
```

`GEMINI_FILE_SEARCH_STORE_NAME` is optional for the first run. If blank, the workflow creates a new Gemini File Search store and writes the store name to `data/run-log.json`. Add it as a repository variable when you want all later cloud runs to keep using the same store.

Artifacts produced by each run:

```txt
generated-markdown -> data/markdown/*.md
run-log            -> data/run-log.json
sync-state         -> data/state.json
```

## Implementation Notes

- Scraping uses Zendesk Help Center API instead of browser HTML scraping.
- The job pulls at least 30 articles and always includes article `360051014713` for the YouTube demo question.
- Markdown keeps headings, code blocks, useful links, and an `Article URL:` citation line.
- Delta detection uses SHA-256 hashes stored in `data/state.json`.
- Added/updated Markdown files are uploaded to Gemini. If local/cloud state has article hashes but missing Gemini document names, the job uploads those skipped files once to repair the store.
- Gemini chunking uses 512-token whitespace chunks with 100-token overlap.
- Secrets stay outside git: `.env` is ignored and `.env.sample` documents required variables.

## Code Map

| File | Role |
| --- | --- |
| `main.py` | Orchestrates the sync: config, scrape, delta check, Gemini upload, run log |
| `scraper.py` | Calls Zendesk API, writes Markdown files, updates article state |
| `markdown_cleaner.py` | Removes page noise, normalizes links, converts HTML to Markdown |
| `gemini_uploader.py` | Creates/reuses Gemini File Search Store, uploads files, asks questions |
| `ask_gemini.py` | Small CLI for testing the assistant answer |
| `state.py` | JSON state helpers and SHA-256 hashing |
| `scripts/fetch_github_actions_data.py` | Downloads latest GitHub Actions artifacts into local `data/` |
| `.github/workflows/daily-sync.yml` | Daily cloud sync job |
| `.github/workflows/ci.yml` | Tests, secret scan, deliverable check, Docker build |

## Checklist

| Requirement | Status |
| --- | --- |
| Free OptiSigns/Gemini warm-up | Manual account step |
| Scrape 30+ support articles | Done |
| Convert articles to clean Markdown | Done |
| Preserve links/headings/code and remove nav noise | Done |
| API-based Gemini File Search upload | Done |
| Log file/chunk/upload counts | Done |
| `main.py` wraps scraper/uploader | Done |
| Dockerfile runs once and exits | Done |
| Daily cloud job with artifacts/logs | Done |
| Clear `.env.sample`, no hard-coded keys | Done |
| Tests for bonus points | Done |
| Screenshot of YouTube answer | Save as `screenshots/youtube-answer.png` |

## Verify

```bash
python scripts/check_deliverables.py
python scripts/check_no_secrets.py
python -m pytest -q
```

Sample question for the screenshot:

```txt
How do I add a YouTube video?
```
