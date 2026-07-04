from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def tracked(path: str) -> bool:
    result = subprocess.run(
        ["git", "ls-files", path],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def status_line(ok: bool, label: str, detail: str = "") -> str:
    marker = "PASS" if ok else "TODO"
    suffix = f" - {detail}" if detail else ""
    return f"[{marker}] {label}{suffix}"


def main() -> int:
    markdown_files = sorted((ROOT / "data" / "markdown").glob("*.md"))
    run_log_path = ROOT / "data" / "run-log.json"
    screenshot_path = ROOT / "screenshots" / "youtube-answer.png"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    run_log = {}
    if run_log_path.exists():
        run_log = json.loads(run_log_path.read_text(encoding="utf-8"))

    checks = [
        (
            len(markdown_files) >= 30,
            "Scraped at least 30 Markdown files",
            f"{len(markdown_files)} found locally",
        ),
        (
            (ROOT / "main.py").exists(),
            "Run-once scraper/uploader is wrapped in main.py",
            "",
        ),
        (
            (ROOT / "Dockerfile").exists() and "python\", \"main.py" in (ROOT / "Dockerfile").read_text(),
            "Dockerfile runs main.py once",
            "",
        ),
        (
            (ROOT / ".github" / "workflows" / "daily-sync.yml").exists(),
            "Daily GitHub Actions workflow exists",
            "",
        ),
        (
            "github.com/nlgiahuy01112003/kb-harvest/actions" in readme or "actions/runs/" in readme,
            "README includes daily job log link",
            "",
        ),
        (
            bool(run_log) and {"added", "updated", "skipped", "files_uploaded"} <= set(run_log),
            "Run log contains added/updated/skipped/uploaded counts",
            "",
        ),
        (
            (ROOT / ".env.sample").exists() and not tracked(".env"),
            ".env.sample exists and .env is not tracked",
            "",
        ),
        (
            (ROOT / "tests").exists(),
            "Bonus tests exist",
            "",
        ),
        (
            screenshot_path.exists(),
            "Assistant screenshot exists",
            "save as screenshots/youtube-answer.png",
        ),
    ]

    for ok, label, detail in checks:
        print(status_line(ok, label, detail))

    print()
    print("Generated Markdown artifact:")
    print("- GitHub Actions uploads data/markdown/*.md as artifact named generated-markdown.")
    print("- GitHub Actions uploads data/run-log.json as artifact named run-log.")
    print("- GitHub Actions uploads data/state.json as artifact named sync-state.")
    print("- Local generated files are ignored by git, which keeps the repository clean.")
    print()
    print("This script is advisory, so TODO items do not fail CI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
