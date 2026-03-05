# first-look

**AI tries new tools so you don't have to.**

first-look monitors Hacker News for new GitHub projects, installs them in a Docker sandbox, actually uses them, and generates honest reports — install guide, usage experience, pros/cons, and a 1-5 rating.

## Example Report

See [reports/httpie-cli.md](reports/httpie-cli.md) for a real output — HTTPie got 3/5 after 5 usage tests revealed a stdin detection gotcha you won't find in the README.

Browse all reports: **[first-look report gallery](https://yaowubarbara.github.io/first-look/)**

## How is this different?

| | first-look | "Ask ChatGPT" | Awesome lists |
|---|---|---|---|
| Actually installs the tool? | Yes (Docker sandbox) | No | No |
| Runs real usage commands? | Yes | No | No |
| Reports real errors? | Yes (stdout/stderr) | Hallucinates | No |
| Updated automatically? | Yes (HN monitoring) | No | Manually curated |

first-look is **not** another LLM wrapper that summarizes READMEs. It generates commands, executes them in a sandbox, and reports on real results. When it says "3 out of 5 commands failed", those commands actually ran.

## How It Works

```
HN Monitor → GitHub Analysis → LLM generates install commands
    → Docker sandbox executes them → LLM generates usage commands
    → Docker runs usage tests → LLM writes experience review
    → Report saved to reports/ + static website
```

Each tool is tested in a clean Ubuntu 22.04 Docker container with memory limits, no root access, and automatic cleanup.

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (running and accessible)
- An OpenAI API key (or any OpenAI-compatible endpoint)

### Setup

```bash
git clone https://github.com/yaowubarbara/first-look.git
cd first-look
pip install -e .
```

### Configure

```bash
# Option A: Use OpenAI directly
export OPENAI_API_KEY="sk-..."

# Option B: Use any OpenAI-compatible endpoint (Ollama, LiteLLM, vLLM, etc.)
export LLM_API_URL="http://localhost:11434/v1/chat/completions"
export LLM_MODEL="llama3"

# Optional: GitHub token (increases API rate limit from 60 to 5000 req/hr)
export GITHUB_TOKEN="ghp_..."
```

### Run

```bash
# Test a specific repo
python main.py test httpie/cli

# Scan HN for new tools and test them
python main.py scan

# Continuous monitoring (polls HN every 5 minutes)
python main.py monitor

# Generate static website from reports
python main.py site
```

## Project Structure

```
first-look/
├── main.py              # CLI entry point
├── pyproject.toml       # Package config
├── config.yaml          # HN filters, environment settings
├── src/
│   ├── monitor.py       # HN Firebase API polling
│   ├── analyzer.py      # GitHub repo metadata + file detection
│   ├── agent.py         # LLM API calls (install/usage/review)
│   ├── installer.py     # Docker sandbox execution
│   ├── pipeline.py      # Orchestrator
│   ├── reporter.py      # Markdown report generation
│   └── site.py          # Static site generator
├── environments/
│   └── ubuntu-22.04/
│       └── Dockerfile   # Sandbox image
├── reports/             # Generated markdown reports
├── docs/                # Generated website (GitHub Pages)
└── tests/               # Test suite
```

## Security

- Docker containers with resource limits (`--memory=1g`, `--cpus=1`, `--pids-limit=256`)
- No root/sudo access inside containers
- Command blocklist prevents destructive operations (`rm -rf`, `curl|bash`, `mkfs`, etc.)
- Containers destroyed after each test
- LLM-generated commands are validated before execution

## Known Limitations

- Only tests on Ubuntu 22.04 (more environments planned)
- LLM may occasionally generate incorrect install commands
- Tools requiring GUI, API keys, or external services may not test well
- Report "experience" section is AI-generated based on command output, not human experience

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

## License

MIT

---

*Reports are AI-generated based on real command execution in Docker sandboxes. Your experience may differ.*
