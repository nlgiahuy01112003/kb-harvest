# Section 3: Reviewing And Q&A

## 16. Final Review Checklist

Run:

```bash
python3 scripts/check_no_secrets.py
python3 scripts/check_deliverables.py
pytest -q
docker build -t kb-harvest .
```

Expected:

```txt
Secret safety check passed.
Tests pass.
Docker build passes.
Deliverable checker passes everything except screenshot until you add it.
```

Manual deliverables:

```txt
GitHub repo link
GitHub Actions run log link
Video demo
screenshots/youtube-answer.png
```

## 17. How To Explain The Project In Review

Short explanation:

```txt
I used Zendesk’s Help Center API instead of scraping rendered pages, because it gives structured article bodies and pagination. I normalize those article bodies into Markdown, store each article as one file, hash the Markdown, and compare hashes between runs. Only added or updated files are uploaded to Gemini File Search by API. A GitHub Actions workflow runs the sync daily, restores previous state from cache, and uploads run logs, sync state, and generated Markdown as artifacts.
```

Why Gemini File Search:

```txt
It is the Gemini equivalent of a vector store/knowledge base. It handles embedding and retrieval, while my script controls ingestion, chunking settings, delta detection, and logging.
```

Why hash-based detection:

```txt
The Zendesk API gives updated_at, but hashing the cleaned Markdown catches meaningful content changes after normalization and avoids re-uploading unchanged files.
```

Potential improvements:

```txt
Add better source ranking for citations.
Add retry/backoff around API uploads.
Store state in durable object storage instead of GitHub cache.
Add a small admin page showing last sync status.
Add evaluation questions for regression testing answer quality.
```

Risks/challenges:

```txt
Docs can change structure.
API quotas can limit uploads.
Generated answers must stay grounded in docs.
Stale documents must be removed on updates.
Secrets must never be committed.
```

### 19.12 15-Minute Project Review Prep

This is a compact review map. The review time limit is generous, but the target should be a focused 15-minute explanation while walking through the code. Use the longer notes only for follow-up questions.

```txt
1. Overall concept understanding
2. Your approach and solution
3. How you learn something new
4. Suggestions to improve OptiBot
5. Potential challenges
```

Use this section to practice answers. Do not read every word in the interview. Use it as a map.

#### 19.12.1 One-Minute Opening Pitch

Say this first:

```txt
I built a run-once knowledge-sync pipeline for an OptiBot mini-clone. The job reads OptiSigns support articles from the Zendesk Help Center API, converts each article body into clean Markdown, saves one Markdown file per article, and tracks each file with a SHA-256 hash. On each run, it detects whether articles are added, updated, or skipped. Only added or updated Markdown files are uploaded to a Gemini File Search Store by API. The assistant uses the required OptiBot system prompt and answers with Article URL citations from the uploaded Markdown. The daily automation runs through GitHub Actions, restores state from cache, writes a run log, and uploads generated Markdown plus logs as artifacts.
```

Then say why this matches the assignment:

```txt
The main requirement was ingestion plus API-based vector-store upload, not a manual UI upload. So I focused on a reliable scraper-uploader job, Dockerized it, scheduled it daily, and added tests and secret checks.
```

Mention the YouTube sample:

```txt
For the required sample question, "How do I add a YouTube video?", I added a required seed article ID for the correct YouTube article. That article is older than the newest article page, so relying only on the first 35 newest articles can retrieve the YouTube Dashboard article instead of the plain YouTube app article.
```

#### 19.12.2 Concept Understanding

The project is a small Retrieval-Augmented Generation system.

Explain RAG in simple words:

```txt
The model should not answer from general knowledge. It should first retrieve relevant support documents from a knowledge base, then answer using those documents. In this project, the knowledge base is Gemini File Search Store, and the documents are Markdown versions of OptiSigns support articles.
```

The system has four layers:

```txt
1. Ingestion:
   Fetch support articles from Zendesk.

2. Normalization:
   Convert messy HTML into clean Markdown.

3. Indexing:
   Upload Markdown files into Gemini File Search by API.

4. Answering:
   Ask Gemini with File Search enabled and require Article URL citations.
```

Why Markdown:

```txt
Markdown is readable, easy to diff, easy to hash, and keeps headings, lists, links, and code blocks. It is also a clean input format for retrieval.
```

Why one file per article:

```txt
One file per article keeps source boundaries clear. If an article changes, I can update only that article's file and Gemini document.
```

Why hash-based delta detection:

```txt
Hashing the cleaned Markdown tells me whether the uploaded content changed. If the hash is the same, I skip upload. If it is different, I upload the new version and delete the stale Gemini document.
```

Why `main.py` exits:

```txt
This is a scheduled data sync job, not a web server. The Docker requirement says docker run should run once and exit 0, so main.py does exactly one sync and exits.
```

#### 19.12.3 Architecture Walkthrough

Use this flow diagram:

```txt
GitHub Actions / Docker / local terminal
  -> main.py
  -> load .env and data/state.json
  -> scraper.fetch_articles()
  -> markdown_cleaner.article_to_markdown()
  -> scraper.write_markdown_articles()
  -> gemini_uploader.ensure_file_search_store()
  -> gemini_uploader.remove_documents()
  -> gemini_uploader.upload_files()
  -> data/run-log.json
  -> save data/state.json
```

Explain each file:

```txt
state.py:
  Handles JSON state, SHA-256 hashing, and run-log writing.

markdown_cleaner.py:
  Converts Zendesk article HTML to clean Markdown.

scraper.py:
  Calls the Zendesk API, handles pagination, writes Markdown, and labels articles as added/updated/skipped.

gemini_uploader.py:
  Creates/reuses Gemini File Search Store, uploads files, deletes stale documents, and asks Gemini with File Search.

main.py:
  Orchestrates the whole sync job.

ask_gemini.py:
  CLI helper to test the assistant with the uploaded File Search Store.

.github/workflows/daily-sync.yml:
  Runs the sync every day and uploads artifacts.

.github/workflows/ci.yml:
  Runs tests, compile check, secret scan, deliverable checker, and Docker build.
```

Explain state:

```txt
state.json is the memory of the job. It stores article hashes, Markdown paths, and Gemini document names. Without state, every run would upload every file again.
```

Explain run log:

```txt
run-log.json is the evidence for the daily job. It records articles_seen, added, updated, skipped, files_uploaded, uploaded_document_names, estimated_chunks, and the File Search Store name.
```

#### 19.12.4 Approach And Solution

Start with the problem:

```txt
The main problem is turning messy support content into a searchable, cited knowledge base that can be updated every day without manual work.
```

Your approach:

```txt
I split the problem into small modules: scrape, clean, state, upload, orchestrate, test, deploy. I avoided putting everything in one large script because each part has a different responsibility and is easier to test separately.
```

Why Zendesk API instead of browser scraping:

```txt
The support site is powered by Zendesk, and the Help Center API returns article JSON with title, URL, updated_at, and body. This is more reliable than scraping rendered HTML pages, which may include navigation, layout, or JavaScript noise.
```

Why Gemini File Search:

```txt
The task allowed OpenAI or Gemini. I chose Gemini and used Gemini File Search as the vector-store/knowledge-base equivalent. The script uploads files through the API, which satisfies the no drag-and-drop requirement.
```

Why chunking settings:

```txt
I used whitespace chunking with 512 max tokens per chunk and 100 overlap tokens. The chunks are small enough for focused retrieval, while the overlap helps when an answer spans a boundary between chunks.
```

Why tests:

```txt
I added offline tests for important behavior: Markdown cleaning, scraper pagination, required YouTube article inclusion, state writes, Gemini upload config, and main.py orchestration. The tests do not call real Zendesk or Gemini APIs, so CI is fast and stable.
```

Why GitHub Actions:

```txt
The assignment requires a daily public/cloud job. GitHub Actions is simple for a take-home, has visible logs, supports secrets, supports scheduled cron, and can upload artifacts for review.
```

#### 19.12.5 Demo Script

Use this flow in the video or live review:

```bash
# 1. Show files
ls

# 2. Show safe env template, not real .env
cat .env.sample

# 3. Run tests
pytest -q

# 4. Run deliverable checker
python3 scripts/check_deliverables.py

# 5. Run sync locally
python3 main.py

# 6. Show run log
cat data/run-log.json

# 7. Ask required sample question
python3 ask_gemini.py "How do I add a YouTube video?"

# 8. Show Docker behavior
docker build -t kb-harvest .
docker run --env-file .env kb-harvest
```

What to point out during the demo:

```txt
data/markdown contains 36 generated Markdown files.
run-log.json shows added/updated/skipped/upload counts.
The YouTube sample answer cites the correct Article URL.
GitHub Actions runs the same job daily.
.env is ignored and not committed.
```

Expected YouTube citation:

```txt
Article URL: https://support.optisigns.com/hc/en-us/articles/360051014713-How-to-use-YouTube-with-OptiSigns
```

#### 19.12.6 How I Learned Something New

Use this answer:

```txt
When I work with a new API or platform, I start by identifying the smallest end-to-end path. For this project, that path was: fetch one Zendesk article, convert it to Markdown, upload one Markdown file to Gemini File Search, and ask one question with citations. After that worked, I expanded it into pagination, multiple files, delta detection, state, Docker, GitHub Actions, and tests.
```

Then explain your learning method:

```txt
I read the official API docs first, then write a small throwaway experiment. Once I understand the response shape and failure modes, I move the working code into a clean module. I add logging and tests around behavior that could break, such as pagination, state persistence, and upload config.
```

Good example from this project:

```txt
The first YouTube answer retrieved the YouTube Dashboard article instead of the normal YouTube app article. I treated that as a retrieval/corpus problem, not only a prompt problem. I checked the local Markdown corpus, found the correct article was missing, found its Zendesk article ID, and added SUPPORT_REQUIRED_ARTICLE_IDS so the right source is always uploaded.
```

What this shows:

```txt
I debug by checking the data pipeline first: what documents exist, what was uploaded, what the model can retrieve, and what source it cites.
```

#### 19.12.7 Suggestions To Improve OptiBot

Suggest practical improvements:

```txt
1. Better source ranking:
   Prefer exact app articles over related dashboard or analytics articles for simple "how do I add X" questions.

2. Query classification:
   Detect intent categories like setup, billing, player troubleshooting, app configuration, scheduling, playlists, or hardware.

3. Clarifying questions:
   If the user says "YouTube", ask whether they mean YouTube video, YouTube Live, Shorts, or YouTube Dashboard when retrieval confidence is mixed.

4. Answer quality evaluation:
   Keep a test set of common support questions and expected source articles. Run it automatically after each knowledge sync.

5. Freshness metadata:
   Prefer newer documents only when they are equally relevant, but do not let newer unrelated docs outrank older exact docs.

6. Human escalation:
   If no strong article is found, provide a short fallback and suggest contacting support instead of hallucinating.

7. Better citations:
   Always show article title plus URL, not only URL, so users understand the source before clicking.

8. Multi-language support:
   Index locale-specific Help Center articles and answer in the user's language when possible.

9. Feedback loop:
   Track thumbs-up/down and unresolved questions to improve docs and retrieval.

10. Admin sync dashboard:
    Show last sync time, article counts, failed uploads, and top missing-answer questions.
```

Tie improvements to business value:

```txt
Better retrieval reduces support load.
Clear citations increase user trust.
Evaluation catches regressions before customers see them.
Feedback data tells the documentation team what articles are missing or confusing.
```

#### 19.12.8 Potential Challenges

Challenge: messy article HTML

```txt
Support articles may contain images, embeds, tables, scripts, or layout wrappers. The cleaner must remove noise without deleting meaningful content.
```

Challenge: retrieval ambiguity

```txt
"YouTube" can mean YouTube video, YouTube Live, Shorts, or YouTube Dashboard. If multiple articles mention the same keyword, retrieval can select a related but wrong article.
```

Challenge: stale documents

```txt
If updated articles are uploaded without deleting old documents, the bot may retrieve outdated instructions. That is why the state stores gemini_document_name and updated articles delete stale docs first.
```

Challenge: API quota and rate limits

```txt
Gemini uploads and Zendesk requests can hit limits. A production version should add retry with exponential backoff and alerting.
```

Challenge: GitHub Actions cache

```txt
GitHub cache is convenient for a take-home, but not a perfect database. For production, state should live in durable storage like Postgres, S3/GCS, Redis, or another managed store.
```

Challenge: answer grounding

```txt
Even with File Search, the model can over-explain or include general knowledge. The prompt says only answer using uploaded docs, but production should also evaluate citations and block low-confidence answers.
```

Challenge: secrets

```txt
API keys must never be committed. The repo uses .gitignore, .env.sample, GitHub secrets, and a secret scanner to reduce this risk.
```

#### 19.12.9 Likely Interview Questions And Answers

Question:

```txt
Why did you use Zendesk API?
```

Answer:

```txt
Because it gives structured article data directly, including title, URL, updated_at, and body. Scraping rendered pages would include nav/sidebar/script noise and be more fragile.
```

Question:

```txt
Why did you convert to Markdown?
```

Answer:

```txt
Markdown is clean, readable, easy to diff, easy to hash, and preserves headings, links, lists, and code blocks. It is also a good format for retrieval.
```

Question:

```txt
How do you upload only the delta?
```

Answer:

```txt
After converting each article to Markdown, I hash the Markdown. I compare the hash against the previous state. New hash means added, different hash means updated, same hash means skipped. Only added/updated files are uploaded.
```

Question:

```txt
How do you avoid stale content?
```

Answer:

```txt
For updated articles, the state contains the previous Gemini document name. Before uploading the new Markdown, I delete the stale Gemini document. Then I save the new document name.
```

Question:

```txt
Why not commit generated Markdown?
```

Answer:

```txt
Generated Markdown can be large and changes daily. The repo stays cleaner if generated files are ignored. GitHub Actions uploads them as artifacts, so reviewers can still inspect the exact generated output.
```

Question:

```txt
What happens if GitHub Actions starts with no state?
```

Answer:

```txt
It treats articles as added and uploads them. After that, the workflow caches data/state.json so later runs can skip unchanged articles.
```

Question:

```txt
Why did the first YouTube answer differ from OptiBot?
```

Answer:

```txt
The correct YouTube article was not in the first 35 newest articles, so the knowledge base only had a YouTube Dashboard article. I fixed that by adding SUPPORT_REQUIRED_ARTICLE_IDS=360051014713, so the exact YouTube article is always included.
```

Question:

```txt
What would you improve with more time?
```

Answer:

```txt
I would add retry/backoff, durable state storage, retrieval evaluation tests, better article ranking, and a small dashboard for sync health and failed uploads.
```

Question:

```txt
How would you scale this?
```

Answer:

```txt
I would store state in a database, process articles in batches, add rate-limit-aware retries, add monitoring/alerts, and run evaluation after each sync. For many locales, I would index each locale separately and route questions by language.
```

#### 19.12.10 What To Show In The Repo

During review, open these files in this order:

```txt
README.md
  Shows setup, run commands, Docker, chunking, and daily job logs.

main.py
  Shows the full orchestration in one place.

scraper.py
  Shows Zendesk pagination, required article IDs, and delta detection.

markdown_cleaner.py
  Shows HTML cleanup and Markdown conversion.

gemini_uploader.py
  Shows API upload, chunking config, File Search tool, and system prompt.

.github/workflows/daily-sync.yml
  Shows daily automation and artifacts.

tests/
  Shows bonus test coverage.
```

#### 19.12.11 Final Submission Checklist

Before replying to the email, confirm:

```txt
[ ] GitHub repo URL is cryptic and not named OptiSigns.
[ ] Repo is pushed.
[ ] .env is not tracked.
[ ] README has setup, local run, Docker, chunking, daily logs, sample screenshot path.
[ ] GitHub Actions daily-sync workflow exists.
[ ] Last Actions run has run-log, sync-state, and generated-markdown artifacts.
[ ] python3 ask_gemini.py "How do I add a YouTube video?" cites the correct article.
[ ] Screenshot saved as screenshots/youtube-answer.png or included in video.
[ ] Video demonstrates scraper run, generated Markdown, run-log, assistant answer, and GitHub Actions.
```

#### 19.12.12 Strong Closing Statement

End the review with:

```txt
The main thing I optimized for was a reliable ingestion pipeline rather than a flashy interface. The assistant quality depends heavily on the quality and freshness of the knowledge base, so I focused on clean Markdown, delta detection, API-based upload, daily automation, logs, and tests. With more time, I would improve retrieval evaluation and production state storage.
```

## 21. 15-Minute Presentation Script

Use this section with the Figma diagram. The presentation should feel like you are walking through the code, not reading a long essay.

### 21.1 Timeline

```txt
0:00-1:00   Personal intro and why this project fits backend/data pipeline work.
1:00-2:00   Explain the work timeline: received email, research, demo, final implementation.
2:00-3:00   Show Figma diagram and say the project has one shared pipeline plus two run paths.
3:00-5:00   Explain the shared pipeline: Zendesk API -> Markdown -> delta -> Gemini upload.
5:00-6:30   Explain local scrape path: python3 main.py -> local data/ -> ask_gemini.py.
6:30-8:00   Explain GitHub Actions path: daily-sync.yml -> cloud run -> artifacts.
8:00-10:00  Open main.py and explain run_sync().
10:00-11:30 Open scraper.py and markdown_cleaner.py.
11:30-12:30 Open gemini_uploader.py.
12:30-14:00 Show run-log/artifacts and answer screenshot or CLI output.
14:00-15:00 Answer the five discussion questions.
```

### 21.2 Opening Script

Say:

```txt
Hi, my name is Nguyen Le Gia Huy. I am a backend-oriented full-stack developer. My main stack is TypeScript, NestJS, Next.js, PostgreSQL, Prisma, Docker, and backend/API system design.

When I received this take-home, I treated it as a data pipeline problem. The chatbot answer is the final visible output, but the important engineering work is how the knowledge is collected, cleaned, updated, uploaded, and verified.
```

Then say:

```txt
I received the email yesterday at 3:00 PM. From around 6:00 PM to 10:00 PM, I focused on understanding the requirement and learning the unfamiliar parts: RAG support bots, Zendesk Help Center API, OptiSigns support docs, Gemini File Search, and GitHub Actions scheduled jobs.

This morning at 6:00 AM, I started with a small demo: fetch one article, convert it to Markdown, upload it, and ask one question. After that worked, I expanded the same flow into the full take-home requirement.
```

Key point:

```txt
I started with a small vertical slice because it is the fastest way to reduce technical risk when the topic is new.
```

### 21.3 Opening With The Figma Diagram

Say:

```txt
I planned this project as a knowledge pipeline, not a UI-first chatbot. The top lane is the shared ingestion pipeline. The middle lane is the local scrape path I use for development and testing. The bottom lane is the GitHub Actions daily scrape path required by the assignment.
```

Then explain the three lanes:

```txt
Shared pipeline:
Support Site -> Scraper -> Markdown Cleaner -> Delta Detection -> Gemini Upload.

Local scrape:
python3 main.py writes local data files, then ask_gemini.py asks the Gemini File Search Store and prints a cited answer.

GitHub Actions scrape:
daily-sync.yml runs the same main.py in cloud, uses GitHub secrets, uploads generated Markdown, run-log, and sync-state artifacts, then fetch_github_actions_data.py can mirror those artifacts back to local.
```

### 21.4 Shared Pipeline Talk Track

Use this while pointing at the top Figma lane:

```txt
The source is support.optisigns.com, which is powered by Zendesk. I use Zendesk Help Center API because it gives structured article JSON instead of noisy rendered HTML.

scraper.py fetches at least 30 articles, handles pagination, and force-includes the required YouTube article ID. That avoids the wrong YouTube Dashboard answer.

markdown_cleaner.py converts each article body from HTML to clean Markdown. It removes noisy tags, normalizes links, preserves structure, and adds an Article URL line for citations.

state.py stores hashes and article metadata. Each Markdown file is hashed with SHA-256, so the job can classify articles as added, updated, or skipped.

gemini_uploader.py uploads only added or updated files to Gemini File Search by API. For updated articles, it deletes the stale Gemini document first.
```

### 21.5 Zendesk API And BeautifulSoup Explanation

Use this when opening `scraper.py` and `markdown_cleaner.py`:

```txt
OptiSigns support articles are hosted on Zendesk Help Center, so I used the Zendesk Help Center Articles API instead of scraping rendered browser pages.

The API endpoints return structured JSON:

https://support.optisigns.com/api/v2/help_center/en-us/articles.json
https://support.optisigns.com/api/v2/help_center/en-us/articles/{article_id}.json

From each article JSON, I use fields like id, title, body, html_url, and updated_at. The body field is still HTML, so the next step is cleaning and converting it.
```

Explain the library roles:

```txt
requests is responsible for calling the Zendesk API.

beautifulsoup4 is not used to fetch the articles. It is used after the API response arrives, because Zendesk article bodies are HTML. BeautifulSoup parses that HTML safely, removes noisy tags, normalizes links, and prepares the content before markdownify converts it into Markdown.
```

The actual flow:

```txt
Zendesk API
  -> article JSON
  -> body HTML
  -> BeautifulSoup cleanup
  -> markdownify HTML-to-Markdown conversion
  -> data/markdown/<slug>.md
```

Why this decision is better than plain browser scraping:

```txt
The Zendesk API is more stable because it gives structured article data and pagination. Browser scraping would require removing navigation, layout, JavaScript-generated content, and other page noise. The API lets me focus on article content quality and delta detection.
```

Short answer if the interviewer asks "What is Zendesk used for?":

```txt
Zendesk is the source API for OptiSigns support articles. I use it to fetch clean article metadata and HTML bodies. Then I use BeautifulSoup and markdownify to normalize those bodies into Markdown for Gemini File Search.
```

### 21.6 Local Scrape Talk Track

Use this while pointing at the purple lane:

```txt
Local scrape is the development and demo path. I run python3 main.py, and it writes data/markdown, data/state.json, and data/run-log.json locally.

After that, I run ask_gemini.py with a question like "How do I add a YouTube video?" The script does not answer from local Markdown directly. It resolves the Gemini File Search Store name from .env or data/state.json, asks Gemini with File Search enabled, and prints an answer with Article URL citations.
```

Command sequence:

```bash
python3 main.py
python3 ask_gemini.py "How do I add a YouTube video?"
```

Key point:

```txt
Local files are useful for debugging and proof, but the assistant's canonical knowledge is the Gemini File Search Store.
```

### 21.7 GitHub Actions Cloud Scrape Talk Track

Use this while pointing at the blue lane:

```txt
GitHub Actions is the cloud daily job. The workflow can run on a schedule or manually through workflow_dispatch.

daily-sync.yml checks out the repo, installs dependencies, restores previous state from cache, validates secrets, then runs python main.py.

The cloud run uses the same shared pipeline as local. It re-scrapes, detects deltas, uploads only changed files, and writes logs.

At the end, GitHub Actions uploads three artifacts: generated-markdown, run-log, and sync-state. These artifacts are important because they prove the job ran and let reviewers inspect the generated files without committing them to git.
```

Command to mirror cloud output locally:

```bash
python3 scripts/fetch_github_actions_data.py
```

If GitHub requires auth:

```bash
export GH_TOKEN=YOUR_TOKEN
python3 scripts/fetch_github_actions_data.py
```

Key point:

```txt
If GitHub Actions has newer Markdown than local, this script downloads the latest artifacts back into data/.
```

### 21.8 Code Walkthrough Order

Open files in this order:

```txt
1. README.md
   Show flow, setup, daily job, checklist.

2. requirements.txt
   Quickly explain the libraries:
   requests, beautifulsoup4, markdownify, google-genai, python-dotenv, pytest.

3. main.py
   Show SyncConfig and run_sync().

4. scraper.py
   Show fetch_articles(), required article IDs, detect_status().

5. markdown_cleaner.py
   Show remove_page_noise(), normalize_links(), clean_markdown().

6. gemini_uploader.py
   Show SYSTEM_PROMPT, upload_files(), ask_with_file_search().

7. state.py
   Show load_state(), save_state(), sha256_text().

8. .github/workflows/daily-sync.yml
   Show schedule, secrets, artifacts.

9. data/run-log.json or GitHub Actions summary
   Show added, updated, skipped, uploaded, estimated_chunks.
```

Short module explanation:

```txt
I kept each file with one responsibility. main.py orchestrates the sync. scraper.py gets article data from Zendesk. markdown_cleaner.py turns article HTML into Markdown. state.py tracks hashes and document names. gemini_uploader.py talks to Gemini. ask_gemini.py is only a CLI test helper.
```

Short class explanation:

```txt
There are only two main data classes. SyncConfig holds environment/configuration values for one run. ScrapedArticle represents one processed article after it has been fetched, converted, hashed, and written to disk.
```

### 21.9 What To Say For `main.py`

```txt
main.py is the orchestrator. I kept main() small, so the real story is run_sync().

run_sync() loads state, fetches articles, writes Markdown, finds changed articles, creates or reuses the Gemini File Search Store, uploads changed files, writes run-log.json, saves state, and exits.

This matches the Docker requirement because the job runs once and exits 0. It is not a web server.
```

### 21.10 Five Discussion Questions

#### Q1. Overall concept understanding

```txt
This is a retrieval-augmented support bot pipeline. The bot should answer from OptiSigns support documents, not from general model memory. So the core work is ingesting docs, cleaning them, keeping them fresh, uploading them to a searchable store, and asking Gemini with File Search so answers include citations.
```

#### Q2. Approach and solution

```txt
I split the project into small modules: scraper.py for Zendesk API, markdown_cleaner.py for HTML-to-Markdown cleanup, state.py for hashes and metadata, gemini_uploader.py for Gemini API work, main.py for orchestration, and GitHub Actions for daily cloud automation.
```

Tradeoffs:

```txt
Zendesk API is more stable than browser scraping.
Markdown is readable and retrieval-friendly.
SHA-256 hashes make delta detection simple.
GitHub Actions gives visible logs and downloadable artifacts.
```

#### Q3. How do you learn something new?

```txt
I start with the smallest vertical slice. For this project: fetch one Zendesk article, convert one article to Markdown, upload one Markdown file to Gemini File Search, then ask one question. After that works, I expand to pagination, state, delta detection, Docker, GitHub Actions, and tests.
```

#### Q4. Suggestions to improve OptiBot

```txt
The biggest improvement is evaluation. I would build a small benchmark of real support questions and expected Article URL citations, then run it after each sync to catch retrieval regressions.
```

Other improvements:

```txt
Ask clarifying questions for ambiguous requests.
Show article titles with URLs.
Add user feedback buttons.
Escalate to human support when docs do not answer.
Add sync health dashboard.
Support multiple locales.
```

#### Q5. Potential challenges

```txt
Stale content: old vector documents can conflict with updated docs, so I delete stale documents before upload.

Ambiguous questions: YouTube can mean normal YouTube video, Shorts, or YouTube Dashboard.

Retrieval accuracy: similar docs can be retrieved incorrectly, so evaluation tests are needed.

API reliability: Zendesk or Gemini can fail or rate-limit, so production needs retries and alerting.

State durability: GitHub Actions cache is acceptable for a take-home, but production should use durable storage.
```

### 21.11 YouTube Demo Explanation

If they ask why the YouTube answer was important:

```txt
The required sample question is "How do I add a YouTube video?" The correct article is older than the newest articles list, so only scraping the first newest 35 can miss it and retrieve a related YouTube Dashboard article instead. I fixed this with SUPPORT_REQUIRED_ARTICLE_IDS=360051014713, so the correct YouTube article is always included.
```

### 21.12 Unknown Question Behavior

If they ask what happens when the question is not in the scraped data:

```txt
The bot should not invent an answer. The system prompt says it can only answer using uploaded docs. If the docs do not directly answer the question, the expected behavior is to say that the answer was not found in the uploaded OptiSigns documents.

For example, if I ask "How do I integrate OptiSigns with a coffee machine?", Gemini may retrieve loosely related integration documents, but the important final answer is that there is no documentation for a direct coffee machine integration. In production, I would make the fallback stricter so unrelated retrieved docs are not summarized.
```

### 21.13 Closing

```txt
I optimized for a reliable knowledge pipeline: clean ingestion, hash-based delta detection, API-based Gemini upload, daily automation, logs, artifacts, and tests. The UI is intentionally not the focus. The core deliverable is that OptiBot answers from fresh uploaded docs with citations.
```
