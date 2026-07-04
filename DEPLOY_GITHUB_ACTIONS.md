# GitHub Actions + Gemini Deployment Guide

Use this as the free daily-job deployment path for this take-home.

## 1. Add Repository Secrets

In GitHub:

1. Open the repository.
2. Go to `Settings` -> `Secrets and variables` -> `Actions`.
3. Click `New repository secret`.
4. Add:

```txt
GEMINI_API_KEY
GEMINI_FILE_SEARCH_STORE_NAME
```

Use your rotated Gemini API key. Do not commit `.env`.

Use the File Search Store from your successful local run unless you create a new one:

```txt
fileSearchStores/your-store-name
```

## 2. Run The Daily Workflow Manually

In GitHub:

1. Go to `Actions`.
2. Open `Daily Knowledge Sync`.
3. Click `Run workflow`.
4. Use:

```txt
max_articles: 35
dry_run_scrape_only: false
```

The workflow runs `python main.py`, uploads only changed articles, and saves cloud artifacts:

```txt
run-log            -> data/run-log.json
sync-state         -> data/state.json
generated-markdown -> data/markdown/*.md
```

## 3. Daily Schedule

The workflow runs every day at:

```txt
0 2 * * *
```

That is `02:00 UTC`.

## 4. Delta Detection On GitHub Actions

GitHub runners are fresh every run, so the workflow restores `data/state.json` using `actions/cache`.

This keeps the assignment behavior:

```txt
added
updated
skipped
files_uploaded
estimated_chunks
```

First run usually uploads all 35 files. Later runs should mostly show:

```txt
added=0
updated=0
skipped=35
files_uploaded=0
```

## 5. Logs For Submission

After a successful run:

1. Open the workflow run.
2. Copy the run URL into `README.md`.
3. Download or open the `run-log`, `sync-state`, and `generated-markdown` artifacts.
4. Show the Actions summary and artifacts in your demo video.

This satisfies the daily job requirement without extra hosting.

## 6. Asking The Bot

This project does not use GitHub Pages or a hosted web UI. Ask the assistant from the CLI so the Gemini API key stays in `.env` locally or in GitHub Actions secrets:

```bash
python3 ask_gemini.py "How do I add a YouTube video?"
```

If local `data/` is missing, set `GEMINI_FILE_SEARCH_STORE_NAME` in `.env` to the cloud File Search Store created by `main.py` or GitHub Actions.
