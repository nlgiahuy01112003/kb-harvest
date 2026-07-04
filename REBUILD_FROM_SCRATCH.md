# Rebuild From Scratch

This is the entry point for the live-coding and presentation script.

The full script is split into three focused sections so it is easier to use during review:

```txt
1. Introduction + Planning
2. Coding + Deploying
3. Reviewing + Q&A
```

## 1. Introduction And Planning

File:

```txt
docs/rebuild/01_introduction_planning.md
```

Use this section at the beginning of the presentation.

It covers:

- Personal introduction.
- Work timeline after receiving the email.
- Project goal.
- Figma pipeline plan.
- System overview.
- Library explanation.
- Module/class responsibility map.
- Environment variables and project file overview.

Recommended speaking order:

```txt
1. Introduce yourself.
2. Explain the timeline:
   - Email received yesterday at 3:00 PM.
   - Research from 6:00 PM to 10:00 PM.
   - Demo started today at 6:00 AM.
   - Full implementation expanded from the demo.
3. Show the Figma architecture diagram.
4. Explain why this is a knowledge pipeline, not a UI-first chatbot.
5. Explain libraries and modules before coding.
```

## 2. Coding And Deploying

File:

```txt
docs/rebuild/02_coding_deploying.md
```

Use this section when you code or explain the implementation.

It covers:

- Rebuild from a blank folder.
- `state.py`
- `markdown_cleaner.py`
- `scraper.py`
- `gemini_uploader.py`
- `main.py`
- `ask_gemini.py`
- Dockerfile.
- GitHub Actions daily job.
- CI workflow.
- Tests.
- Exact verification commands.

Recommended coding order:

```txt
1. requirements.txt
2. .env.sample and .gitignore
3. state.py
4. markdown_cleaner.py
5. scraper.py
6. gemini_uploader.py
7. main.py
8. ask_gemini.py
9. Dockerfile
10. GitHub Actions workflow
11. tests
12. verification commands
```

## 3. Reviewing And Q&A

File:

```txt
docs/rebuild/03_reviewing.md
```

Use this section after the code walkthrough.

It covers:

- 15-minute project review script.
- One-minute opening pitch.
- Concept understanding.
- Architecture walkthrough.
- Approach and solution.
- Demo script.
- How you learned new tools.
- Suggestions to improve OptiBot.
- Potential challenges.
- Likely interview questions and answers.
- Final submission checklist.
- Current code function-by-function explanation.

Recommended review order:

```txt
1. Run or show tests.
2. Show generated Markdown.
3. Show run-log.json.
4. Show GitHub Actions artifacts.
5. Ask the required YouTube question.
6. Explain what happens for unknown/out-of-scope questions.
7. Answer review questions.
8. Close with tradeoffs and production improvements.
```

## Fast 15-Minute Flow

If time is short, use this compressed flow:

```txt
0:00-1:00   Introduce yourself and project goal.
1:00-2:00   Explain timeline and learning approach.
2:00-3:00   Show Figma pipeline.
3:00-5:00   Explain Zendesk -> Markdown -> Gemini flow.
5:00-8:00   Walk through main.py, scraper.py, markdown_cleaner.py.
8:00-10:00  Walk through gemini_uploader.py and state.py.
10:00-12:00 Show GitHub Actions, artifacts, Docker.
12:00-14:00 Show tests, run-log, and sample answer.
14:00-15:00 Answer Q&A: concept, approach, learning, improvements, challenges.
```

## One-Sentence Summary

```txt
This project is a run-once knowledge sync pipeline: it fetches OptiSigns Zendesk articles, converts them to clean Markdown, detects deltas with hashes, uploads only changed files to Gemini File Search by API, and proves the result with logs, artifacts, tests, and cited answers.
```
