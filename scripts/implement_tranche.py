#!/usr/bin/env python3
"""Run registered implement tranches (pytest + index promotion + overlay complete)."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WS = yaml.safe_load((ROOT / "workspace.yaml").read_text(encoding="utf-8"))
PRODUCT = (ROOT / WS["repos"]["product"]).resolve()
SPEC = (ROOT / WS["repos"]["spec_root"]).resolve()
INDEX = SPEC / "SV_SPEC" / "lrm_clause_index.yaml"
MATRIX = PRODUCT / "docs/compliance/LRM_COVERAGE_MATRIX.md"
PICKER = ROOT / "scripts/pick_next_owned_task.py"

# st_id -> (pytest -k, lrm_clause_id, m5_test_id, lrm_section filter, index batch)
TrancheSpec = tuple[str, str, str, str | None, str]
TRANCHES: dict[str, TrancheSpec] = {
    "ST-OWNED-9-001": (
        "test_sv_m5_310_owned_active_clocked_nba_after_posedge",
        "LRM-ACTIVE-CLOCKED-REGION-SIM",
        "test_sv_m5_310_owned_active_clocked_nba_after_posedge",
        "9.3",
        "OWNED-CH9-001",
    ),
    "ST-OWNED-9-002": (
        "test_sv_m5_311_owned_always_comb_owned",
        "LRM-ALWAYS-COMB",
        "test_sv_m5_311_owned_always_comb_owned",
        "9.4",
        "OWNED-CH9-002",
    ),
}


def run_pytest(expr: str) -> None:
    venv = PRODUCT / ".venv/bin/python"
    py = str(venv) if venv.is_file() else sys.executable
    proc = subprocess.run(
        [py, "-m", "pytest", "tests/conformance/test_sv_matrix.py", "-k", expr, "-q"],
        cwd=PRODUCT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"pytest failed:\n{proc.stdout}\n{proc.stderr}")


def promote_index(lrm_id: str, test_id: str, lrm_section: str | None, batch: str) -> None:
    data = yaml.safe_load(INDEX.read_text(encoding="utf-8"))
    matched = False
    for clause in data.get("clauses") or []:
        if clause.get("id") != lrm_id:
            continue
        if lrm_section is not None and str(clause.get("lrm_section")) != lrm_section:
            continue
        clause["support_status"] = "supported"
        clause["backend"] = "owned"
        clause["batch"] = batch
        tests = list(clause.get("test_ids") or [])
        if test_id not in tests:
            tests.append(test_id)
        clause["test_ids"] = tests
        matched = True
        break
    if not matched:
        raise SystemExit(f"clause not found: {lrm_id} section={lrm_section}")
    INDEX.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def update_matrix(lrm_id: str, test_id: str, lrm_section: str | None) -> None:
    if not MATRIX.is_file():
        return
    text = MATRIX.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        if not line.startswith(f"| {lrm_id} |"):
            out.append(line)
            continue
        if lrm_section is not None and f"| {lrm_section} |" not in line:
            out.append(line)
            continue
        parts = line.split("|")
        if len(parts) < 8:
            out.append(line)
            continue
        parts[4] = " supported "
        parts[5] = " owned "
        existing = parts[6].strip().strip("`")
        tests = [t.strip() for t in existing.split(",") if t.strip()]
        if test_id not in tests:
            tests.append(test_id)
        parts[6] = f" `{', '.join(tests)}` "
        out.append("|".join(parts))
    MATRIX.write_text("\n".join(out) + "\n", encoding="utf-8")


def mark_complete(st_id: str) -> None:
    subprocess.run(
        [sys.executable, str(PICKER), "--apply-complete", st_id],
        check=True,
        cwd=ROOT,
    )


def write_contract(st_id: str, lrm_id: str, test_id: str, title: str, stem: str) -> None:
    path = ROOT / "contracts" / f"{st_id}.yaml"
    path.write_text(
        f"""schema_version: "1.0"
st_id: {st_id}
lrm_clause_id: {lrm_id}
title: {title}
status: completed

owned_must:
  - Owned C++ parses always_comb and exports AlwaysComb procedural IR.
  - scheduling_region active_comb with continuous_assign statement bodies.

tests:
  m5_test_id: {test_id}
  feature_test_stem: {stem}

promotion:
  from_status: partial
  to_status: supported
  completed: true
""",
        encoding="utf-8",
    )


CONTRACT_META: dict[str, tuple[str, str]] = {
    "ST-OWNED-9-001": ("active_clocked region NBA after posedge", "comb_plus_ff"),
    "ST-OWNED-9-002": ("always_comb", "always_comb"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("st_id", help="ST-OWNED-* id")
    args = parser.parse_args()
    if args.st_id not in TRANCHES:
        print(f"No registered tranche for {args.st_id}", file=sys.stderr)
        return 1
    expr, lrm_id, test_id, lrm_section, batch = TRANCHES[args.st_id]
    title, stem = CONTRACT_META.get(args.st_id, (lrm_id, "feature_tests"))
    print(f"== pytest {expr} ==")
    run_pytest(expr)
    print(f"== promote {lrm_id} (section {lrm_section}) ==")
    promote_index(lrm_id, test_id, lrm_section, batch)
    update_matrix(lrm_id, test_id, lrm_section)
    write_contract(args.st_id, lrm_id, test_id, title, stem)
    mark_complete(args.st_id)
    print(f"OK: {args.st_id} tranche complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
