#!/usr/bin/env python3
"""
push_to_github.py — pushes all CuratorTaste AI files to:
https://github.com/akhil304/Personal-Entertainment-Guide

Usage:
    export GITHUB_TOKEN=your_token_here
    python push_to_github.py
"""

import os, json, urllib.request, urllib.error
from pathlib import Path

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_USER  = "akhil304"
REPO_NAME    = "Personal-Entertainment-Guide"

if not GITHUB_TOKEN:
    print("ERROR: Set GITHUB_TOKEN first.")
    print("  export GITHUB_TOKEN=ghp_your_token")
    print("  (same token used for daily-planner)")
    exit(1)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
    "User-Agent": "personal-entertainment-guide-push",
}

def gh(method, path, body=None):
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def get_head_sha():
    for branch in ("main", "master"):
        d, s = gh("GET", f"/repos/{GITHUB_USER}/{REPO_NAME}/git/refs/heads/{branch}")
        if s == 200 and "object" in d:
            print(f"  Branch: {branch}")
            return d["object"]["sha"], branch
    return None, None

def create_blob(content):
    d, _ = gh("POST", f"/repos/{GITHUB_USER}/{REPO_NAME}/git/blobs",
              {"content": content, "encoding": "utf-8"})
    return d["sha"]

def push_files(file_map):
    print(f"\nConnecting to github.com/{GITHUB_USER}/{REPO_NAME}...")
    info, status = gh("GET", f"/repos/{GITHUB_USER}/{REPO_NAME}")
    if status != 200:
        print(f"Cannot access repo (status {status}): {info.get('message')}")
        print("Check your GITHUB_TOKEN has 'repo' scope and the repo exists.")
        exit(1)
    print(f"  Repo found: {info['full_name']}")

    head_sha, branch = get_head_sha()
    if not head_sha:
        print("Could not find main/master branch.")
        exit(1)

    tree_data, _ = gh("GET", f"/repos/{GITHUB_USER}/{REPO_NAME}/git/commits/{head_sha}")
    base_tree_sha = tree_data["tree"]["sha"]

    print(f"\nUploading {len(file_map)} files...")
    entries = []
    for path, content in file_map.items():
        print(f"  + {path}")
        entries.append({
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": create_blob(content),
        })

    tree_resp, _ = gh("POST", f"/repos/{GITHUB_USER}/{REPO_NAME}/git/trees",
                      {"base_tree": base_tree_sha, "tree": entries})

    commit_resp, _ = gh("POST", f"/repos/{GITHUB_USER}/{REPO_NAME}/git/commits", {
        "message": (
            "feat: CuratorTaste AI — full project scaffold\n\n"
            "- YouTube OAuth2 connector (liked videos + subscriptions)\n"
            "- Fingerprint engine with recency-weighted trait scoring\n"
            "- Mood engine (time-of-day pattern learning)\n"
            "- Signal collector (liked/watched/skipped/disliked)\n"
            "- Curator agent (Claude-powered ranked recommendations)\n"
            "- Preference agent (natural language ignore/boost commands)\n"
            "- 8-week build roadmap in README"
        ),
        "tree": tree_resp["sha"],
        "parents": [head_sha],
    })

    gh("PATCH", f"/repos/{GITHUB_USER}/{REPO_NAME}/git/refs/heads/{branch}",
       {"sha": commit_resp["sha"], "force": False})

    print(f"\n✅ Done! All files pushed.")
    print(f"   https://github.com/{GITHUB_USER}/{REPO_NAME}")

def read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except:
        return ""

if __name__ == "__main__":
    push_files({
        "README.md":                           read("README.md"),
        ".env.example":                        read(".env.example"),
        ".gitignore":                          read(".gitignore"),
        "requirements.txt":                    read("requirements.txt"),
        "core/__init__.py":                    "",
        "core/fingerprint.py":                 read("core/fingerprint.py"),
        "core/mood_engine.py":                 read("core/mood_engine.py"),
        "core/signal_collector.py":            read("core/signal_collector.py"),
        "agents/__init__.py":                  "",
        "agents/curator_agent.py":             read("agents/curator_agent.py"),
        "agents/preference_agent.py":          read("agents/preference_agent.py"),
        "connectors/__init__.py":              "",
        "connectors/youtube_connector.py":     read("connectors/youtube_connector.py"),
        "storage/.gitkeep":                    "",
        "tests/.gitkeep":                      "",
    })
