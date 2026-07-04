from __future__ import annotations

import zipfile
import json
from pathlib import Path

import pytest

from scripts import fetch_github_actions_data as fetcher


def test_infer_repo_from_ssh_remote() -> None:
    assert (
        fetcher.infer_repo("git@github.com:nlgiahuy01112003/Mini-Cloe-test.git")
        == "nlgiahuy01112003/Mini-Cloe-test"
    )


def test_infer_repo_from_https_remote() -> None:
    assert (
        fetcher.infer_repo("https://github.com/nlgiahuy01112003/Mini-Cloe-test.git")
        == "nlgiahuy01112003/Mini-Cloe-test"
    )


def test_infer_repo_rejects_unknown_remote() -> None:
    with pytest.raises(ValueError):
        fetcher.infer_repo("git@example.com:team/repo.git")


def test_extract_markdown_flattens_artifact_paths(tmp_path: Path) -> None:
    zip_path = tmp_path / "generated-markdown.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("data/markdown/one.md", "# One\n")
        archive.writestr("data/markdown/two.md", "# Two\n")
        archive.writestr("data/run-log.json", "{}")

    output_dir = tmp_path / "markdown"
    count = fetcher._extract_markdown(zip_path, output_dir)

    assert count == 2
    assert (output_dir / "one.md").read_text(encoding="utf-8") == "# One\n"
    assert (output_dir / "two.md").read_text(encoding="utf-8") == "# Two\n"


def test_extract_single_file(tmp_path: Path) -> None:
    zip_path = tmp_path / "run-log.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("data/run-log.json", '{"ok": true}\n')

    output_path = tmp_path / "data" / "run-log.json"
    fetcher._extract_single_file(zip_path, output_path)

    assert output_path.read_text(encoding="utf-8") == '{"ok": true}\n'


def test_build_minimal_state_from_run_log_and_markdown(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    markdown_dir = data_dir / "markdown"
    markdown_dir.mkdir(parents=True)
    (data_dir / "run-log.json").write_text(
        json.dumps({"gemini_file_search_store_name": "fileSearchStores/example"}),
        encoding="utf-8",
    )
    (markdown_dir / "youtube.md").write_text(
        "\n".join(
            [
                "---",
                'title: "How to use YouTube"',
                'article_url: "https://support.optisigns.com/hc/en-us/articles/360051014713-How-to-use-YouTube-with-OptiSigns"',
                'updated_at: "2026-07-01T00:00:00Z"',
                "---",
                "",
                "# How to use YouTube",
            ]
        ),
        encoding="utf-8",
    )

    state_path = fetcher.build_minimal_state(data_dir)
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert state["gemini"]["file_search_store_name"] == "fileSearchStores/example"
    assert state["articles"]["360051014713"]["slug"] == "youtube"
    assert state["articles"]["360051014713"]["title"] == "How to use YouTube"
