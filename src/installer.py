"""
Installer - runs installation in a Docker sandbox and captures results.
Each environment is an isolated Docker container.
"""

import subprocess
import time
import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StepResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration: float  # seconds


@dataclass
class InstallResult:
    environment: str
    repo: str
    success: bool
    steps: list[StepResult] = field(default_factory=list)
    total_duration: float = 0.0
    error_summary: Optional[str] = None


IMAGE_TAG_PREFIX = "first-look-env"

# Commands that should never appear in generated install/usage commands
BLOCKED_PATTERNS = [
    "rm -rf /", "rm -rf ~", "rm -rf $HOME", "rm -rf *",
    "mkfs.", "dd if=", ":(){", "fork bomb",
    "chmod -R 777", "chmod 777 /",
    "> /dev/sda", "> /dev/",
    "shutdown", "reboot", "halt", "poweroff",
    "curl|bash", "curl|sh", "wget|bash", "wget|sh",
    "curl | bash", "curl | sh", "wget | bash", "wget | sh",
    "python -c \"import os;os.system",
    "nc -l", "ncat", "netcat",
    "nohup", "crontab",
]


def _is_command_safe(cmd: str) -> bool:
    """Basic safety check on commands before execution."""
    cmd_lower = cmd.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return False
    # Check for pipe-to-shell patterns (curl/wget ... | bash/sh)
    import re
    if re.search(r"(curl|wget)\s+.+\|\s*(bash|sh)", cmd_lower):
        return False
    return True


def build_environment(env_name: str, dockerfile_path: str) -> str:
    """Build a Docker image for the environment. Returns image tag."""
    tag = f"{IMAGE_TAG_PREFIX}:{env_name}"
    # Skip build if image already exists
    check = subprocess.run(
        ["docker", "image", "inspect", tag],
        capture_output=True, timeout=10,
    )
    if check.returncode == 0:
        print(f"  [docker] Image {tag} already exists, skipping build.")
        return tag
    if "/" in dockerfile_path:
        context_dir = dockerfile_path.rsplit("/", 1)[0]
        dockerfile_name = dockerfile_path.rsplit("/", 1)[1]
    else:
        context_dir = "."
        dockerfile_name = dockerfile_path
    result = subprocess.run(
        ["docker", "build", "-t", tag, "-f", dockerfile_name, "."],
        capture_output=True, text=True, timeout=300,
        cwd=context_dir,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to build {env_name}: {result.stderr}")
    return tag


def run_in_container(image_tag: str, commands: list[str], timeout: int = 300,
                     network: str = "bridge") -> list[StepResult]:
    """Run a sequence of commands in a fresh Docker container.

    Each command runs via `docker exec` so we capture per-step results.
    network: 'bridge' (default, has internet) or 'none' (no network access)
    """
    container_name = f"fl-test-{int(time.time())}"
    steps = []

    # Validate commands
    for cmd in commands:
        if not _is_command_safe(cmd):
            raise ValueError(f"Blocked unsafe command: {cmd[:80]}")

    # Start container in background
    run_result = subprocess.run(
        ["docker", "run", "-d", "--name", container_name,
         "--memory=1g", "--cpus=1",
         "--pids-limit=256",
         f"--network={network}",
         image_tag, "sleep", str(timeout)],
        capture_output=True, text=True, timeout=30,
    )

    if run_result.returncode != 0:
        raise RuntimeError(f"Failed to start container: {run_result.stderr}")

    try:
        for cmd in commands:
            start = time.time()
            result = subprocess.run(
                ["docker", "exec", container_name, "bash", "-c", cmd],
                capture_output=True, text=True,
                timeout=min(timeout, 120),
            )
            duration = time.time() - start

            steps.append(StepResult(
                command=cmd,
                exit_code=result.returncode,
                stdout=result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
                stderr=result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
                duration=round(duration, 2),
            ))

            # If a step fails, continue but record it
            if result.returncode != 0:
                print(f"  [!] Step failed (exit={result.returncode}): {cmd[:80]}")
    finally:
        # Always clean up
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True, timeout=10,
        )

    return steps


def test_install(env_name: str, image_tag: str, repo_url: str,
                 install_commands: list[str], test_commands: list[str],
                 timeout: int = 300) -> InstallResult:
    """Run a full install test: clone + install + basic test."""
    all_commands = [
        f"git clone {repo_url} /home/tester/project",
        "cd /home/tester/project && ls -la",
    ] + [
        f"cd /home/tester/project && {cmd}" for cmd in install_commands
    ] + [
        f"cd /home/tester/project && {cmd}" for cmd in test_commands
    ]

    start = time.time()
    steps = run_in_container(image_tag, all_commands, timeout=timeout)
    total_duration = round(time.time() - start, 2)

    # Determine overall success: all install steps passed
    install_step_count = 2 + len(install_commands)  # clone + ls + install cmds
    install_steps = steps[:install_step_count]
    success = all(s.exit_code == 0 for s in install_steps)

    error_summary = None
    if not success:
        failed = [s for s in install_steps if s.exit_code != 0]
        if failed:
            error_summary = f"Failed at: {failed[0].command}\nError: {failed[0].stderr[:500]}"

    return InstallResult(
        environment=env_name,
        repo=repo_url,
        success=success,
        steps=steps,
        total_duration=total_duration,
        error_summary=error_summary,
    )


if __name__ == "__main__":
    # Quick test with a known repo
    print("Building ubuntu-22.04 environment...")
    tag = build_environment("ubuntu-22.04", "environments/ubuntu-22.04/Dockerfile")
    print(f"Image built: {tag}")

    print("Testing installation of httpie...")
    result = test_install(
        env_name="ubuntu-22.04",
        image_tag=tag,
        repo_url="https://github.com/httpie/cli",
        install_commands=["pip3 install ."],
        test_commands=["http --version"],
    )
    print(f"Success: {result.success}")
    print(f"Duration: {result.total_duration}s")
    for step in result.steps:
        status = "OK" if step.exit_code == 0 else "FAIL"
        print(f"  [{status}] {step.command[:60]} ({step.duration}s)")
