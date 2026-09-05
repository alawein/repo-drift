"""Shared GitHub helpers used by visibility and branch_name detectors.

Both functions take an injectable subprocess runner so tests don't need git
or the gh CLI on PATH.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

# (cmd: list[str], cwd: Path | None) -> (returncode, stdout, stderr)
SubprocessRunner = Callable[[list, Path | None], tuple]


def _default_runner(cmd: list[str], cwd: Path | None) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


_REMOTE_PATTERNS = (re.compile(r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?/?$"),)


def get_repo_slug(
    repo_root: Path,
    *,
    runner: SubprocessRunner = _default_runner,
) -> str | None:
    """Return `<owner>/<repo>` parsed from origin remote, or None if unresolvable."""
    code, out, _ = runner(["git", "config", "--get", "remote.origin.url"], repo_root)
    if code != 0 or not out.strip():
        return None
    url = out.strip()
    for pat in _REMOTE_PATTERNS:
        m = pat.search(url)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
    return None


def fetch_repo_metadata(
    slug: str,
    *,
    runner: SubprocessRunner = _default_runner,
) -> dict:
    """Return GitHub repo metadata via `gh api`. Raises RuntimeError on failure."""
    code, out, err = runner(
        ["gh", "api", f"repos/{slug}", "--jq", "{visibility, default_branch}"],
        None,
    )
    if code != 0:
        raise RuntimeError(f"gh api repos/{slug} failed: {err.strip() or 'rc=' + str(code)}")
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh api repos/{slug} returned invalid JSON: {exc}") from exc
