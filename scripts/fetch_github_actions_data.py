from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


DEFAULT_WORKFLOW = "daily-sync.yml"
DEFAULT_BRANCH = "main"
DEFAULT_OUTPUT_DIR = Path("data")
ARTIFACT_TARGETS = {
    "sync-state": Path("state.json"),
    "run-log": Path("run-log.json"),
    "generated-markdown": Path("markdown"),
}
REQUIRED_ARTIFACTS = {"run-log", "generated-markdown"}


def _run_git_remote() -> str:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def infer_repo(remote_url: str | None = None) -> str:
    remote = remote_url or _run_git_remote()
    patterns = [
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
        r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
    ]

    for pattern in patterns:
        match = re.search(pattern, remote)
        if match:
            return f"{match.group('owner')}/{match.group('repo')}"

    raise ValueError(f"Could not infer GitHub repo from origin remote: {remote}")


def github_request(url: str, token: str | None = None) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "kb-harvest-artifact-fetcher",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {detail}") from exc

    if "application/json" in content_type:
        return json.loads(data.decode("utf-8"))
    return data


def resolve_github_token() -> str | None:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        return token

    if shutil.which("gh") is None:
        return None

    result = subprocess.run(
        ["gh", "auth", "token"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def successful_runs(repo: str, workflow: str, branch: str, token: str | None) -> list[dict[str, Any]]:
    url = (
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs"
        f"?branch={branch}&status=success&per_page=20"
    )
    payload = github_request(url, token)
    runs = payload.get("workflow_runs", [])
    if not runs:
        raise RuntimeError(f"No successful runs found for {workflow} on branch {branch}.")
    return runs


def list_run_artifacts(repo: str, run_id: int, token: str | None) -> dict[str, dict[str, Any]]:
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    payload = github_request(url, token)
    artifacts = {}
    for artifact in payload.get("artifacts", []):
        if not artifact.get("expired"):
            artifacts[artifact["name"]] = artifact
    return artifacts


def download_artifact(repo: str, artifact_id: int, token: str | None, destination: Path) -> None:
    url = f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip"
    data = github_request(url, token)
    destination.write_bytes(data)


def _extract_single_file(zip_path: Path, output_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        file_names = [name for name in archive.namelist() if not name.endswith("/")]
        if not file_names:
            raise RuntimeError(f"{zip_path.name} did not contain a file.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(file_names[0]) as source, output_path.open("wb") as target:
            shutil.copyfileobj(source, target)


def _extract_markdown(zip_path: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.endswith("/") or not name.endswith(".md"):
                continue
            target = output_dir / Path(name).name
            with archive.open(name) as source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)
            count += 1

    return count


def _frontmatter_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*[\"']?(.*?)[\"']?\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _article_id_from_url(url: str) -> str:
    match = re.search(r"/articles/(\d+)", url)
    return match.group(1) if match else ""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_minimal_state(output_dir: Path) -> Path:
    run_log_path = output_dir / "run-log.json"
    markdown_dir = output_dir / "markdown"
    state_path = output_dir / "state.json"

    run_log = json.loads(run_log_path.read_text(encoding="utf-8")) if run_log_path.exists() else {}
    state: dict[str, Any] = {
        "articles": {},
        "gemini": {
            "file_search_store_name": run_log.get("gemini_file_search_store_name", ""),
        },
    }

    if markdown_dir.exists():
        for path in sorted(markdown_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            url = _frontmatter_value(text, "article_url")
            article_id = _article_id_from_url(url) or path.stem
            state["articles"][article_id] = {
                "slug": path.stem,
                "title": _frontmatter_value(text, "title"),
                "url": url,
                "updated_at": _frontmatter_value(text, "updated_at"),
                "hash": _sha256_text(text),
                "markdown_path": str(path),
                "gemini_document_name": "",
            }

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return state_path


def find_latest_run_with_required_artifacts(
    repo: str,
    workflow: str,
    branch: str,
    token: str | None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    skipped_runs: list[str] = []

    for run in successful_runs(repo, workflow, branch, token):
        run_id = int(run["id"])
        artifacts = list_run_artifacts(repo, run_id, token)
        missing = sorted(REQUIRED_ARTIFACTS - set(artifacts))
        if not missing:
            return run, artifacts, skipped_runs
        skipped_runs.append(f"{run_id} missing {', '.join(missing)}")

    detail = "; ".join(skipped_runs) or "no artifact details available"
    raise RuntimeError(f"No successful run with required artifacts found. Checked: {detail}")


def extract_artifact(artifact_name: str, zip_path: Path, output_dir: Path) -> str:
    target = ARTIFACT_TARGETS[artifact_name]
    if artifact_name == "generated-markdown":
        count = _extract_markdown(zip_path, output_dir / target)
        return f"{count} Markdown files"

    output_path = output_dir / target
    _extract_single_file(zip_path, output_path)
    return str(output_path)


def fetch_artifacts(
    repo: str,
    workflow: str,
    branch: str,
    output_dir: Path,
    token: str | None,
) -> dict[str, Any]:
    run, artifacts, skipped_runs = find_latest_run_with_required_artifacts(
        repo=repo,
        workflow=workflow,
        branch=branch,
        token=token,
    )
    run_id = int(run["id"])

    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: dict[str, Any] = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        for artifact_name in ARTIFACT_TARGETS:
            if artifact_name not in artifacts:
                extracted[artifact_name] = (
                    "missing; rebuilt locally" if artifact_name == "sync-state" else "missing"
                )
                continue

            zip_path = temp_path / f"{artifact_name}.zip"
            download_artifact(repo, int(artifacts[artifact_name]["id"]), token, zip_path)
            extracted[artifact_name] = extract_artifact(artifact_name, zip_path, output_dir)

    if "sync-state" not in artifacts:
        extracted["sync-state"] = f"rebuilt minimal {build_minimal_state(output_dir)}"

    return {
        "repo": repo,
        "workflow": workflow,
        "branch": branch,
        "run_id": run_id,
        "run_url": run["html_url"],
        "output_dir": str(output_dir),
        "extracted": extracted,
        "skipped_runs": skipped_runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download latest Daily Knowledge Sync artifacts into local data/."
    )
    parser.add_argument("--repo", default="", help="GitHub repo in owner/name format.")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    token = resolve_github_token()
    repo = args.repo or infer_repo()

    try:
        result = fetch_artifacts(
            repo=repo,
            workflow=args.workflow,
            branch=args.branch,
            output_dir=Path(args.output_dir),
            token=token,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}")
        print("If the GitHub API rejects artifact download, set GH_TOKEN or GITHUB_TOKEN.")
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
