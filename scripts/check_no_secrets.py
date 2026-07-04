from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


BLOCKED_TRACKED_PATHS = {
    ".env",
    " .env",
    "data/state.json",
    "data/run-log.json",
}

SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_-]{25,}"),
    re.compile(r"AQ\.Ab8[0-9A-Za-z_-]{20,}"),
    re.compile(r"(?i)(gemini|google|api)_?key\s*=\s*[\"']?[0-9A-Za-z_.-]{20,}"),
    re.compile(r"(?i)GEMINI_API_KEY:\s*[0-9A-Za-z_.-]{20,}"),
]

SKIP_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    failures: list[str] = []
    tracked = tracked_files()

    for path in tracked:
        if path in BLOCKED_TRACKED_PATHS:
            failures.append(f"blocked tracked file: {path}")

    for raw_path in tracked:
        path = Path(raw_path)
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"possible secret in tracked file: {raw_path}")
                break

    if failures:
        print("Secret safety check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Secret safety check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
