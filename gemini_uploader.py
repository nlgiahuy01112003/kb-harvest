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
        raise RuntimeError("GEMINI_API_KEY is required. API_KEY is also accepted as an alias.")
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

    display_name = os.getenv("GEMINI_STORE_DISPLAY_NAME", "OptiSigns Support Articles")
    embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    store = client.file_search_stores.create(
        config={
            "display_name": display_name,
            "embedding_model": embedding_model,
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
        LOGGER.info("Removing stale Gemini document: %s", document_name)
        try:
            client.file_search_stores.documents.delete(name=document_name)
        except Exception as exc:
            LOGGER.warning("Could not remove %s: %s", document_name, exc)


def upload_files(client: genai.Client, store_name: str, paths: list[Path]) -> list[str]:
    document_names: list[str] = []

    for path in paths:
        LOGGER.info("Uploading %s to Gemini File Search Store", path)
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
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    response = client.models.generate_content(
        model=model,
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
