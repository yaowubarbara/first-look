#!/usr/bin/env python3
"""
first-look: AI tries new tools so you don't have to.

Usage:
    python main.py scan              # Scan HN and test new tools
    python main.py test owner/repo   # Test a specific GitHub repo
    python main.py monitor           # Continuous monitoring mode
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.pipeline import process_repo, run_scan, load_config
from src.monitor import poll_loop


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "scan":
        results = run_scan()
        print(f"\nDone. Processed {len(results)} tools.")
        for r in results:
            print(f"  {r['repo']}: {r.get('verdict', 'unknown')}")

    elif cmd == "test":
        if len(sys.argv) < 3:
            print("Usage: python main.py test owner/repo")
            sys.exit(1)
        parts = sys.argv[2].split("/")
        if len(parts) != 2:
            print("Format: owner/repo (e.g. httpie/cli)")
            sys.exit(1)
        config = load_config()
        result = process_repo(parts[0], parts[1], config=config)
        print(f"\nResult: {result.get('verdict', 'unknown')}")

    elif cmd == "monitor":
        config = load_config()
        hn_config = config.get("hn", {})

        def on_new_post(post):
            if post.repo_owner and post.repo_name:
                try:
                    process_repo(post.repo_owner, post.repo_name,
                                 hn_post=post, config=config)
                except Exception as e:
                    print(f"[error] Failed to process {post.repo_owner}/{post.repo_name}: {e}")

        poll_loop(
            callback=on_new_post,
            interval=hn_config.get("poll_interval", 300),
            min_score=hn_config.get("min_score", 5),
            max_age_hours=hn_config.get("max_age_hours", 24),
        )

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
