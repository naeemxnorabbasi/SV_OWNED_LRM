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
OVERLAY = ROOT / "docs/orchestration/backlog_status_overlay.yaml"
PICKER = ROOT / "scripts/pick_next_owned_task.py"

# st_id -> (pytest -k expression, lrm_clause_id, m5_test_id)
TRANCHES: dict[str, tuple[str, str, str]] = {
    "ST-OWNED-9-001": (
        "test_sv_m5_310_owned_active_clocked_nba_after_posedge",
        "LRM-ACTIVE-CLOCKED-REGION-SIM",
        "test_sv_m5_310_owned_active_clocked_nba_after_posedge",
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


def promote_index(lrm_id: str, test_id: str) -> None:
    data = yaml.safe_load(INDEX.read_text(encoding="utf-8"))
    for clause in data.get("clauses") or []:
        if clause.get("id") != lrm_id:
            continue
        clause["support_status"] = "supported"
        clause["backend"] = "owned"
        clause["batch"] = "OWNED-CH9-001"
        tests = list(clause.get("test_ids") or [])
        if test_id not in tests:
            tests.append(test_id)
        clause["test_ids"] = tests
        break
    else:
        raise SystemExit(f"clause not found: {lrm_id}")
    INDEX.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def update_matrix(lrm_id: str, test_id: str) -> None:
    if not MATRIX.is_file():
        return
    text = MATRIX.read_text(encoding="utf-8")
    row_re = re.compile(
        rf"^\| {re.escape(lrm_id)} \|.*?\| `([^`]*)` \|$",
        re.MULTILINE,
    )

    def repl(m: re.Match[str]) -> str:
        parts = m.group(0).split("|")
        if len(parts) < 7:
            return m.group(0)
        parts[4] = " supported "
        parts[5] = " owned "
        existing = parts[6].strip().strip("`")
        tests = [t.strip() for t in existing.split(",") if t.strip()]
        if test_id not in tests:
            tests.append(test_id)
        parts[6] = f" `{', '.join(tests)}` "
        return "|".join(parts)

    new_text, n = row_re.subn(repl, text, count=1)
    if n:
        MATRIX.write_text(new_text, encoding="utf-8")


def mark_complete(st_id: str) -> None:
    subprocess.run(
        [sys.executable, str(PICKER), "--apply-complete", st_id],
        check=True,
        cwd=ROOT,
    )


def write_contract(st_id: str, lrm_id: str, test_id: str) -> None:
    path = ROOT / "contracts" / f"{st_id}.yaml"
    path.write_text(
        f"""schema_version: "1.0"
st_id: {st_id}
lrm_clause_id: {lrm_id}
title: active_clocked region NBA after posedge
status: completed

owned_must:
  - AlwaysFF procedural IR tagged scheduling_region active_clocked.
  - Unified sim steps comb region then posedge + NBA in active_clocked region.

tests:
  m5_test_id: {test_id}
  feature_test_stem: comb_plus_ff

promotion:
  from_status: partial
  to_status: supported
  completed: true
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("st_id", help="ST-OWNED-* id")
    args = parser.parse_args()
    if args.st_id not in TRANCHES:
        print(f"No registered tranche for {args.st_id}", file=sys.stderr)
        return 1
    expr, lrm_id, test_id = TRANCHES[args.st_id]
    print(f"== pytest {expr} ==")
    run_pytest(expr)
    print(f"== promote {lrm_id} ==")
    promote_index(lrm_id, test_id)
    update_matrix(lrm_id, test_id)
    write_contract(args.st_id, lrm_id, test_id)
    mark_complete(args.st_id)
    print(f"OK: {args.st_id} tranche complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
