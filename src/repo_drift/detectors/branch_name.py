"""branch_name — flag stale default-branch references in docs.

Catches stale default-branch references after a repository changes
default branches. Only branch-context matches count, so
prose like "the main idea" or "master plan" never triggers.

The expected default branch comes from `.drift-rules.yaml` `expected`, or
auto-detects from `gh api repos/<slug>` when not provided. Without either,
the detector silently no-ops — same opt-in shape as the visibility detector.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from repo_drift._github import (
    fetch_repo_metadata as _default_fetch_metadata,
)
from repo_drift._github import (
    get_repo_slug as _default_get_slug,
)
from repo_drift.finding import Finding

_KNOWN_DEFAULTS = ("main", "master", "trunk", "develop")
DEFAULT_DOC_FILES = ("README.md", "CLAUDE.md", "AGENTS.md", "SSOT.md", "CONTRIBUTING.md")


def detect(
    repo_root: Path,
    config: dict,
    *,
    api: Callable[[str], dict] | None = None,
    get_repo_slug: Callable[[Path], str | None] | None = None,
) -> list[Finding]:
    expected = config.get("expected")
    file_for_warnings = _file_for_warnings(repo_root)

    if expected is None:
        api = api or _default_fetch_metadata
        get_slug = get_repo_slug or _default_get_slug
        slug = config.get("repo") or get_slug(repo_root)
        if not slug:
            return []  # opt-in: no expected, no slug → no-op
        try:
            metadata = api(slug)
        except Exception as exc:  # noqa: BLE001 - api is an injectable callable of
            # unknown failure modes; one detector must not crash the whole run.
            return [
                Finding(
                    detector="branch_name",
                    file=file_for_warnings,
                    line=None,
                    message=f"branch_name API call failed for {slug}: {exc}",
                    severity="warning",
                )
            ]
        expected = (metadata.get("default_branch") or "").strip()
        if not expected:
            return []

    wrong_names = [n for n in _KNOWN_DEFAULTS if n != expected]
    patterns = [_branch_context_pattern(name) for name in wrong_names]
    doc_files = tuple(config.get("doc_files") or DEFAULT_DOC_FILES)

    findings: list[Finding] = []
    for doc_file in doc_files:
        doc_path = repo_root / doc_file
        if not doc_path.is_file():
            continue
        text = doc_path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, name in zip(patterns, wrong_names, strict=True):
                if pattern.search(line):
                    findings.append(
                        Finding(
                            detector="branch_name",
                            file=Path(doc_file),
                            line=lineno,
                            message=(
                                f"{doc_file}:{lineno} references branch {name!r} "
                                f"but default branch is {expected!r}"
                            ),
                            fix_hint=(
                                f"Replace {name!r} with {expected!r} in this branch reference"
                            ),
                        )
                    )
                    break  # one finding per line keeps output readable
    return findings


def _branch_context_pattern(name: str) -> re.Pattern[str]:
    n = re.escape(name)
    # Each alternation captures one explicit branch context. The patterns are
    # deliberately narrow so prose ("the main idea", "master plan") is never
    # flagged. Markdown wraps branch names in backticks/quotes, so the
    # separator class allows those between "branch:" / "branch " and the
    # name. Case-insensitive because docs commonly capitalize "Branch:".
    return re.compile(
        r"(?:"
        rf"\bbranch[:\s`'\"]+{n}\b"
        rf"|\b{n}[\s\-`'\"]*[\s\-]branch\b"
        rf"|\bgit\s+(?:checkout|switch|push|pull|merge|rebase|reset|cherry-pick)\b[^\n]*?\b{n}\b"
        rf"|\borigin/{n}\b"
        rf"|\brefs/heads/{n}\b"
        rf"|\b(?:tree|blob|commits|edit|raw)/{n}\b"
        r")",
        re.IGNORECASE,
    )


def _file_for_warnings(repo_root: Path) -> Path:
    if (repo_root / ".drift-rules.yaml").is_file():
        return Path(".drift-rules.yaml")
    return Path(".")
