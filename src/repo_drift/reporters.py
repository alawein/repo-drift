"""Output formatters for drift findings.

Two formats today:
  - render_json: structured payload for batch / dashboards
  - render_github: GitHub Actions workflow commands so findings show up as
    PR annotations on the relevant lines

GitHub workflow command format reference:
  https://docs.github.com/actions/using-workflows/workflow-commands-for-github-actions
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from repo_drift.finding import Finding

_GITHUB_SEVERITY_TO_CMD = {
    "error": "error",
    "warning": "warning",
    "info": "notice",
}


def render_json(findings: Iterable[Finding]) -> str:
    items = list(findings)
    payload = {
        "count": len(items),
        "findings": [f.to_dict() for f in items],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_github(findings: Iterable[Finding]) -> str:
    lines = []
    for finding in findings:
        cmd = _GITHUB_SEVERITY_TO_CMD[finding.severity]
        location = f"file={str(finding.file).replace(chr(92), '/')}"
        if finding.line is not None:
            location += f",line={finding.line}"
        message = f"[{finding.detector}] {finding.message}"
        if finding.fix_hint:
            message += f" — {finding.fix_hint}"
        # GitHub workflow commands require these escapes inside the message
        # so that multi-line messages don't break the command parser.
        message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        lines.append(f"::{cmd} {location}::{message}")
    return "\n".join(lines)
