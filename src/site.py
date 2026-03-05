"""
Static site generator - converts reports/*.md into a browsable HTML website.
Output goes to docs/ for GitHub Pages hosting.
"""

import os
import re
from datetime import datetime


REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")


def parse_report(filepath: str) -> dict:
    """Parse a markdown report into structured data."""
    with open(filepath) as f:
        content = f.read()

    data = {"filename": os.path.basename(filepath), "content": content}

    # Parse title
    m = re.search(r"^# First Look: (.+)$", content, re.MULTILINE)
    data["title"] = m.group(1) if m else os.path.basename(filepath).replace(".md", "")

    # Parse description
    m = re.search(r"^> (.+)$", content, re.MULTILINE)
    data["description"] = m.group(1) if m else ""

    # Parse table fields
    for field, key in [
        ("Tested", "tested"), ("Language", "language"), ("Stars", "stars"),
        ("Verdict", "verdict"), ("Install Difficulty", "difficulty"),
        ("Estimated Human Time", "time_est"), ("Source", "source"),
    ]:
        m = re.search(rf"\| {field} \| (.+?) \|", content)
        data[key] = m.group(1).strip() if m else ""

    # Parse rating
    m = re.search(r"\*\*Rating:\*\* (\d)/5", content)
    data["rating"] = int(m.group(1)) if m else 0

    # Parse summary section
    m = re.search(r"## Summary\n\n(.+?)(?=\n##)", content, re.DOTALL)
    data["summary"] = m.group(1).strip() if m else ""

    # Verdict badge
    verdict_raw = data.get("verdict", "")
    if "works_with_issues" in verdict_raw:
        data["verdict_class"] = "warn"
        data["verdict_label"] = "WORKS (ISSUES)"
    elif "works" in verdict_raw.lower() or "PASS" in verdict_raw:
        data["verdict_class"] = "pass"
        data["verdict_label"] = "WORKS"
    elif "broken" in verdict_raw.lower() or "FAIL" in verdict_raw:
        data["verdict_class"] = "fail"
        data["verdict_label"] = "BROKEN"
    else:
        data["verdict_class"] = "unknown"
        data["verdict_label"] = "UNKNOWN"

    # Stars as number
    try:
        data["stars_num"] = int(data.get("stars", "0").replace(",", ""))
    except ValueError:
        data["stars_num"] = 0

    return data


def md_to_html(md: str) -> str:
    """Simple markdown to HTML converter for report content."""
    html = md

    # Headers
    html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Blockquotes
    html = re.sub(r"^> (.+)$", r"<blockquote>\1</blockquote>", html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Code
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

    # Links
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)

    # Tables
    lines = html.split("\n")
    result = []
    in_table = False
    for line in lines:
        if line.startswith("|") and "|" in line[1:]:
            if line.startswith("|--") or line.startswith("| --"):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not in_table:
                result.append("<table>")
                in_table = True
            result.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        else:
            if in_table:
                result.append("</table>")
                in_table = False
            result.append(line)
    if in_table:
        result.append("</table>")
    html = "\n".join(result)

    # Lists
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"^(\d+)\. (.+)$", r"<li>\2</li>", html, flags=re.MULTILINE)

    # Wrap consecutive <li> in <ul>
    html = re.sub(r"((?:<li>.*?</li>\n?)+)", r"<ul>\1</ul>", html)

    # Paragraphs (lines that aren't already tagged)
    lines = html.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("<") and not stripped.startswith("---"):
            result.append(f"<p>{stripped}</p>")
        elif stripped == "---":
            result.append("<hr>")
        else:
            result.append(line)

    return "\n".join(result)


CSS = """
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --text-dim: #8b949e;
  --accent: #58a6ff;
  --green: #3fb950;
  --yellow: #d29922;
  --red: #f85149;
  --purple: #bc8cff;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  line-height: 1.6;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.header {
  text-align: center;
  padding: 48px 20px 32px;
  border-bottom: 1px solid var(--border);
}
.header h1 { font-size: 32px; margin-bottom: 8px; }
.header p { color: var(--text-dim); font-size: 18px; }

.stats {
  display: flex;
  justify-content: center;
  gap: 40px;
  padding: 20px;
  color: var(--text-dim);
  font-size: 14px;
}
.stats strong { color: var(--text); font-size: 20px; display: block; }

.filters {
  display: flex;
  justify-content: center;
  gap: 12px;
  padding: 16px 20px;
  flex-wrap: wrap;
}
.filter-btn {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-dim);
  padding: 6px 16px;
  border-radius: 20px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.filter-btn:hover, .filter-btn.active {
  background: var(--accent);
  color: var(--bg);
  border-color: var(--accent);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
  max-width: 1200px;
  margin: 24px auto;
  padding: 0 20px;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  transition: border-color 0.2s, transform 0.2s;
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  display: block;
}
.card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  text-decoration: none;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
.card-title { font-size: 18px; font-weight: 600; }
.badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 600;
  text-transform: uppercase;
}
.badge.pass { background: rgba(63,185,80,0.15); color: var(--green); }
.badge.warn { background: rgba(210,153,34,0.15); color: var(--yellow); }
.badge.fail { background: rgba(248,81,73,0.15); color: var(--red); }
.badge.unknown { background: rgba(139,148,158,0.15); color: var(--text-dim); }

.card-desc {
  color: var(--text-dim);
  font-size: 14px;
  margin-bottom: 16px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-dim);
  flex-wrap: wrap;
}
.card-meta span { display: flex; align-items: center; gap: 4px; }
.stars-display { color: var(--yellow); letter-spacing: 2px; font-size: 14px; }

/* Report page */
.report {
  max-width: 800px;
  margin: 0 auto;
  padding: 32px 20px;
}
.report .back { display: inline-block; margin-bottom: 24px; color: var(--text-dim); }
.report h1 { font-size: 28px; margin-bottom: 8px; }
.report h2 { font-size: 20px; margin: 32px 0 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
.report h3 { font-size: 16px; margin: 20px 0 8px; }
.report p { margin-bottom: 12px; }
.report blockquote {
  border-left: 3px solid var(--border);
  padding: 8px 16px;
  color: var(--text-dim);
  margin: 12px 0;
  font-style: italic;
}
.report table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}
.report td {
  padding: 8px 12px;
  border: 1px solid var(--border);
  font-size: 14px;
}
.report tr:nth-child(odd) { background: rgba(255,255,255,0.02); }
.report ul { margin: 8px 0 16px 20px; }
.report li { margin-bottom: 6px; font-size: 15px; }
.report code {
  background: rgba(255,255,255,0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}
.report strong { color: var(--accent); }
.report hr { border: none; border-top: 1px solid var(--border); margin: 32px 0; }

.footer {
  text-align: center;
  padding: 32px 20px;
  color: var(--text-dim);
  font-size: 13px;
  border-top: 1px solid var(--border);
}
"""


def render_stars(rating: int) -> str:
    return "★" * rating + "☆" * (5 - rating)


def generate_index(reports: list[dict]) -> str:
    """Generate the index page HTML."""
    # Stats
    total = len(reports)
    avg_rating = sum(r["rating"] for r in reports) / total if total else 0
    pass_count = sum(1 for r in reports if r["verdict_class"] == "pass")
    warn_count = sum(1 for r in reports if r["verdict_class"] == "warn")

    # Languages for filter
    languages = sorted(set(r["language"] for r in reports if r["language"]))

    cards_html = ""
    for r in sorted(reports, key=lambda x: x.get("rating", 0), reverse=True):
        slug = r["filename"].replace(".md", ".html")
        cards_html += f"""
    <a class="card" href="{slug}" data-lang="{r['language']}">
      <div class="card-header">
        <div class="card-title">{r['title']}</div>
        <span class="badge {r['verdict_class']}">{r['verdict_label']}</span>
      </div>
      <div class="card-desc">{r['summary'][:150]}</div>
      <div class="card-meta">
        <span class="stars-display">{render_stars(r['rating'])}</span>
        <span>{r['language']}</span>
        <span>{'⭐ ' + str(r['stars_num']) if r['stars_num'] else ''}</span>
        <span>{r['difficulty']}</span>
        <span>{r.get('tested', '')}</span>
      </div>
    </a>"""

    filter_buttons = '<button class="filter-btn active" onclick="filterLang(\'all\')">All</button>'
    for lang in languages:
        filter_buttons += f'<button class="filter-btn" onclick="filterLang(\'{lang}\')">{lang}</button>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>first-look — AI tries new tools so you don't have to</title>
<style>{CSS}</style>
</head>
<body>
  <div class="header">
    <h1>first-look</h1>
    <p>AI tries new tools so you don't have to</p>
  </div>

  <div class="stats">
    <div><strong>{total}</strong> tools tested</div>
    <div><strong>{avg_rating:.1f}</strong> avg rating</div>
    <div><strong>{pass_count + warn_count}</strong> installable</div>
  </div>

  <div class="filters">{filter_buttons}</div>

  <div class="grid" id="grid">{cards_html}
  </div>

  <div class="footer">
    <a href="https://github.com/yaowubarbara/first-look">GitHub</a> ·
    AI tries new tools so you don't have to
  </div>

  <script>
  function filterLang(lang) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('.card').forEach(c => {{
      c.style.display = (lang === 'all' || c.dataset.lang === lang) ? '' : 'none';
    }});
  }}
  </script>
</body>
</html>"""


def generate_report_page(report: dict) -> str:
    """Generate an individual report page."""
    content_html = md_to_html(report["content"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{report['title']} — first-look</title>
<style>{CSS}</style>
</head>
<body>
  <div class="report">
    <a class="back" href="index.html">← Back to all reports</a>
    {content_html}
  </div>
  <div class="footer">
    <a href="https://github.com/yaowubarbara/first-look">GitHub</a> ·
    AI tries new tools so you don't have to
  </div>
</body>
</html>"""


def build_site(reports_dir: str = None, output_dir: str = None):
    """Build the static site from all markdown reports."""
    reports_dir = reports_dir or REPORTS_DIR
    output_dir = output_dir or DOCS_DIR

    os.makedirs(output_dir, exist_ok=True)

    # Parse all reports
    reports = []
    for f in sorted(os.listdir(reports_dir)):
        if f.endswith(".md"):
            data = parse_report(os.path.join(reports_dir, f))
            reports.append(data)

    if not reports:
        print("[site] No reports found.")
        return

    # Generate index
    index_html = generate_index(reports)
    with open(os.path.join(output_dir, "index.html"), "w") as f:
        f.write(index_html)

    # Generate individual pages
    for r in reports:
        slug = r["filename"].replace(".md", ".html")
        page_html = generate_report_page(r)
        with open(os.path.join(output_dir, slug), "w") as f:
            f.write(page_html)

    print(f"[site] Built {len(reports)} report pages → {output_dir}/")


if __name__ == "__main__":
    build_site()
