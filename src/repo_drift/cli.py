"""Drift subcommand dispatcher.

Exposes two operator entry points:
  - run(): execute detectors and emit findings via the chosen reporter
  - explain(): list registered detectors so operators know what's available

main() wraps both behind an argparse interface so the same code is callable
from the repo-drift root CLI and from a standalone `python -m
repo_drift.cli` invocation.

The registry argument is keyword-only and defaults to the package-level
default registry. Tests inject a custom registry to keep dispatch logic
independent of the detector roster.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path

from repo_drift.registry import DetectorRegistry
from repo_drift.reporters import render_github, render_json
from repo_drift.rules import Rules
from repo_drift.runner import run_detectors


def default_registry() -> DetectorRegistry:
    """Return the production registry with all built-in detectors registered."""
    from repo_drift.detectors import (
        agent_contract,
        branch_name,
        claimed_dep,
        feature_claim,
        kernel_conformance,
        metadata_schema,
        missing_file,
        stale_config,
        visibility,
        workflow_pin,
        worktree_registry,
    )

    registry = DetectorRegistry()
    registry.register("branch_name", branch_name.detect)
    registry.register("claimed_dep", claimed_dep.detect)
    registry.register("feature_claim", feature_claim.detect)
    registry.register("missing_file", missing_file.detect)
    registry.register("stale_config", stale_config.detect)
    registry.register("visibility", visibility.detect)
    # Kernel canonicalization detectors (opt-in: no-op unless their required
    # detector_config keys are present in .drift-rules.yaml, same convention
    # as `visibility` above). See alawein docs/governance/kernel-spec.md and
    # docs/internal/plans/2026-09-08-kernel-canonicalization.md Phase 2.
    registry.register("kernel_conformance", kernel_conformance.detect)
    registry.register("workflow_pin", workflow_pin.detect)
    registry.register("agent_contract", agent_contract.detect)
    registry.register("metadata_schema", metadata_schema.detect)
    registry.register("worktree_registry", worktree_registry.detect)
    return registry


def run(
    *,
    target: Path,
    rules_path: Path | None,
    reporter: str,
    only: Iterable[str] | None,
    registry: DetectorRegistry | None = None,
) -> int:
    registry = registry if registry is not None else default_registry()
    rules = Rules.load(rules_path) if rules_path else Rules()

    findings = run_detectors(
        registry=registry,
        rules=rules,
        target=target,
        only=list(only) if only is not None else None,
    )

    if reporter == "github":
        output = render_github(findings)
    else:
        output = render_json(findings)

    if output:
        print(output)

    has_error = any(f.severity == "error" for f in findings)
    return 1 if has_error else 0


def explain(*, registry: DetectorRegistry | None = None) -> int:
    registry = registry if registry is not None else default_registry()
    names = registry.names()
    if not names:
        print("(no detectors registered)")
    else:
        for name in names:
            print(name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-drift",
        description="Repository drift detectors",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run detectors and emit findings")
    check.add_argument(
        "--target",
        type=Path,
        default=Path.cwd(),
        help="Repo root to scan. Defaults to cwd.",
    )
    check.add_argument(
        "--rules",
        type=Path,
        default=None,
        help="Path to .drift-rules.yaml. Defaults to <target>/.drift-rules.yaml if it exists.",
    )
    check.add_argument(
        "--reporter",
        choices=("json", "github"),
        default="json",
    )
    check.add_argument(
        "--detector",
        action="append",
        default=None,
        help="Run only the named detector (repeatable). Overrides opt_out.",
    )

    sub.add_parser("explain", help="List registered detectors")

    return parser


def main(
    argv: list[str] | None = None,
    *,
    registry: DetectorRegistry | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "check":
        rules_path = args.rules
        if rules_path is None:
            candidate = args.target / ".drift-rules.yaml"
            rules_path = candidate if candidate.exists() else None
        return run(
            target=args.target,
            rules_path=rules_path,
            reporter=args.reporter,
            only=args.detector,
            registry=registry,
        )
    if args.command == "explain":
        return explain(registry=registry)

    parser.error(f"unsupported command {args.command}")
    return 2  # pragma: no cover  (parser.error raises)


if __name__ == "__main__":
    raise SystemExit(main())
