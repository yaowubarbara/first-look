"""
HN Monitor - watches Hacker News for new tool/project launches.
Uses the official HN Firebase API (no auth needed).
"""

import os
import re
import time
import json
import urllib.request
from dataclasses import dataclass, asdict
from typing import Optional


HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/newstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"


@dataclass
class HNPost:
    id: int
    title: str
    url: Optional[str]
    score: int
    time: int
    github_url: Optional[str] = None
    repo_owner: Optional[str] = None
    repo_name: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "first-look/0.1"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def extract_github_info(url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract owner/repo from a GitHub URL."""
    if not url:
        return None, None, None
    match = re.match(r"https?://github\.com/([^/]+)/([^/?\#]+)", url)
    if match:
        owner, repo = match.group(1), match.group(2)
        github_url = f"https://github.com/{owner}/{repo}"
        return github_url, owner, repo
    return None, None, None


def fetch_post(item_id: int) -> Optional[HNPost]:
    """Fetch a single HN post by ID."""
    try:
        data = fetch_json(HN_ITEM_URL.format(item_id))
        if not data or data.get("type") != "story":
            return None
        url = data.get("url", "")
        github_url, owner, repo = extract_github_info(url)
        return HNPost(
            id=data["id"],
            title=data.get("title", ""),
            url=url,
            score=data.get("score", 0),
            time=data.get("time", 0),
            github_url=github_url,
            repo_owner=owner,
            repo_name=repo,
        )
    except Exception as e:
        print(f"[monitor] Error fetching item {item_id}: {e}")
        return None


def scan_new_stories(min_score: int = 5, max_age_hours: int = 24, limit: int = 100) -> list[HNPost]:
    """Scan recent HN stories for GitHub project links."""
    cutoff = int(time.time()) - (max_age_hours * 3600)
    story_ids = fetch_json(HN_TOP_URL)[:limit]

    results = []
    for sid in story_ids:
        post = fetch_post(sid)
        if not post:
            continue
        if post.time < cutoff:
            continue
        if post.github_url and post.score >= min_score:
            results.append(post)

    results.sort(key=lambda p: p.score, reverse=True)
    return results


SEEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".seen_posts.json")


def _load_seen() -> set:
    """Load previously seen post IDs from disk."""
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save_seen(seen: set):
    """Save seen post IDs to disk."""
    with open(SEEN_FILE, "w") as f:
        # Keep only the last 5000 IDs to prevent unbounded growth
        recent = sorted(seen)[-5000:]
        json.dump(recent, f)


def poll_loop(callback, interval=300, min_score=5, max_age_hours=24):
    """Continuously poll HN and call callback with new GitHub posts."""
    seen = _load_seen()
    print(f"[monitor] Starting HN poll loop (interval={interval}s, min_score={min_score})")
    print(f"[monitor] Loaded {len(seen)} previously seen posts")
    while True:
        try:
            posts = scan_new_stories(min_score=min_score, max_age_hours=max_age_hours)
            for post in posts:
                if post.id not in seen:
                    seen.add(post.id)
                    _save_seen(seen)
                    print(f"[monitor] New: {post.title} ({post.github_url}) score={post.score}")
                    callback(post)
        except Exception as e:
            print(f"[monitor] Poll error: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    # Quick test: scan and print
    posts = scan_new_stories(min_score=1, max_age_hours=48)
    print(f"Found {len(posts)} GitHub posts on HN:")
    for p in posts:
        print(f"  [{p.score}] {p.title}")
        print(f"       {p.github_url}")
