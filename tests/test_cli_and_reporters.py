from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_drift.cli import main
from repo_drift.finding import Finding
from repo_drift.reporters import render_github


def test_explain_lists_all_builtin_detectors(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["explain"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "branch_name",
        "claimed_dep",
        "feature_claim",
        "missing_file",
        "stale_config",
        "visibility",
    ]


def test_check_uses_rules_and_emits_github_annotations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("Use branch: master.\n", encoding="utf-8")
    (tmp_path / ".drift-rules.yaml").write_text(
        "opt_out: [claimed_dep, feature_claim, missing_file, stale_config, visibility]\n"
        "detector_config:\n  branch_name:\n    expected: main\n",
        encoding="utf-8",
    )

    assert main(["check", "--target", str(tmp_path), "--reporter", "github"]) == 1
    output = capsys.readouterr().out.strip()
    assert output.startswith("::error file=README.md,line=1::[branch_name]")


def test_check_without_findings_returns_zero_and_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", "--target", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {"count": 0, "findings": []}


def test_github_reporter_escapes_message_control_characters() -> None:
    output = render_github([Finding("test", Path("a.md"), 2, "one%\ntwo", severity="warning")])
    assert output == "::warning file=a.md,line=2::[test] one%25%0Atwo"
