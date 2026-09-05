"""Detector plugin registry.

A detector is a callable `(repo_root: Path, config: dict) -> list[Finding]`.
Detectors register themselves with a DetectorRegistry; the CLI iterates the
registry to dispatch checks.

The registry deliberately rejects double-registration so that a typo in a
detector module name surfaces immediately rather than silently shadowing.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from repo_drift.finding import Finding

DetectorFn = Callable[[Path, dict], list[Finding]]


class DetectorRegistry:
    def __init__(self) -> None:
        self._detectors: dict[str, DetectorFn] = {}

    def register(self, name: str, detector: DetectorFn) -> None:
        if name in self._detectors:
            raise ValueError(f"detector {name!r} already registered")
        self._detectors[name] = detector

    def get(self, name: str) -> DetectorFn:
        if name not in self._detectors:
            raise KeyError(f"unknown detector: {name!r}")
        return self._detectors[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._detectors))

    def all(self) -> dict[str, DetectorFn]:
        return dict(self._detectors)
