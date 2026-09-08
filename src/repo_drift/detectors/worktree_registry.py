"""worktree_registry — warn on git worktrees outside the registered roots.

Local-machine check: worktree paths are filesystem-specific, so this
detector is only meaningful when run against a local checkout, not in CI.
Findings are warnings, never errors, since an unregistered worktree is a
fleet-hygiene signal (see alawein ADR 0006), not a broken repo.

Configuration (opt-in: no-op unless `registered_roots` is present):
  registered_roots — required to enable the detector. A list of absolute
                      path prefixes (e.g. the two roots from ADR 0006:
                      `~/worktrees` and `~/.codex/worktrees`, expanded).

`list_worktrees` is a keyword-only test seam; production calls `git
worktree list --porcelain` via subprocess.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from repo_drift.finding import Finding


def _default_list_worktrees(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git worktree list failed")
    paths = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(line[len("worktree "):].strip())
    return paths


def _normalize(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix().lower()


def detect(
    repo_root: Path,
    config: dict,
    *,
    list_worktrees: Callable[[Path], list[str]] | None = None,
) -> list[Finding]:
    registered_roots = config.get("registered_roots")
    if not registered_roots:
        return []

    lister = list_worktrees or _default_list_worktrees
    finding_file = Path(".")

    try:
        worktree_paths = lister(repo_root)
    except Exception as exc:  # noqa: BLE001 - lister is an injectable callable of
        # unknown failure modes; one detector must not crash the whole run.
        return [
            Finding(
                detector="worktree_registry",
                file=finding_file,
                line=None,
                message=f"worktree_registry check skipped: git worktree list failed: {exc}",
                severity="warning",
            )
        ]

    normalized_roots = [_normalize(root) for root in registered_roots]
    findings: list[Finding] = []
    for path in worktree_paths:
        normalized_path = _normalize(path)
        if any(normalized_path.startswith(root) for root in normalized_roots):
            continue
        findings.append(
            Finding(
                detector="worktree_registry",
                file=finding_file,
                line=None,
                message=f"worktree outside registered roots: {path}",
                fix_hint=(
                    "Move the worktree under one of the registered roots, or remove it "
                    "with `git worktree remove` (never delete the directory by hand)"
                ),
                severity="warning",
            )
        )
    return findings
