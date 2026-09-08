"""agent_contract — verify AGENTS.md carries the required managed sections.

Configuration (opt-in: no-op unless `required_sections` is present):
  required_sections — required to enable the detector. A list of exact
                       Markdown heading lines, e.g. "## Kernel contract".
  target             — optional path, defaults to "AGENTS.md".

A missing AGENTS.md when the detector is enabled is one finding, not one
per missing section, since there is nothing more specific to point at.
"""

from __future__ import annotations

from pathlib import Path

from repo_drift.finding import Finding


def detect(repo_root: Path, config: dict) -> list[Finding]:
    required_sections = config.get("required_sections")
    if not required_sections:
        return []

    target = config.get("target", "AGENTS.md")
    target_path = repo_root / target
    rel_target = Path(target)

    if not target_path.is_file():
        return [
            Finding(
                detector="agent_contract",
                file=rel_target,
                line=None,
                message=f"{rel_target.as_posix()} is missing",
                fix_hint="Render AGENTS.md from the kernel (see docs/governance/kernel-spec.md)",
            )
        ]

    text = target_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    findings: list[Finding] = []
    for section in required_sections:
        if section not in lines:
            findings.append(
                Finding(
                    detector="agent_contract",
                    file=rel_target,
                    line=None,
                    message=f"{rel_target.as_posix()} is missing required section: {section!r}",
                    fix_hint="Re-render the kernel-managed AGENTS.md section",
                )
            )

    return findings
