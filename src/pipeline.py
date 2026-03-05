"""
Pipeline - the main orchestrator that ties everything together.
Monitor HN -> Analyze repo -> Install in sandbox -> Generate report.
"""

import os
import sys
import yaml
from typing import Optional

from .monitor import HNPost, scan_new_stories
from .analyzer import analyze_repo
from .installer import build_environment, test_install
from .agent import generate_install_commands, generate_usage_commands, write_experience_review, analyze_results
from .reporter import generate_report, generate_tweet
from .site import build_site


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def process_repo(owner: str, name: str, hn_post: Optional[HNPost] = None,
                 config: Optional[dict] = None) -> dict:
    """Full pipeline for a single repo: analyze -> install -> report."""
    config = config or load_config()
    api_key = os.environ.get("LLM_API_KEY", "")

    print(f"\n{'='*60}")
    print(f"Processing: {owner}/{name}")
    print(f"{'='*60}")

    # Step 1: Analyze the repo
    print("[1/5] Analyzing repository...")
    repo_info = analyze_repo(owner, name)
    print(f"  Language: {repo_info.language} | Stars: {repo_info.stars}")
    print(f"  Install type: {repo_info.install_type}")
    print(f"  README: {len(repo_info.readme)} chars")

    if not repo_info.readme:
        print("  [!] No README found, skipping.")
        return {"status": "skipped", "reason": "no readme"}

    # Step 2: Generate install commands via LLM
    print("[2/5] Generating install commands...")
    env_config = config.get("environments", [{}])[0]
    env_name = env_config.get("name", "ubuntu-22.04")

    commands = generate_install_commands(
        readme=repo_info.readme,
        language=repo_info.language or "unknown",
        install_type=repo_info.install_type,
        environment=env_name,
        api_key=api_key,
    )
    print(f"  Install commands: {len(commands.get('install_commands', []))}")
    print(f"  Test commands: {len(commands.get('test_commands', []))}")
    print(f"  What it does: {commands.get('what_it_does', 'unknown')}")
    for cmd in commands.get("install_commands", []):
        print(f"    $ {cmd}")

    # Step 3: Run installation in Docker
    print(f"[3/5] Testing installation in {env_name}...")
    dockerfile = env_config.get("dockerfile", f"environments/{env_name}/Dockerfile")
    timeout = env_config.get("timeout", 300)

    image_tag = build_environment(env_name, dockerfile)
    install_result = test_install(
        env_name=env_name,
        image_tag=image_tag,
        repo_url=f"https://github.com/{owner}/{name}",
        install_commands=commands.get("install_commands", []),
        test_commands=commands.get("test_commands", []),
        timeout=timeout,
    )
    print(f"  Result: {'SUCCESS' if install_result.success else 'FAILED'}")
    print(f"  Duration: {install_result.total_duration}s")

    # Step 4: Actually USE the tool
    print("[4/5] Testing actual usage...")
    experience = {}
    if install_result.success:
        try:
            usage_cmds = generate_usage_commands(
                readme=repo_info.readme,
                what_it_does=commands.get("what_it_does", ""),
                language=repo_info.language or "unknown",
                api_key=api_key,
            )
            print(f"  Usage commands: {len(usage_cmds)}")
            for uc in usage_cmds:
                print(f"    $ {uc['command'][:70]}  # {uc['description'][:40]}")

            # Run usage commands in Docker (reuse same image)
            from .installer import run_in_container
            usage_shell_cmds = [
                f"export PATH=\"$HOME/.local/bin:$PATH\" && cd /home/tester/project && {uc['command']}"
                for uc in usage_cmds
            ]
            # Need to reinstall first, then run usage
            reinstall_cmds = [
                f"git clone https://github.com/{owner}/{name} /home/tester/project",
            ] + [
                f"cd /home/tester/project && {cmd}" for cmd in commands.get("install_commands", [])
            ] + usage_shell_cmds

            usage_steps = run_in_container(image_tag, reinstall_cmds, timeout=timeout)

            # Extract just the usage step results (skip reinstall steps)
            install_count = 1 + len(commands.get("install_commands", []))
            usage_step_results = usage_steps[install_count:]

            usage_results = []
            for i, step in enumerate(usage_step_results):
                desc = usage_cmds[i]["description"] if i < len(usage_cmds) else ""
                usage_results.append({
                    "command": step.command,
                    "description": desc,
                    "exit_code": step.exit_code,
                    "stdout": step.stdout,
                    "stderr": step.stderr,
                })
                status = "OK" if step.exit_code == 0 else "FAIL"
                print(f"    [{status}] {desc}")

            experience = write_experience_review(
                repo_name=f"{owner}/{name}",
                what_it_does=commands.get("what_it_does", ""),
                readme=repo_info.readme,
                usage_results=usage_results,
                install_verdict="success" if install_result.success else "failed",
                api_key=api_key,
            )
            print(f"  Rating: {experience.get('rating', '?')}/5")
            print(f"  Would use: {experience.get('would_i_use_it', '?')}")
        except Exception as e:
            print(f"  [!] Usage test failed: {e}")
    else:
        print("  Skipped (installation failed)")

    # Step 5: Analyze and generate report
    print("[5/5] Generating report...")
    analysis = analyze_results(
        repo_name=f"{owner}/{name}",
        steps=install_result.steps,
        environment=env_name,
        success=install_result.success,
        api_key=api_key,
    )

    report_path = generate_report(
        repo_owner=owner,
        repo_name=name,
        repo_description=repo_info.description or "",
        stars=repo_info.stars,
        language=repo_info.language or "unknown",
        hn_title=hn_post.title if hn_post else "",
        hn_score=hn_post.score if hn_post else 0,
        install_results=[install_result],
        analysis=analysis,
        experience=experience,
        output_dir=config.get("output", {}).get("reports_dir", "reports"),
    )

    tweet = generate_tweet(
        repo_owner=owner,
        repo_name=name,
        verdict=analysis.get("verdict", "unknown"),
        difficulty=analysis.get("install_difficulty", "unknown"),
        summary=analysis.get("summary", ""),
    )

    # Rebuild static site
    build_site()

    print(f"\n  Report: {report_path}")
    print(f"\n  Draft tweet:\n  {tweet}")

    return {
        "status": "done",
        "repo": f"{owner}/{name}",
        "success": install_result.success,
        "verdict": analysis.get("verdict"),
        "report": report_path,
        "tweet": tweet,
    }


def run_scan(config: Optional[dict] = None):
    """Scan HN for new tools and process each one."""
    config = config or load_config()
    hn_config = config.get("hn", {})

    print("Scanning Hacker News for new tools...")
    posts = scan_new_stories(
        min_score=hn_config.get("min_score", 5),
        max_age_hours=hn_config.get("max_age_hours", 24),
    )
    print(f"Found {len(posts)} GitHub projects on HN")

    results = []
    for post in posts[:5]:  # Process top 5 max per scan
        if post.repo_owner and post.repo_name:
            result = process_repo(
                owner=post.repo_owner,
                name=post.repo_name,
                hn_post=post,
                config=config,
            )
            results.append(result)

    return results
