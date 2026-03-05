# first-look

**AI tries new tools so you don't have to.**

first-look monitors Hacker News for new GitHub projects, installs them in a Docker sandbox, actually uses them, and generates honest reports — install guide, usage experience, pros/cons, and a 1-5 rating.

## Example Report

See [reports/httpie-cli.md](reports/httpie-cli.md) for a real output — a full review of HTTPie including installation steps, 5 usage tests, and a 3/5 rating.

## How It Works

```
HN Monitor → GitHub Analysis → LLM generates install commands
    → Docker sandbox executes them → LLM generates usage commands
    → Docker runs usage tests → LLM writes experience review
    → Markdown report saved to reports/
```

Each tool is tested in a clean Ubuntu 22.04 Docker container with memory limits, no root access, and automatic cleanup. The AI doesn't just summarize the README — it actually runs the commands and reports what happened.

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (running and accessible)
- Access to an OpenAI-compatible LLM API endpoint

### Setup

```bash
git clone https://github.com/yaowubarbara/first-look.git
cd first-look
pip install -r requirements.txt
```

### Configure

Set environment variables:

```bash
# Required: OpenAI-compatible LLM API endpoint
export LLM_API_URL="http://127.0.0.1:3456/v1/chat/completions"
export LLM_MODEL="openai/gpt-4o"  # or any OpenAI-compatible model

# Optional: GitHub token (increases API rate limit from 60 to 5000 req/hr)
export GITHUB_TOKEN="ghp_your_token_here"
```

### Run

```bash
# Test a specific repo
python main.py test httpie/cli

# Scan HN for new tools and test them
python main.py scan

# Continuous monitoring (polls HN every 5 minutes)
python main.py monitor
```

Reports are saved to the `reports/` directory as markdown files.

## Project Structure

```
first-look/
├── main.py              # CLI entry point
├── config.yaml          # Configuration (environments, HN filters)
├── requirements.txt     # Python dependencies (just pyyaml)
├── src/
│   ├── monitor.py       # HN Firebase API polling
│   ├── analyzer.py      # GitHub repo metadata + file detection
│   ├── agent.py         # LLM API calls (install/usage/review generation)
│   ├── installer.py     # Docker sandbox execution
│   ├── pipeline.py      # Orchestrator (ties everything together)
│   └── reporter.py      # Markdown report generation
├── environments/
│   └── ubuntu-22.04/
│       └── Dockerfile   # Sandbox environment
└── reports/             # Generated reports
```

## Security

- Tests run in Docker containers with resource limits (`--memory=1g`, `--cpus=1`, `--pids-limit=256`)
- Process count limited (`--pids-limit=256`) to prevent fork bombs
- No sudo access inside containers
- Basic command blocklist prevents obviously destructive operations
- Containers are automatically removed after each test

## License

MIT

---

*Generated reports are AI-produced based on automated testing. Your experience may differ depending on your environment.*
