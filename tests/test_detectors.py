from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_drift.detectors import (
    branch_name,
    claimed_dep,
    feature_claim,
    missing_file,
    stale_config,
    visibility,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_branch_name_avoids_prose_false_positive(tmp_path: Path) -> None:
    write(tmp_path / "README.md", "Our master plan is composable.\nbranch: master\n")
    findings = branch_name.detect(tmp_path, {"expected": "main"})
    assert [(item.file, item.line) for item in findings] == [(Path("README.md"), 2)]


def test_claimed_dep_checks_manifest_and_nearby_disclaimer(tmp_path: Path) -> None:
    write(tmp_path / "README.md", "Uses kit-sdk.\nNo live SDK calls.\n")
    write(tmp_path / "package.json", json.dumps({"dependencies": {}}))
    config = {"tracked_packages": {"js": ["kit-sdk"]}, "disclaimer_pattern": "no live SDK"}
    assert claimed_dep.detect(tmp_path, config) == []
    write(tmp_path / "README.md", "Uses kit-sdk.\n")
    assert len(claimed_dep.detect(tmp_path, config)) == 1


def test_feature_claim_requires_matching_source_token(tmp_path: Path) -> None:
    write(tmp_path / "README.md", "Webhook delivery\n")
    config = {"claims": [{"tokens": ["webhook"], "description": "Webhook delivery"}]}
    assert len(feature_claim.detect(tmp_path, config)) == 1
    write(tmp_path / "src" / "delivery.py", "def webhook(): pass\n")
    assert feature_claim.detect(tmp_path, config) == []


def test_missing_file_checks_required_and_local_json_schema(tmp_path: Path) -> None:
    write(tmp_path / "config" / "service.yaml", "name: 8\n")
    write(
        tmp_path / "schemas" / "service.schema.json",
        json.dumps(
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            }
        ),
    )
    config = {
        "required": ["README.md", "config/service.yaml"],
        "schemas": {"config/service.yaml": "schemas/service.schema.json"},
    }
    findings = missing_file.detect(tmp_path, config)
    assert len(findings) == 2
    assert {item.file.as_posix() for item in findings} == {"README.md", "config/service.yaml"}


def test_missing_file_rejects_parent_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="relative"):
        missing_file.detect(tmp_path, {"required": ["../outside"]})


def test_stale_config_can_be_configured(tmp_path: Path) -> None:
    write(tmp_path / "tool.config.js", "module.exports = {}\n")
    write(tmp_path / "package.json", json.dumps({"devDependencies": {}}))
    config = {"config_map": {"tool.config.js": ["tool-package"]}}
    assert len(stale_config.detect(tmp_path, config)) == 1
    write(tmp_path / "package.json", json.dumps({"devDependencies": {"tool-package": "1"}}))
    assert stale_config.detect(tmp_path, config) == []


def test_visibility_is_opt_in_and_api_errors_are_warnings(tmp_path: Path) -> None:
    assert visibility.detect(tmp_path, {}) == []
    findings = visibility.detect(
        tmp_path,
        {"expected": "public", "repo": "owner/repo"},
        api=lambda _: (_ for _ in ()).throw(RuntimeError("unavailable")),
    )
    assert len(findings) == 1
    assert findings[0].severity == "warning"
