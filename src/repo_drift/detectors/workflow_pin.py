"""workflow_pin — verify every reusable-workflow `uses:` reference in
`.github/workflows/*.yml` targets a single pinned SHA.

Configuration (opt-in: no-op unless `expected_sha` is present):
  expected_sha  — required to enable the detector. The canonical commit SHA.
  owner_repo    — optional 'owner/repo' to scope matching. Defaults to
                  matching any `uses: <anything>/.github/workflows/...@<sha>`
                  reference, i.e. every reusable workflow, not only the hub's.

Only reusable-workflow `uses:` lines (paths containing
`.github/workflows/` before the `@`) are considered; a plain action
reference like `actions/checkout@v4` is not a reusable *workflow* and is out
of scope for this detector.
"""

from __future__ import annotations

import re
from pathlib import Path

from repo_drift.finding import Finding

_USES_LINE = re.compile(
    r"^\s*(?:-\s*)?uses:\s*['\"]?(?P<ref>[^'\"\s]+)['\"]?\s*$"
)


def detect(repo_root: Path, config: dict) -> list[Finding]:
    expected_sha = config.get("expected_sha")
    if not expected_sha:
        return []

    owner_repo = config.get("owner_repo")
    workflows_dir = repo_root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []

    findings: list[Finding] = []
    for workflow_path in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        rel_path = workflow_path.relative_to(repo_root)
        try:
            lines = workflow_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for line_no, line in enumerate(lines, start=1):
            match = _USES_LINE.match(line)
            if not match:
                continue
            ref = match.group("ref")
            if ".github/workflows/" not in ref or "@" not in ref:
                continue
            path_part, _, sha = ref.rpartition("@")
            if owner_repo and not path_part.startswith(f"{owner_repo}/"):
                continue
            if sha == expected_sha:
                continue
            findings.append(
                Finding(
                    detector="workflow_pin",
                    file=rel_path,
                    line=line_no,
                    message=(
                        f"reusable workflow pin drifted: {path_part}@{sha} "
                        f"does not match expected @{expected_sha}"
                    ),
                    fix_hint=f"Pin to @{expected_sha} (see catalog/kernel.yaml in the hub)",
                )
            )

    return findings
