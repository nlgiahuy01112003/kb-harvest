import json

from state import load_state, save_state, sha256_text, write_json


def test_load_state_returns_fresh_default_when_file_missing(tmp_path):
    first = load_state(tmp_path / "missing.json")
    second = load_state(tmp_path / "missing.json")

    first["articles"]["1"] = {"title": "changed"}

    assert second["articles"] == {}
    assert second["gemini"]["file_search_store_name"] == ""


def test_load_state_normalizes_old_state_shape(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text('{"articles": {"1": {"title": "One"}}}', encoding="utf-8")

    state = load_state(state_path)

    assert state["articles"]["1"]["title"] == "One"
    assert state["gemini"]["file_search_store_name"] == ""


def test_save_state_creates_parent_directory_and_writes_pretty_json(tmp_path):
    state_path = tmp_path / "nested" / "state.json"
    save_state(state_path, {"articles": {}, "gemini": {"file_search_store_name": "stores/abc"}})

    loaded = json.loads(state_path.read_text(encoding="utf-8"))

    assert loaded["gemini"]["file_search_store_name"] == "stores/abc"
    assert state_path.read_text(encoding="utf-8").endswith("\n")


def test_write_json_creates_parent_directory(tmp_path):
    log_path = tmp_path / "data" / "run-log.json"
    write_json(log_path, {"added": 1, "skipped": 2})

    assert json.loads(log_path.read_text(encoding="utf-8")) == {"added": 1, "skipped": 2}


def test_sha256_text_is_stable_for_utf8_input():
    assert sha256_text("OptiBot") == sha256_text("OptiBot")
    assert sha256_text("OptiBot") != sha256_text("optibot")
