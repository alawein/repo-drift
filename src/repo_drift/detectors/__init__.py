"""Built-in drift detectors.

Each detector is a module exposing `detect(repo_root, config) -> list[Finding]`.
Detectors are registered by `repo_drift.cli.default_registry` so the
main CLI surface stays decoupled from individual detector implementations.
"""

from __future__ import annotations
