from types import SimpleNamespace

import pytest

import gemini_uploader
from gemini_uploader import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TOKENS,
    ask_with_file_search,
    ensure_file_search_store,
    estimate_chunks,
    remove_documents,
    resolve_store_name,
    upload_files,
)
from state import save_state


def test_estimate_chunks_counts_at_least_one_chunk_per_file(tmp_path):
    empty_file = tmp_path / "empty.md"
    short_file = tmp_path / "short.md"
    empty_file.write_text("", encoding="utf-8")
    short_file.write_text("one two three", encoding="utf-8")

    assert estimate_chunks([empty_file, short_file]) == 2


def test_estimate_chunks_uses_configured_overlap_stride(tmp_path):
    path = tmp_path / "long.md"
    path.write_text(" ".join(["word"] * 1000), encoding="utf-8")
    stride = CHUNK_TOKENS - CHUNK_OVERLAP_TOKENS
    expected_tokens = int(1000 * 1.35)
    expected_chunks = ((expected_tokens - 1) // stride) + 1

    assert estimate_chunks([path]) == expected_chunks


def test_get_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is required"):
        gemini_uploader.get_client()


def test_resolve_store_name_prefers_environment_variable(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"articles": {}, "gemini": {"file_search_store_name": "stores/from-state"}})
    monkeypatch.setenv("GEMINI_FILE_SEARCH_STORE_NAME", "stores/from-env")

    assert resolve_store_name(state_path) == "stores/from-env"


def test_resolve_store_name_reads_state_file(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"articles": {}, "gemini": {"file_search_store_name": "stores/from-state"}})
    monkeypatch.delenv("GEMINI_FILE_SEARCH_STORE_NAME", raising=False)

    assert resolve_store_name(state_path) == "stores/from-state"


def test_resolve_store_name_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_FILE_SEARCH_STORE_NAME", raising=False)

    with pytest.raises(RuntimeError, match="Run python3 main.py first"):
        resolve_store_name(tmp_path / "missing-state.json")


class FakeStoreService:
    def __init__(self):
        self.created_config = None

    def create(self, config):
        self.created_config = config
        return SimpleNamespace(name="stores/new")


def test_ensure_file_search_store_reuses_existing_name(monkeypatch):
    monkeypatch.setenv("GEMINI_FILE_SEARCH_STORE_NAME", "stores/existing")
    client = SimpleNamespace(file_search_stores=FakeStoreService())
    state = {"gemini": {"file_search_store_name": ""}}

    assert ensure_file_search_store(client, state) == "stores/existing"
    assert client.file_search_stores.created_config is None


def test_ensure_file_search_store_creates_and_saves_name(monkeypatch):
    monkeypatch.delenv("GEMINI_FILE_SEARCH_STORE_NAME", raising=False)
    monkeypatch.setenv("GEMINI_STORE_DISPLAY_NAME", "Test Store")
    client = SimpleNamespace(file_search_stores=FakeStoreService())
    state = {}

    store_name = ensure_file_search_store(client, state)

    assert store_name == "stores/new"
    assert state["gemini"]["file_search_store_name"] == "stores/new"
    assert client.file_search_stores.created_config["display_name"] == "Test Store"


class FakeDocuments:
    def __init__(self):
        self.deleted = []

    def delete(self, name):
        self.deleted.append(name)
        if name == "documents/fail":
            raise RuntimeError("already deleted")


def test_remove_documents_skips_empty_names_and_continues_after_errors():
    documents = FakeDocuments()
    client = SimpleNamespace(file_search_stores=SimpleNamespace(documents=documents))

    remove_documents(client, ["", "documents/ok", "documents/fail"])

    assert documents.deleted == ["documents/ok", "documents/fail"]


class FakeUploadStores:
    def __init__(self):
        self.uploads = []

    def upload_to_file_search_store(self, file_search_store_name, file, config):
        self.uploads.append(
            {
                "store_name": file_search_store_name,
                "file": file,
                "config": config,
            }
        )
        return SimpleNamespace(done=True, response=SimpleNamespace(document_name=f"documents/{file.stem}"))


def test_upload_files_sends_markdown_chunking_config(tmp_path):
    path = tmp_path / "article.md"
    path.write_text("# Article", encoding="utf-8")
    stores = FakeUploadStores()
    client = SimpleNamespace(file_search_stores=stores)

    document_names = upload_files(client, "stores/abc", [path])

    assert document_names == ["documents/article"]
    assert stores.uploads[0]["store_name"] == "stores/abc"
    assert stores.uploads[0]["config"]["mime_type"] == "text/markdown"
    chunk_config = stores.uploads[0]["config"]["chunking_config"]["white_space_config"]
    assert chunk_config["max_tokens_per_chunk"] == CHUNK_TOKENS
    assert chunk_config["max_overlap_tokens"] == CHUNK_OVERLAP_TOKENS


def test_upload_files_waits_for_pending_operation(monkeypatch, tmp_path):
    path = tmp_path / "article.md"
    path.write_text("# Article", encoding="utf-8")
    pending = SimpleNamespace(done=False)
    complete = SimpleNamespace(done=True, response=SimpleNamespace(document_name="documents/waited"))
    stores = SimpleNamespace(
        upload_to_file_search_store=lambda file_search_store_name, file, config: pending
    )
    operations = SimpleNamespace(get=lambda operation: complete)
    client = SimpleNamespace(file_search_stores=stores, operations=operations)
    monkeypatch.setattr(gemini_uploader.time, "sleep", lambda seconds: None)

    assert upload_files(client, "stores/abc", [path]) == ["documents/waited"]


def test_ask_with_file_search_passes_system_prompt_and_store(monkeypatch):
    captured = {}

    def fake_generate_content(model, contents, config):
        captured["model"] = model
        captured["contents"] = contents
        captured["config"] = config
        return SimpleNamespace(text="Use the YouTube app.\n\nArticle URL: https://example.com")

    client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content))
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")

    answer = ask_with_file_search(client, "stores/abc", "How do I add a YouTube video?")

    assert "YouTube app" in answer
    assert captured["model"] == "gemini-test"
    assert captured["contents"] == "How do I add a YouTube video?"
    assert captured["config"].system_instruction == gemini_uploader.SYSTEM_PROMPT
