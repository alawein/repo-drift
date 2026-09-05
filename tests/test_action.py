from __future__ import annotations

from pathlib import Path

import yaml

ACTION_PATH = Path(__file__).resolve().parents[1] / "action.yml"


def test_composite_action_is_self_contained_and_token_free() -> None:
    action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
    assert action["runs"]["using"] == "composite"
    rendered = ACTION_PATH.read_text(encoding="utf-8").lower()
    assert "github_token" not in rendered
    assert "secrets." not in rendered
    assert "git+https" not in rendered
    assert "$github_action_path" in rendered
    assert "repo-drift" in rendered
