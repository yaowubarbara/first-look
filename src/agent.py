"""
Agent - the AI brain that reads READMEs, generates install commands,
analyzes results, and writes reports.

Uses an OpenAI-compatible LLM API endpoint.
"""

import json
import os
import re
import urllib.request
from typing import Optional


# OpenAI-compatible LLM API endpoint
DEFAULT_PROXY_URL = "http://127.0.0.1:3456/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o"


def _call_llm(prompt: str, system: str = "", model: str = "",
              max_tokens: int = 4096, api_key: str = "",
              retries: int = 2) -> str:
    """Call LLM via OpenAI-compatible API endpoint."""
    proxy_url = os.environ.get("LLM_API_URL", DEFAULT_PROXY_URL)
    model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }).encode()

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                proxy_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except Exception:
            if attempt < retries:
                import time
                time.sleep(2 ** attempt)
                continue
            raise


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown wrapping and extra text."""
    text = text.strip()
    # Try to extract JSON from markdown code blocks
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find JSON object in the text
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")


SYSTEM_PROMPT = """You are an expert DevOps engineer and tool evaluator.
Your job is to analyze software projects and generate precise installation commands.
Be practical, concise, and focus on what actually works.
Always prefer the simplest installation method."""


def generate_install_commands(readme: str, language: str, install_type: str,
                              environment: str = "Ubuntu 22.04",
                              api_key: str = "") -> dict:
    """Read a README and generate installation commands for the given environment.

    Returns dict with:
      - install_commands: list of shell commands to install
      - test_commands: list of shell commands to verify it works
      - notes: any warnings or special considerations
    """
    prompt = f"""Analyze this README and generate installation commands for {environment}.

Project language: {language}
Detected install type: {install_type}

README:
---
{readme[:6000]}
---

Respond in JSON format ONLY (no markdown, no explanation):
{{
  "install_commands": ["cmd1", "cmd2", ...],
  "test_commands": ["cmd1", ...],
  "notes": "any warnings",
  "what_it_does": "one sentence description",
  "complexity": "simple|moderate|complex"
}}

Rules:
- Use the simplest installation method from the README
- If pip/npm install is available, prefer that over building from source
- Include dependency installation (apt-get) if needed
- test_commands should verify the tool actually works (--version, --help, or a basic operation)
- Maximum 8 install commands, 3 test commands
- Commands must work on {environment} with bash
- NEVER use sudo — the container runs as a non-root user without sudo access"""

    response = _call_llm(prompt, system=SYSTEM_PROMPT, api_key=api_key)
    return _parse_json_response(response)


def generate_usage_commands(readme: str, what_it_does: str, language: str,
                            api_key: str = "") -> list:
    """Generate commands to actually USE the tool (not just install it)."""
    prompt = f"""You installed a tool. Now generate 3-5 shell commands that ACTUALLY USE it
to demonstrate what it does. Not --version or --help, but real usage.

Tool description: {what_it_does}
Language: {language}

README excerpt:
---
{readme[:4000]}
---

Respond in JSON format ONLY:
{{
  "usage_commands": [
    {{"command": "the shell command", "description": "what this demonstrates"}}
  ]
}}

Rules:
- Show the tool doing its PRIMARY job (not just confirming it's installed)
- Use simple, safe examples (public URLs, sample data, etc.)
- Each command should produce visible, interesting output
- If it's a CLI tool, show actual usage. If it's a library, write a small inline script.
- Maximum 5 commands
- Commands must be non-destructive and safe to run in a sandbox
- NEVER use sudo"""

    response = _call_llm(prompt, system=SYSTEM_PROMPT, api_key=api_key)
    return _parse_json_response(response).get("usage_commands", [])


def write_experience_review(repo_name: str, what_it_does: str, readme: str,
                            usage_results: list, install_verdict: str,
                            api_key: str = "") -> dict:
    """Write a human-like experience review based on actual usage results."""
    usage_summary = []
    for r in usage_results:
        status = "worked" if r["exit_code"] == 0 else "failed"
        entry = f"Command: {r['command']}\n  Purpose: {r['description']}\n  Status: {status}"
        if r["exit_code"] == 0 and r.get("stdout"):
            entry += f"\n  Output preview: {r['stdout'][:300]}"
        if r["exit_code"] != 0 and r.get("stderr"):
            entry += f"\n  Error: {r['stderr'][:200]}"
        usage_summary.append(entry)

    prompt = f"""You just installed and tried "{repo_name}". Write an honest, practical review
as if you're a developer telling a friend about it over coffee.

Tool: {repo_name}
What it does: {what_it_does}
Install verdict: {install_verdict}

Usage test results:
{chr(10).join(usage_summary)}

README excerpt (for context):
{readme[:2000]}

Write a JSON response:
{{
  "first_impression": "1-2 sentences, your gut reaction",
  "what_i_tried": ["describe each thing you tried and what happened"],
  "pros": ["genuine strengths you noticed"],
  "cons": ["honest criticisms or limitations"],
  "who_is_this_for": "one sentence about the target user",
  "would_i_use_it": "yes/maybe/no + brief reason",
  "experience_summary": "3-4 sentence review a busy developer would actually read",
  "rating": "1-5 (1=waste of time, 3=decent, 5=must-have)"
}}

Rules:
- Be HONEST. If it didn't work well, say so.
- Be specific. Don't say "it's great", say WHY.
- Write like a real developer, not a marketing brochure.
- Base your review on what actually happened in the usage tests."""

    response = _call_llm(prompt, system=SYSTEM_PROMPT, api_key=api_key)
    return _parse_json_response(response)


def analyze_results(repo_name: str, steps: list, environment: str,
                    success: bool, api_key: str = "") -> dict:
    """Analyze installation results and generate a structured report."""
    steps_summary = []
    for s in steps:
        status = "SUCCESS" if s.exit_code == 0 else f"FAILED (exit={s.exit_code})"
        entry = f"$ {s.command}\n  Status: {status} ({s.duration}s)"
        if s.exit_code != 0 and s.stderr:
            entry += f"\n  Error: {s.stderr[:300]}"
        steps_summary.append(entry)

    prompt = f"""Analyze this installation test result and write a concise report.

Tool: {repo_name}
Environment: {environment}
Overall result: {"SUCCESS" if success else "FAILED"}

Steps:
{chr(10).join(steps_summary)}

Write a JSON report:
{{
  "verdict": "works|works_with_issues|broken",
  "install_difficulty": "easy|moderate|hard",
  "time_estimate": "how long a human would spend",
  "what_went_well": ["..."],
  "issues": ["..."],
  "tips": ["specific tips for this environment"],
  "step_by_step_guide": ["human-readable step 1", "step 2", ...],
  "summary": "2-3 sentence summary for a busy developer"
}}"""

    response = _call_llm(prompt, system=SYSTEM_PROMPT, api_key=api_key)
    return _parse_json_response(response)
