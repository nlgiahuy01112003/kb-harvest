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
