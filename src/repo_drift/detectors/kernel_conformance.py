"""kernel_conformance — verify a repo's ``.kernel-manifest.json`` against an
expected manifest, without re-rendering.

This detector never invokes the kernel renderer (see
alawein/core/alawein `scripts/kernel/`); it only compares hashes, keeping
repo-drift dependency-free per ADR 0004
(alawein `docs/adr/0004-kernel-renderer-and-distribution.md`). The expected
manifest -- kernel_version plus a `{path: sha256}` map -- is supplied
entirely through `.drift-rules.yaml` `detector_config`, typically populated
by the kernel-sync fanout for that repo's rendered output.

Configuration (opt-in: no-op unless both keys are present):
  expected_kernel_version — required to enable the detector.
  expected_files           — required to enable the detector. `{path: sha256}`.

Missing `.kernel-manifest.json` on disk is reported as a single finding
rather than one finding per expected file, since the repo has evidently
never adopted the kernel yet.
"""

from __future__ import annotations

import json
from pathlib import Path

from repo_drift.finding import Finding

MANIFEST_FILENAME = ".kernel-manifest.json"


def detect(repo_root: Path, config: dict) -> list[Finding]:
    expected_kernel_version = config.get("expected_kernel_version")
    expected_files = config.get("expected_files")
    if not expected_kernel_version or not expected_files:
        return []

    manifest_path = repo_root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return [
            Finding(
                detector="kernel_conformance",
                file=Path(MANIFEST_FILENAME),
                line=None,
                message=f"{MANIFEST_FILENAME} is missing; kernel not yet adopted in this repo",
                fix_hint="Run the kernel renderer for this repo (see kernel-spec.md)",
            )
        ]

    try:
        actual = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [
            Finding(
                detector="kernel_conformance",
                file=Path(MANIFEST_FILENAME),
                line=None,
                message=f"{MANIFEST_FILENAME} failed to parse: {exc}",
                fix_hint="Re-render the kernel manifest for this repo",
            )
        ]

    findings: list[Finding] = []
    actual_version = actual.get("kernel_version")
    if actual_version != expected_kernel_version:
        findings.append(
            Finding(
                detector="kernel_conformance",
                file=Path(MANIFEST_FILENAME),
                line=None,
                message=(
                    f"kernel_version mismatch: expected={expected_kernel_version!r} "
                    f"actual={actual_version!r}"
                ),
                fix_hint="Re-render this repo against the current kernel version",
            )
        )

    actual_files = actual.get("files", {})
    for rel_path, expected_hash in sorted(expected_files.items()):
        actual_hash = actual_files.get(rel_path)
        if actual_hash is None:
            findings.append(
                Finding(
                    detector="kernel_conformance",
                    file=Path(rel_path),
                    line=None,
                    message=f"{rel_path} is missing from {MANIFEST_FILENAME}",
                    fix_hint="Re-render the managed file set for this repo",
                )
            )
        elif actual_hash != expected_hash:
            findings.append(
                Finding(
                    detector="kernel_conformance",
                    file=Path(rel_path),
                    line=None,
                    message=f"{rel_path} manifest hash drifted from the kernel-expected hash",
                    fix_hint="Re-render this file from the kernel, or update the kernel pin",
                )
            )

    return findings
