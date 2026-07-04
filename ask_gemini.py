from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from gemini_uploader import ask_with_file_search, get_client, resolve_store_name

STATE_PATH = Path("data") / "state.json"


def main() -> int:
    load_dotenv()
    question = " ".join(os.sys.argv[1:]) or "How do I add a YouTube video?"
    try:
        store_name = resolve_store_name(STATE_PATH)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=os.sys.stderr)
        print(
            "Fix: run `python3 main.py` once, or set GEMINI_FILE_SEARCH_STORE_NAME in `.env`.",
            file=os.sys.stderr,
        )
        return 1

    answer = ask_with_file_search(get_client(), store_name, question)
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
