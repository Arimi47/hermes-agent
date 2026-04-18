"""Merge a git-tracked seed config into the persisted config.yaml.

Seed wins for every key except model.default and model.provider, which the
dashboard and `hermes model` / codex_login.py (respectively) own at runtime.
The merge runs once per container boot, right before the admin server starts.

Usage:
    python merge_config.py <seed_yaml> <target_yaml>
"""

import sys
from pathlib import Path

import yaml


def merge(seed_path: Path, target_path: Path) -> None:
    seed = yaml.safe_load(seed_path.read_text()) or {}
    existing: dict = {}
    if target_path.exists():
        existing = yaml.safe_load(target_path.read_text()) or {}

    merged = dict(seed)

    # Preserve runtime-owned fields from the existing file if set.
    existing_model = existing.get("model") or {}
    if existing_model.get("default") or existing_model.get("provider"):
        merged_model = dict(merged.get("model") or {})
        if existing_model.get("default"):
            merged_model["default"] = existing_model["default"]
        if existing_model.get("provider"):
            merged_model["provider"] = existing_model["provider"]
        merged["model"] = merged_model

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(yaml.safe_dump(merged, sort_keys=False))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    merge(Path(sys.argv[1]), Path(sys.argv[2]))
