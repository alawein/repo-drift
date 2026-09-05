"""stale_config — flag framework config files when the framework isn't installed.

A config file like `capacitor.config.ts` is dead weight if `@capacitor/core`
isn't actually in package.json — the file ships, but nothing reads it. This
is a common sign that a configuration file is no longer used.

DEFAULT_CONFIG_MAP lists `<config-file>` → list of acceptable required
packages (ANY one of which counts as "installed"). Users can extend or
override per-repo via `.drift-rules.yaml`:

  detector_config:
    stale_config:
      config_map:
        my-tool.config.js: [my-tool, my-tool-fork]
        capacitor.config.ts: []   # disable a built-in entry

An empty required-deps list means "don't enforce this config" — useful when
a config file is intentionally retained for some other reason.
"""

from __future__ import annotations

import json
from pathlib import Path

from repo_drift.finding import Finding

DEFAULT_CONFIG_MAP: dict[str, list[str]] = {
    # Capacitor
    "capacitor.config.ts": ["@capacitor/core"],
    "capacitor.config.js": ["@capacitor/core"],
    "capacitor.config.json": ["@capacitor/core"],
    # Next.js
    "next.config.js": ["next"],
    "next.config.mjs": ["next"],
    "next.config.ts": ["next"],
    # Vite
    "vite.config.js": ["vite"],
    "vite.config.ts": ["vite"],
    "vite.config.mjs": ["vite"],
    # Tailwind
    "tailwind.config.js": ["tailwindcss"],
    "tailwind.config.ts": ["tailwindcss"],
    "tailwind.config.mjs": ["tailwindcss"],
    "tailwind.config.cjs": ["tailwindcss"],
    # Astro / Nuxt / SvelteKit / Remix
    "astro.config.mjs": ["astro"],
    "astro.config.ts": ["astro"],
    "nuxt.config.ts": ["nuxt"],
    "nuxt.config.js": ["nuxt"],
    "svelte.config.js": ["svelte", "@sveltejs/kit"],
    "remix.config.js": ["@remix-run/dev"],
    # Testing
    "playwright.config.ts": ["@playwright/test"],
    "playwright.config.js": ["@playwright/test"],
    "vitest.config.ts": ["vitest"],
    "vitest.config.js": ["vitest"],
    "jest.config.js": ["jest"],
    "jest.config.ts": ["jest"],
    # Other
    "tsup.config.ts": ["tsup"],
    "rollup.config.js": ["rollup"],
    "rollup.config.ts": ["rollup"],
    "webpack.config.js": ["webpack"],
}

_NPM_DEP_KEYS = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
)


def detect(repo_root: Path, config: dict) -> list[Finding]:
    config_map = dict(DEFAULT_CONFIG_MAP)
    config_map.update(config.get("config_map") or {})

    deps = _read_npm_deps(repo_root / "package.json")
    if deps is None:
        return []  # no manifest to compare against

    findings: list[Finding] = []
    for config_file, required in config_map.items():
        if not required:
            continue  # explicitly disabled
        if not (repo_root / config_file).is_file():
            continue
        if any(pkg in deps for pkg in required):
            continue
        required_str = " | ".join(required)
        findings.append(
            Finding(
                detector="stale_config",
                file=Path(config_file),
                line=None,
                message=(
                    f"{config_file} is present but none of [{required_str}] is in package.json"
                ),
                fix_hint=(
                    f"`npm install {required[0]}` if you intend to use it, "
                    f"otherwise delete {config_file}"
                ),
            )
        )
    return findings


def _read_npm_deps(path: Path) -> set[str] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    deps: set[str] = set()
    for key in _NPM_DEP_KEYS:
        section = data.get(key) or {}
        if isinstance(section, dict):
            deps.update(section.keys())
    return deps
