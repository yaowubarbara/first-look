"""
GitHub Repo Analyzer - fetches and analyzes repo info before testing.
"""

import json
import os
import base64
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RepoInfo:
    owner: str
    name: str
    description: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    readme: str = ""
    has_dockerfile: bool = False
    has_requirements: bool = False
    has_package_json: bool = False
    has_setup_py: bool = False
    has_cargo_toml: bool = False
    has_go_mod: bool = False
    has_makefile: bool = False
    topics: list[str] = field(default_factory=list)
    install_type: str = "unknown"  # pip, npm, cargo, go, make, docker, manual


GITHUB_API = "https://api.github.com"


def _get_headers() -> dict:
    """Build request headers, including auth token if available."""
    headers = {
        "User-Agent": "first-look/0.1",
        "Accept": "application/vnd.github.v3+json",
    }
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _check_rate_limit(resp):
    """Check GitHub API rate limit headers and warn if low."""
    remaining = resp.headers.get("X-RateLimit-Remaining")
    if remaining is not None and int(remaining) < 10:
        reset_time = resp.headers.get("X-RateLimit-Reset", "0")
        wait_secs = max(0, int(reset_time) - int(time.time()))
        print(f"  [!] GitHub API rate limit low: {remaining} remaining, resets in {wait_secs}s")
        if int(remaining) == 0:
            print(f"  [!] Rate limited. Sleeping {wait_secs}s...")
            time.sleep(min(wait_secs + 1, 60))


def _fetch(url: str, retries: int = 2) -> dict:
    """Fetch JSON from GitHub API with auth, rate limit handling, and retry."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=_get_headers())
            with urllib.request.urlopen(req, timeout=15) as resp:
                _check_rate_limit(resp)
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 403 and "rate limit" in str(e.read()).lower():
                reset = e.headers.get("X-RateLimit-Reset", "0")
                wait = max(0, int(reset) - int(time.time())) + 1
                print(f"  [!] Rate limited (403). Waiting {min(wait, 60)}s...")
                time.sleep(min(wait, 60))
                continue
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise
        except Exception:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise


def _fetch_readme(owner: str, name: str) -> str:
    """Fetch README content (decoded from base64)."""
    try:
        data = _fetch(f"{GITHUB_API}/repos/{owner}/{name}/readme")
        content = data.get("content", "")
        return base64.b64decode(content).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _detect_install_type(info: RepoInfo) -> str:
    """Guess how this project should be installed."""
    if info.has_dockerfile:
        return "docker"
    if info.has_cargo_toml:
        return "cargo"
    if info.has_go_mod:
        return "go"
    if info.has_package_json:
        return "npm"
    if info.has_setup_py or info.has_requirements:
        return "pip"
    if info.has_makefile:
        return "make"
    return "manual"


def analyze_repo(owner: str, name: str) -> RepoInfo:
    """Fetch repo metadata and README, detect project type."""
    repo_data = _fetch(f"{GITHUB_API}/repos/{owner}/{name}")

    info = RepoInfo(
        owner=owner,
        name=name,
        description=repo_data.get("description", ""),
        language=repo_data.get("language", ""),
        stars=repo_data.get("stargazers_count", 0),
        topics=repo_data.get("topics", []),
    )

    # Fetch README
    info.readme = _fetch_readme(owner, name)

    # Check root files to detect project type
    try:
        tree = _fetch(f"{GITHUB_API}/repos/{owner}/{name}/contents/")
        filenames = {item["name"].lower() for item in tree if item["type"] == "file"}

        info.has_dockerfile = "dockerfile" in filenames
        info.has_requirements = "requirements.txt" in filenames
        info.has_package_json = "package.json" in filenames
        info.has_setup_py = "setup.py" in filenames or "pyproject.toml" in filenames
        info.has_cargo_toml = "cargo.toml" in filenames
        info.has_go_mod = "go.mod" in filenames
        info.has_makefile = "makefile" in filenames
    except Exception:
        pass

    info.install_type = _detect_install_type(info)
    return info


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python analyzer.py <owner> <repo>")
        sys.exit(1)
    info = analyze_repo(sys.argv[1], sys.argv[2])
    print(f"Repo: {info.owner}/{info.name}")
    print(f"Language: {info.language} | Stars: {info.stars}")
    print(f"Install type: {info.install_type}")
    print(f"README length: {len(info.readme)} chars")
    print(f"Topics: {', '.join(info.topics)}")
