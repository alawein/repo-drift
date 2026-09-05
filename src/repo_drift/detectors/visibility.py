"""visibility — flag mismatches between claimed and actual GitHub visibility.

Operator declares the expected visibility ('public' or 'private') in
.drift-rules.yaml. The detector reads the actual visibility from the GitHub
API and emits a finding if they don't match.

Configuration:
  expected — required when the detector is enabled. One of 'public' / 'private'.
  repo     — optional 'owner/name'. Defaults to parsing git origin remote.

API failures emit warnings (severity=warning) rather than errors so a flaky
GitHub does not block PR CI on its own. The same applies to inability to
determine the repo slug (e.g. detached working copies).

`api` and `get_repo_slug` are keyword-only test seams — production calls
through the `gh` CLI via repo_drift._github.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from repo_drift._github import (
    fetch_repo_metadata as _default_fetch_metadata,
)
from repo_drift._github import (
    get_repo_slug as _default_get_slug,
)
from repo_drift.finding import Finding

_VALID_EXPECTED = frozenset({"public", "private"})


def detect(
    repo_root: Path,
    config: dict,
    *,
    api: Callable[[str], dict] | None = None,
    get_repo_slug: Callable[[Path], str | None] | None = None,
) -> list[Finding]:
    expected = config.get("expected")
    if expected is None:
        return []

    if expected not in _VALID_EXPECTED:
        raise ValueError(
            f"visibility.expected must be one of {sorted(_VALID_EXPECTED)}, got {expected!r}"
        )

    api = api or _default_fetch_metadata
    get_slug = get_repo_slug or _default_get_slug

    slug = config.get("repo") or get_slug(repo_root)
    file_for_finding = _finding_file(repo_root)

    if not slug:
        return [
            Finding(
                detector="visibility",
                file=file_for_finding,
                line=None,
                message=(
                    "visibility check skipped: could not determine GitHub repo slug "
                    "(set `detector_config.visibility.repo` in .drift-rules.yaml)"
                ),
                severity="warning",
            )
        ]

    try:
        metadata = api(slug)
    except Exception as exc:  # noqa: BLE001 - api is an injectable callable of
        # unknown failure modes; one detector must not crash the whole run.
        return [
            Finding(
                detector="visibility",
                file=file_for_finding,
                line=None,
                message=f"visibility API call failed for {slug}: {exc}",
                severity="warning",
            )
        ]

    actual = (metadata.get("visibility") or "").lower()
    # GitHub Enterprise returns 'internal' for internal repos; treat the same as
    # private from a policy-comparison standpoint.
    actual_normalized = "private" if actual == "internal" else actual

    if actual_normalized == expected:
        return []

    return [
        Finding(
            detector="visibility",
            file=file_for_finding,
            line=None,
            message=(
                f"{slug} visibility mismatch: docs declare expected={expected!r} "
                f"but GitHub reports {actual!r}"
            ),
            fix_hint=(
                "Update .drift-rules.yaml visibility.expected to match GitHub, "
                "or change the repo's visibility on GitHub"
            ),
        )
    ]


def _finding_file(repo_root: Path) -> Path:
    if (repo_root / ".drift-rules.yaml").is_file():
        return Path(".drift-rules.yaml")
    return Path(".")
