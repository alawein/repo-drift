from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_drift.detectors import (
    agent_contract,
    kernel_conformance,
    metadata_schema,
    workflow_pin,
    worktree_registry,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- kernel_conformance ---------------------------------------------------


def test_kernel_conformance_is_opt_in() -> None:
    assert kernel_conformance.detect(Path("/nonexistent"), {}) == []


def test_kernel_conformance_flags_missing_manifest(tmp_path: Path) -> None:
    config = {"expected_kernel_version": "0.1.0", "expected_files": {"README.md": "abc"}}
    findings = kernel_conformance.detect(tmp_path, config)
    assert len(findings) == 1
    assert ".kernel-manifest.json" in findings[0].message


def test_kernel_conformance_flags_drift_and_version_mismatch(tmp_path: Path) -> None:
    write(
        tmp_path / ".kernel-manifest.json",
        json.dumps({"kernel_version": "0.0.9", "files": {"README.md": "wrong-hash"}}),
    )
    config = {
        "expected_kernel_version": "0.1.0",
        "expected_files": {"README.md": "right-hash", "AGENTS.md": "agents-hash"},
    }
    findings = kernel_conformance.detect(tmp_path, config)
    messages = [f.message for f in findings]
    assert any("kernel_version mismatch" in m for m in messages)
    assert any("README.md" in m and "drifted" in m for m in messages)
    assert any("AGENTS.md" in m and "missing" in m for m in messages)


def test_kernel_conformance_clean_when_matching(tmp_path: Path) -> None:
    write(
        tmp_path / ".kernel-manifest.json",
        json.dumps({"kernel_version": "0.1.0", "files": {"README.md": "hash-a"}}),
    )
    config = {"expected_kernel_version": "0.1.0", "expected_files": {"README.md": "hash-a"}}
    assert kernel_conformance.detect(tmp_path, config) == []


# --- workflow_pin ----------------------------------------------------------


def test_workflow_pin_is_opt_in() -> None:
    assert workflow_pin.detect(Path("/nonexistent"), {}) == []


def test_workflow_pin_flags_drifted_sha(tmp_path: Path) -> None:
    write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "jobs:\n  build:\n    uses: alawein/alawein/.github/workflows/ci.yml@deadbeef\n",
    )
    findings = workflow_pin.detect(tmp_path, {"expected_sha": "cafef00d"})
    assert len(findings) == 1
    assert findings[0].line == 3


def test_workflow_pin_ignores_non_reusable_workflow_uses(tmp_path: Path) -> None:
    write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "jobs:\n  build:\n    steps:\n      - uses: actions/checkout@v4\n",
    )
    assert workflow_pin.detect(tmp_path, {"expected_sha": "cafef00d"}) == []


def test_workflow_pin_matches_pinned_sha_is_clean(tmp_path: Path) -> None:
    write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "jobs:\n  build:\n    uses: alawein/alawein/.github/workflows/ci.yml@cafef00d\n",
    )
    assert workflow_pin.detect(tmp_path, {"expected_sha": "cafef00d"}) == []


# --- agent_contract ---------------------------------------------------------


def test_agent_contract_is_opt_in() -> None:
    assert agent_contract.detect(Path("/nonexistent"), {}) == []


def test_agent_contract_flags_missing_file(tmp_path: Path) -> None:
    findings = agent_contract.detect(tmp_path, {"required_sections": ["## Kernel contract"]})
    assert len(findings) == 1
    assert "missing" in findings[0].message


def test_agent_contract_flags_missing_section(tmp_path: Path) -> None:
    write(tmp_path / "AGENTS.md", "# AGENTS\n\n## Something else\n")
    findings = agent_contract.detect(tmp_path, {"required_sections": ["## Kernel contract"]})
    assert len(findings) == 1


def test_agent_contract_clean_when_section_present(tmp_path: Path) -> None:
    write(tmp_path / "AGENTS.md", "# AGENTS\n\n## Kernel contract\n\nBody.\n")
    assert agent_contract.detect(tmp_path, {"required_sections": ["## Kernel contract"]}) == []


# --- metadata_schema ---------------------------------------------------------


def test_metadata_schema_is_opt_in() -> None:
    assert metadata_schema.detect(Path("/nonexistent"), {}) == []


def test_metadata_schema_validates_against_schema(tmp_path: Path) -> None:
    write(tmp_path / "service-metadata.yaml", "profile: 8\n")
    write(
        tmp_path / "schemas" / "repo.schema.json",
        json.dumps({"type": "object", "properties": {"profile": {"type": "string"}}}),
    )
    findings = metadata_schema.detect(tmp_path, {"schema": "schemas/repo.schema.json"})
    assert len(findings) == 1


def test_metadata_schema_missing_schema_file_raises(tmp_path: Path) -> None:
    write(tmp_path / "service-metadata.yaml", "profile: x\n")
    with pytest.raises(ValueError, match="does not exist"):
        metadata_schema.detect(tmp_path, {"schema": "schemas/missing.json"})


# --- worktree_registry --------------------------------------------------------


def test_worktree_registry_is_opt_in() -> None:
    assert worktree_registry.detect(Path("/nonexistent"), {}) == []


def test_worktree_registry_flags_unregistered_worktree(tmp_path: Path) -> None:
    findings = worktree_registry.detect(
        tmp_path,
        {"registered_roots": ["/home/user/worktrees"]},
        list_worktrees=lambda _: ["/home/user/worktrees/repo/slug", "/tmp/rogue/repo"],
    )
    assert len(findings) == 1
    assert "rogue" in findings[0].message
    assert findings[0].severity == "warning"


def test_worktree_registry_clean_when_all_registered(tmp_path: Path) -> None:
    findings = worktree_registry.detect(
        tmp_path,
        {"registered_roots": ["/home/user/worktrees"]},
        list_worktrees=lambda _: ["/home/user/worktrees/repo/slug"],
    )
    assert findings == []


def test_worktree_registry_git_failure_is_a_warning(tmp_path: Path) -> None:
    def _boom(_root: Path) -> list[str]:
        raise RuntimeError("git not found")

    findings = worktree_registry.detect(
        tmp_path, {"registered_roots": ["/home/user/worktrees"]}, list_worktrees=_boom
    )
    assert len(findings) == 1
    assert findings[0].severity == "warning"
