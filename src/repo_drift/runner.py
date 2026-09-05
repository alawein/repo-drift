"""Detector dispatch.

run_detectors() is the single entry point used by the CLI and by tests.
It picks which detectors to run, calls each with the appropriate config, and
collects findings. Detector registration order does not affect output order:
findings come back grouped by detector name, sorted alphabetically, so output
is deterministic across runs.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from repo_drift.finding import Finding
from repo_drift.registry import DetectorRegistry
from repo_drift.rules import Rules


def run_detectors(
    *,
    registry: DetectorRegistry,
    rules: Rules,
    target: Path,
    only: Iterable[str] | None = None,
) -> list[Finding]:
    if only is not None:
        names = list(only)
        for name in names:
            registry.get(name)  # raises KeyError if unknown
    else:
        names = [name for name in registry.names() if rules.is_enabled(name)]

    findings: list[Finding] = []
    for name in sorted(names):
        detector = registry.get(name)
        config = rules.config_for(name)
        findings.extend(detector(target, config))
    return findings
