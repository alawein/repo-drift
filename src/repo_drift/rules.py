"""Per-repo rules.yaml loader for the drift module.

A rules file lives at the repo root (default name `.drift-rules.yaml`) and
controls two things:
  - opt_out: list of detector names that should not run in this repo
  - detector_config: per-detector config dicts forwarded to detector callables

Missing file is not an error — defaults are permissive (all detectors enabled,
no per-detector config).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_ALLOWED_KEYS = frozenset({"opt_out", "detector_config"})


@dataclass(frozen=True)
class Rules:
    opt_out: tuple[str, ...] = ()
    detector_config: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Rules:
        if not path.exists():
            return cls()

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            # TRY004 wants TypeError for an isinstance failure, but ValueError
            # here is the tested public contract (test_drift_rules.py asserts
            # it); changing the exception type is a breaking change, not a
            # lint fix.
            raise ValueError(  # noqa: TRY004
                f"{path}: top-level rules document must be a mapping, got {type(raw).__name__}"
            )

        unknown = set(raw) - _ALLOWED_KEYS
        if unknown:
            raise ValueError(
                f"{path}: unknown top-level keys {sorted(unknown)}; "
                f"allowed: {sorted(_ALLOWED_KEYS)}"
            )

        opt_out_raw = raw.get("opt_out", [])
        if not isinstance(opt_out_raw, list):
            raise ValueError(  # noqa: TRY004 - tested contract, see above
                f"{path}: opt_out must be a list, got {type(opt_out_raw).__name__}"
            )

        detector_config_raw = raw.get("detector_config", {}) or {}
        if not isinstance(detector_config_raw, dict):
            raise ValueError(  # noqa: TRY004 - tested contract, see above
                f"{path}: detector_config must be a mapping, "
                f"got {type(detector_config_raw).__name__}"
            )

        return cls(
            opt_out=tuple(str(item) for item in opt_out_raw),
            detector_config={
                str(k): dict(v) if isinstance(v, dict) else {}
                for k, v in detector_config_raw.items()
            },
        )

    def is_enabled(self, detector: str) -> bool:
        return detector not in self.opt_out

    def config_for(self, detector: str) -> dict[str, Any]:
        return self.detector_config.get(detector, {})
