from __future__ import annotations

import html
import json
import os
import urllib.request
from collections import Counter
from pathlib import Path

USER = os.environ["GITHUB_USER"]
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"
OUT = Path("assets/activity.svg")


def api(path: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    req = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def esc(value):
    return html.escape(str(value), quote=True)


profile = api(f"/users/{USER}")
repos = api(f"/users/{USER}/repos?per_page=100&sort=updated&type=owner")
events = api(f"/users/{USER}/events/public?per_page=30")

repos = [r for r in repos if not r.get("fork") and not r.get("archived")]
lang_bytes = Counter()

for repo in repos[:30]:
    try:
        langs = api(f"/repos/{USER}/{repo['name']}/languages")
        lang_bytes.update(langs)
    except Exception:
        pass

top_langs = lang_bytes.most_common(5)
total_lang = sum(v for _, v in top_langs) or 1
recent_repos = sorted(repos, key=lambda r: r.get("pushed_at") or "", reverse=True)[:4]


def event_line(e):
    kind = e.get("type", "")
    repo = e.get("repo", {}).get("name", "").split("/")[-1]
    payload = e.get("payload", {})

    if kind == "PushEvent":
        count = len(payload.get("commits", []))
        return f"push · {repo} · {count} commit{'s' if count != 1 else ''}"
    if kind == "PullRequestEvent":
        return f"pr {payload.get('action', '')} · {repo}"
    if kind == "IssuesEvent":
        return f"issue {payload.get('action', '')} · {repo}"
    if kind == "CreateEvent":
        return f"create {payload.get('ref_type', '')} · {repo}"
    if kind == "WatchEvent":
        return f"star · {repo}"
    if repo:
        return f"{kind.replace('Event', '').lower()} · {repo}"
    return kind.replace("Event", "").lower()


event_lines = []
seen = set()
for event in events:
    line = event_line(event)
    if line and line not in seen:
        event_lines.append(line)
        seen.add(line)
    if len(event_lines) == 4:
        break


def bar(x, y, width, pct, label, color):
    filled = max(4, int(width * pct))
    return f'''
    <text class="small" x="{x}" y="{y-7}">{esc(label)}</text>
    <rect x="{x}" y="{y}" width="{width}" height="8" rx="4" fill="#21262d"/>
    <rect x="{x}" y="{y}" width="{filled}" height="8" rx="4" fill="{color}"/>'''


palette = ["#a371f7", "#58a6ff", "#3fb950", "#d29922", "#f778ba"]

if top_langs:
    lang_svg = "".join(
        bar(585, 89 + i * 28, 420, value / total_lang, name, palette[i])
        for i, (name, value) in enumerate(top_langs)
    )
else:
    lang_svg = '<text class="small" x="585" y="105">No public repository language data yet.</text>'

if recent_repos:
    repo_svg = ""
    for i, repo in enumerate(recent_repos):
        desc = (repo.get("description") or "public repository").strip()
        if len(desc) > 58:
            desc = desc[:55] + "..."
        repo_svg += f'''
        <text class="repo" x="42" y="{104 + i * 30}">{esc(repo["name"])}</text>
        <text class="muted" x="230" y="{104 + i * 30}">{esc(desc)}</text>'''
else:
    repo_svg = '<text class="muted" x="42" y="104">No public repositories indexed yet.</text>'

if event_lines:
    events_svg = "".join(
        f'<text class="muted" x="42" y="{214 + i * 22}">{esc(line)}</text>'
        for i, line in enumerate(event_lines[:3])
    )
else:
    events_svg = '<text class="muted" x="42" y="214">No recent public events.</text>'

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="300" viewBox="0 0 1100 300" role="img" aria-labelledby="title desc">
<title id="title">{esc(USER)} public GitHub activity</title>
<desc id="desc">Automatically generated from public GitHub API data.</desc>
<style>
.bg{{fill:#0d1117}}
.label{{fill:#8b949e;font:600 11px ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:1.6px}}
.h{{fill:#f0f6fc;font:600 18px ui-monospace,SFMono-Regular,Consolas,monospace}}
.repo{{fill:#c9d1d9;font:600 13px ui-monospace,SFMono-Regular,Consolas,monospace}}
.muted{{fill:#8b949e;font:12px ui-monospace,SFMono-Regular,Consolas,monospace}}
.small{{fill:#b1bac4;font:11px ui-monospace,SFMono-Regular,Consolas,monospace}}
</style>
<rect class="bg" width="1100" height="300" rx="18"/>
<rect x="1" y="1" width="1098" height="298" rx="17" fill="none" stroke="#30363d"/>

<text class="label" x="42" y="39">PUBLIC ACTIVITY</text>
<text class="h" x="42" y="67">{esc(USER)}</text>
<text class="muted" x="214" y="67">{profile.get("public_repos", 0)} public repos · {len(events)} recent API events</text>

<line x1="550" y1="30" x2="550" y2="270" stroke="#21262d"/>

<text class="label" x="42" y="88">RECENT REPOSITORIES</text>
{repo_svg}

<text class="label" x="42" y="190">RECENT EVENTS</text>
{events_svg}

<text class="label" x="585" y="58">LANGUAGE SIGNAL</text>
{lang_svg}

<text class="small" x="585" y="262">generated inside the profile repository · public data only</text>
</svg>'''

OUT.write_text(svg, encoding="utf-8")
