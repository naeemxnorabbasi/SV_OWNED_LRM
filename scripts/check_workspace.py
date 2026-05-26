#!/usr/bin/env python3
"""Validate SV_OWNED_LRM workspace paths and generated backlog freshness."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ws = yaml.safe_load((ROOT / "workspace.yaml").read_text(encoding="utf-8"))
    errors: list[str] = []

    for key, rel in ws.get("repos", {}).items():
        if key.startswith("_"):
            continue
        path = (ROOT / rel).resolve()
        if key.endswith("_index") or key.endswith("_root"):
            if not path.exists():
                errors.append(f"missing repo path {key}: {path}")
        elif key in ("product", "eval", "spec_root"):
            if not path.is_dir():
                errors.append(f"missing directory {key}: {path}")

    for label, rel in ws.get("inherit", {}).items():
        path = (ROOT / rel).resolve()
        if not path.is_file():
            errors.append(f"missing inherit {label}: {path}")

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_owned_backlog.py"), "--check"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        errors.append(f"backlog check failed:\n{proc.stderr or proc.stdout}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1

    print("OK: workspace paths and generated backlog")
    return 0


if __name__ == "__main__":
    sys.exit(main())
