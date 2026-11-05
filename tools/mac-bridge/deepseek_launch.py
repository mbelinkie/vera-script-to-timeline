"""Narrow, popup-free DeepSeek launch tools for the VERA Mac Bridge.

These can only (1) post a groomed brief as a comment on an issue in one of the
two VERA repositories and add the `deepseek`/`deepseek-pro` label, or (2) read
an issue's DeepSeek status. They run the local `gh` CLI with fixed arguments
(never a shell), so no on-Mac approval is needed. The label starts the
`.github/workflows/deepseek.yml` job on GitHub's servers, not on this Mac.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

BRIEF_MARK = "<!-- vera-deepseek-brief -->"
CODEX_BRIEF_MARK = "<!-- vera-codex-brief -->"
CODEX_LABEL = "codex-prepped"
STATUS_MARK = "<!-- vera-deepseek-status -->"
REPOS = {
    "timeline": "mbelinkie/vera-script-to-timeline",
    "script-to-timeline": "mbelinkie/vera-script-to-timeline",
    "vera-script-to-timeline": "mbelinkie/vera-script-to-timeline",
    "mbelinkie/vera-script-to-timeline": "mbelinkie/vera-script-to-timeline",
    "research": "mbelinkie/vera-research-video-clips",
    "vera-research-video-clips": "mbelinkie/vera-research-video-clips",
    "mbelinkie/vera-research-video-clips": "mbelinkie/vera-research-video-clips",
}
LABELS = {"flash": "deepseek", "pro": "deepseek-pro"}
ELIGIBLE_TYPES = {"type:implementation", "type:bug"}
TRIGGER_COLORS = {"deepseek": "1f6feb", "deepseek-pro": "8250df"}
MIN_BRIEF = 40
MAX_BRIEF = 60_000
TIMEOUT = 30


class LaunchError(ValueError):
    pass


def resolve_repo(repo: str) -> str:
    key = str(repo or "").strip().lower()
    if key not in REPOS:
        raise LaunchError("repo must be 'timeline' or 'research'")
    return REPOS[key]


def resolve_issue(issue: int | str) -> int:
    try:
        number = int(str(issue).lstrip("#"))
    except ValueError as error:
        raise LaunchError("issue must be a positive issue number") from error
    if number < 1 or number > 10_000_000:
        raise LaunchError("issue must be a positive issue number")
    return number


def _env() -> dict:
    keep = ("HOME", "USER", "LOGNAME", "LANG", "TMPDIR", "GH_CONFIG_DIR")
    env = {name: os.environ[name] for name in keep if name in os.environ}
    env.setdefault("HOME", str(Path.home()))
    env["PATH"] = os.environ.get(
        "VERA_BRIDGE_PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    )
    env["GH_PROMPT_DISABLED"] = "1"
    env["NO_COLOR"] = "1"
    return env


def _gh(args: list[str], stdin: str | None = None) -> str:
    env = _env()
    gh = shutil.which("gh", path=env["PATH"])
    if not gh:
        raise LaunchError("GitHub CLI (gh) was not found on this Mac's bridge PATH")
    done = subprocess.run(
        [gh, *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        env=env,
        check=False,
    )
    if done.returncode != 0:
        raise LaunchError(
            f"gh {' '.join(args[:2])} failed: {done.stderr.strip()[-400:]}"
        )
    return done.stdout.strip()


def launch(repo: str, issue: int | str, brief: str, model: str = "flash") -> dict:
    full = resolve_repo(repo)
    number = resolve_issue(issue)
    model = str(model or "flash").strip().lower()
    if model not in LABELS:
        raise LaunchError("model must be 'flash' or 'pro'")
    text = str(brief or "").strip()
    if len(text) < MIN_BRIEF:
        raise LaunchError(f"brief must be at least {MIN_BRIEF} characters")
    if len(text) > MAX_BRIEF:
        raise LaunchError(f"brief must be at most {MAX_BRIEF} characters")
    label = LABELS[model]

    view = json.loads(
        _gh(["issue", "view", str(number), "-R", full, "--json", "state,labels,url"])
    )
    if view.get("state") != "OPEN":
        raise LaunchError("issue is not open")
    current = {item.get("name") for item in view.get("labels", [])}
    if "deepseek-excluded" in current:
        raise LaunchError(
            "issue is labelled deepseek-excluded; "
            "use vera_post_brief to prep it for Codex"
        )
    if not current & ELIGIBLE_TYPES:
        raise LaunchError("only type:implementation or type:bug issues go to DeepSeek")
    if "deepseek-running" in current:
        raise LaunchError("a DeepSeek attempt is already running for this issue")

    comment_url = _gh(
        ["issue", "comment", str(number), "-R", full, "--body-file", "-"],
        stdin=f"{BRIEF_MARK}\n## DeepSeek brief ({model})\n\n{text}\n",
    )
    _gh(
        [
            "label",
            "create",
            label,
            "-R",
            full,
            "--color",
            TRIGGER_COLORS[label],
            "--force",
        ]
    )
    stale = [name for name in ("deepseek", "deepseek-pro") if name in current]
    if stale:
        _gh(
            [
                "issue",
                "edit",
                str(number),
                "-R",
                full,
                *[part for name in stale for part in ("--remove-label", name)],
            ]
        )
    _gh(["issue", "edit", str(number), "-R", full, "--add-label", label])
    return {
        "status": "launched",
        "repo": full,
        "issue": number,
        "model": model,
        "brief_comment": comment_url.splitlines()[-1] if comment_url else "",
        "next": "The GitHub job starts within about a minute and posts progress on "
        f"{view.get('url')}. "
        "It ends with a draft PR (label deepseek-done) or a deepseek-failed note.",
    }


def _check_brief(brief: str) -> str:
    text = str(brief or "").strip()
    if len(text) < MIN_BRIEF:
        raise LaunchError(f"brief must be at least {MIN_BRIEF} characters")
    if len(text) > MAX_BRIEF:
        raise LaunchError(f"brief must be at most {MAX_BRIEF} characters")
    return text


def post_brief(repo: str, issue: int | str, brief: str) -> dict:
    """Post a Codex prep brief on an open code issue and label it codex-prepped."""
    full = resolve_repo(repo)
    number = resolve_issue(issue)
    text = _check_brief(brief)
    view = json.loads(
        _gh(["issue", "view", str(number), "-R", full, "--json", "state,labels,url"])
    )
    if view.get("state") != "OPEN":
        raise LaunchError("issue is not open")
    current = {item.get("name") for item in view.get("labels", [])}
    if not current & ELIGIBLE_TYPES:
        raise LaunchError(
            "only type:implementation or type:bug issues get Codex briefs"
        )
    comment_url = _gh(
        ["issue", "comment", str(number), "-R", full, "--body-file", "-"],
        stdin=f"{CODEX_BRIEF_MARK}\n## Codex prep brief (from ChatGPT)\n\n{text}\n",
    )
    _gh(["label", "create", CODEX_LABEL, "-R", full, "--color", "0e8a16", "--force"])
    _gh(["issue", "edit", str(number), "-R", full, "--add-label", CODEX_LABEL])
    return {
        "status": "posted",
        "repo": full,
        "issue": number,
        "brief_comment": comment_url.splitlines()[-1] if comment_url else "",
        "next": f"{view.get('url')} is now labelled {CODEX_LABEL} and shows as "
        "Ready for Codex on the prep board.",
    }


def status(repo: str, issue: int | str) -> dict:
    full = resolve_repo(repo)
    number = resolve_issue(issue)
    view = json.loads(
        _gh(
            [
                "issue",
                "view",
                str(number),
                "-R",
                full,
                "--json",
                "state,labels,comments,url",
            ]
        )
    )
    labels = sorted(
        item.get("name")
        for item in view.get("labels", [])
        if str(item.get("name", "")).startswith("deepseek")
    )
    notes = [
        c.get("body", "")
        for c in view.get("comments", [])
        if STATUS_MARK in c.get("body", "")
    ]
    latest = notes[-1].replace(STATUS_MARK, "").strip()[:1500] if notes else ""
    state = (
        "running"
        if "deepseek-running" in labels
        else "draft-ready"
        if "deepseek-done" in labels
        else "failed"
        if "deepseek-failed" in labels
        else "queued"
        if {"deepseek", "deepseek-pro"} & set(labels)
        else "not-started"
    )
    return {
        "repo": full,
        "issue": number,
        "url": view.get("url"),
        "deepseek": state,
        "labels": labels,
        "latest_update": latest,
    }
