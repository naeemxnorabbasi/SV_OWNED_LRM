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
OVERLAY = ROOT / "docs/orchestration/backlog_status_overlay.yaml"

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
    "ST-OWNED-9-003": (
        "test_sv_m5_312_owned_always_comb_procedural_metadata",
        "LRM-ALWAYS-COMB",
        "test_sv_m5_312_owned_always_comb_procedural_metadata",
        "9.2",
        "OWNED-CH9-003",
    ),
    "ST-OWNED-9-004": (
        "test_sv_m5_109_sim_always_comb_from_owned_ir",
        "LRM-ALWAYS-COMB-STATEMENT-SIM",
        "test_sv_m5_109_sim_always_comb_from_owned_ir",
        "9.2.2",
        "OWNED-CH9-004",
    ),
    "ST-OWNED-9-005": (
        "test_sv_m5_313_owned_always_ff_owned",
        "LRM-ALWAYS-FF",
        "test_sv_m5_313_owned_always_ff_owned",
        "9.4",
        "OWNED-CH9-005",
    ),
    "ST-OWNED-9-006": (
        "test_sv_m5_244_case_arm_if_expr_guard_owned",
        "LRM-CASE-ARM-IF-EXPR-GUARD",
        "test_sv_m5_244_case_arm_if_expr_guard_owned",
        "9.4.1",
        "OWNED-CH9-006",
    ),
    "ST-OWNED-9-007": (
        "test_sv_m5_143_always_comb_case_labels_owned",
        "LRM-CASE-ENDCASE-PARSE",
        "test_sv_m5_143_always_comb_case_labels_owned",
        "9.4.1",
        "OWNED-CH9-007",
    ),
    "ST-OWNED-9-008": (
        "test_sv_m5_143_always_comb_case_labels_owned",
        "LRM-CASE-LABEL-IR",
        "test_sv_m5_143_always_comb_case_labels_owned",
        "9.4.1",
        "OWNED-CH9-008",
    ),
    "ST-OWNED-9-009": (
        "test_sv_m5_153_nested_case_pipe_labels_owned",
        "LRM-CASE-LABEL-PATH",
        "test_sv_m5_153_nested_case_pipe_labels_owned",
        "9.4.1",
        "OWNED-CH9-009",
    ),
    "ST-OWNED-9-011": (
        "test_sv_m5_147_comb_if_guard_metadata_owned",
        "LRM-COMB-IF-GUARD-IR",
        "test_sv_m5_147_comb_if_guard_metadata_owned",
        "9.2.1",
        "OWNED-CH9-011",
    ),
    "ST-OWNED-9-012": (
        "test_sv_m5_117_sim_unified_comb_plus_ff_owned_ir",
        "LRM-COMB-PLUS-FF-RTL",
        "test_sv_m5_117_sim_unified_comb_plus_ff_owned_ir",
        "9.2",
        "OWNED-CH9-012",
    ),
    "ST-OWNED-9-015": (
        "test_sv_m5_134_nba_if_guard_export_owned",
        "LRM-ELSE-IF-CHAIN",
        "test_sv_m5_134_nba_if_guard_export_owned",
        "9.2.1",
        "OWNED-CH9-015",
    ),
    "ST-OWNED-9-016": (
        "test_sv_m5_122_sim_region_scheduled_detect_owned_ir",
        "LRM-EVENT-REGION-ORDER",
        "test_sv_m5_122_sim_region_scheduled_detect_owned_ir",
        "9",
        "OWNED-CH9-016",
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
  - Owned backend satisfies clause with registered M5 evidence.

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
    "ST-OWNED-9-003": ("always_comb procedural metadata", "always_comb"),
    "ST-OWNED-9-004": ("always_comb XOR sim statement-backed comb", "always_comb"),
    "ST-OWNED-9-005": ("always_ff", "always_ff"),
    "ST-OWNED-9-006": ("case arm if_expr guard", "always_comb_case_arm_if_expr"),
    "ST-OWNED-9-007": ("case/endcase in always_comb", "always_comb_case_mux"),
    "ST-OWNED-9-008": ("case_label metadata", "always_comb_case_mux"),
    "ST-OWNED-9-009": ("hierarchical case_label paths", "always_comb_nested_case"),
    "ST-OWNED-9-011": ("comb if_pos/if_neg guard metadata", "always_comb_if_en"),
    "ST-OWNED-9-012": ("comb_plus_ff corpus", "comb_plus_ff"),
    "ST-OWNED-9-015": ("else if chain in always bodies", "always_ff"),
    "ST-OWNED-9-016": ("active region order comb before clocked", "comb_plus_ff"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("st_id", nargs="?", help="ST-OWNED-* id")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run all registered tranches not yet completed in overlay",
    )
    args = parser.parse_args()
    if args.batch:
        overlay = yaml.safe_load(OVERLAY.read_text(encoding="utf-8")) if OVERLAY.is_file() else {}
        done = set((overlay.get("status_by_id") or {}).keys())
        failed = 0
        for st_id in sorted(TRANCHES.keys()):
            if st_id in done and (overlay.get("status_by_id") or {}).get(st_id) == "completed":
                continue
            print(f"\n######## {st_id} ########")
            if main_for(st_id) != 0:
                failed += 1
        return 1 if failed else 0
    if not args.st_id:
        parser.error("st_id or --batch required")
    return main_for(args.st_id)


def main_for(st_id: str) -> int:
    if st_id not in TRANCHES:
        print(f"No registered tranche for {st_id}", file=sys.stderr)
        return 1
    expr, lrm_id, test_id, lrm_section, batch = TRANCHES[st_id]
    title, stem = CONTRACT_META.get(st_id, (lrm_id, "feature_tests"))
    print(f"== pytest {expr} ==")
    run_pytest(expr)
    print(f"== promote {lrm_id} (section {lrm_section}) ==")
    promote_index(lrm_id, test_id, lrm_section, batch)
    update_matrix(lrm_id, test_id, lrm_section)
    write_contract(st_id, lrm_id, test_id, title, stem)
    mark_complete(st_id)
    print(f"OK: {st_id} tranche complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
