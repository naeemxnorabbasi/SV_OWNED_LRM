#!/usr/bin/env python3
"""Generate OWNED_WAVE_REGISTRY + phase_backlog_owned.yaml (ST-OWNED-* rows).

Reads lrm_clause_index.yaml via workspace.yaml. Safe to re-run (idempotent ids).
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "workspace.yaml"
OUT_REGISTRY = ROOT / "docs" / "orchestration" / "OWNED_WAVE_REGISTRY.yaml"
OUT_BACKLOG = ROOT / "docs" / "orchestration" / "phase_backlog_owned.yaml"
OUT_SUMMARY = ROOT / "docs" / "orchestration" / "owned_gap_summary.yaml"
OVERLAY = ROOT / "docs" / "orchestration" / "backlog_status_overlay.yaml"

POD_BY_CHAPTER: dict[str, str] = {
    "4": "sema",
    "5": "sema",
    "6": "sema",
    "7": "sema",
    "8": "sema",
    "9": "parser_always",
    "10": "lower",
    "11": "lower",
    "12": "parser_always",
    "13": "sema",
    "14": "sema",
    "15": "sema",
    "16": "parser_sva",
    "17": "sema",
    "18": "sema",
    "19": "sema",
    "20": "sema",
    "22": "parser_module",
    "23": "parser_module",
    "25": "parser_generate",
    "26": "parser_generate",
    "27": "parser_module",
    "34": "sema",
    "35": "sema",
}

POD_TO_TRACK: dict[str, str] = {
    "parser_tokens": "B",
    "parser_skip": "B",
    "parser_expr": "B",
    "parser_module": "B",
    "parser_generate": "B",
    "parser_always": "B",
    "parser_sva": "E",
    "sema": "B",
    "lower": "C",
    "lexer": "B",
    "preprocess": "B",
    "ir_export": "C",
    "sim": "D",
    "eval_corpus": "H",
    "tests_m5": "I",
    "conformance": "I",
    "lrm_indexer": "LRM",
    "orchestrator": "orchestrator",
}

CHAPTER_TITLES: dict[str, str] = {
    "9": "Procedural blocks",
    "16": "Assertions",
    "23": "Modules and hierarchy",
    "10": "Assignment patterns",
    "18": "Constraints",
    "27": "Configuration",
}


def load_workspace() -> dict:
    ws = yaml.safe_load(WORKSPACE.read_text(encoding="utf-8"))
    index_rel = ws["repos"]["lrm_clause_index"]
    index_path = (ROOT / index_rel).resolve()
    if not index_path.is_file():
        raise SystemExit(f"lrm_clause_index not found: {index_path}")
    ws["_index_path"] = index_path
    return ws


def chapter(section: str | None) -> str:
    if not section or section in ("—", "-", ""):
        return "misc"
    return section.split(".")[0]


def registry_id(ch: str, seq: int) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "", ch) or "misc"
    return f"OWNED-{safe}-{seq:03d}"


def st_id(registry_key: str) -> str:
    return registry_key.replace("OWNED-", "ST-OWNED-", 1)


def chapter_gate_id(ch: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "", ch) or "misc"
    return f"ST-OWNED-GATE-CH{safe}"


def is_gap(clause: dict) -> bool:
    if clause.get("support_status") in ("partial", "unsupported"):
        return True
    if clause.get("backend") != "owned":
        return True
    return False


def wave0_subtasks() -> list[dict]:
    """Platform tranches — Wave 0 (orchestrator umbrella)."""
    items = [
        ("ST-OWNED-GATE-W0", "Wave 0 platform gate", "orchestrator", "completed"),
        ("ST-W0-01", "Clause factory schema + example", "I", "completed"),
        ("ST-W0-02", "generate_owned_backlog.py + registry", "I", "completed"),
        ("ST-W0-03", "FILE_OWNERSHIP.yaml + check_workspace.py", "I", "completed"),
        ("ST-W0-04", "Parser TU split (parser_tokens.cpp)", "B", "completed"),
        ("ST-W0-05", "sema_context skeleton", "B", "completed"),
        ("ST-W0-06", "IR schema v3 preview + oracle farm inherit", "C", "completed"),
    ]
    out: list[dict] = []
    for sid, title, track, status in items:
        out.append(
            {
                "id": sid,
                "phase": "owned-lrm",
                "track": track,
                "title": title,
                "status": status,
                "depends_on": [],
                "verification": "docs/plans/OWNED_FULL_LRM_PROGRAM.md Wave 0",
                "agent": "generalPurpose",
            }
        )
    out[0]["depends_on"] = []
    for row in out[1:]:
        row["depends_on"] = ["ST-OWNED-GATE-W0"]
    return out


def build_units(clauses: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    gaps = [c for c in clauses if is_gap(c)]
    by_ch: dict[str, list[dict]] = defaultdict(list)
    for c in gaps:
        by_ch[chapter(c.get("lrm_section"))].append(c)

    units: list[dict] = []
    for ch in sorted(by_ch.keys(), key=lambda x: (x == "misc", x)):
        for i, c in enumerate(sorted(by_ch[ch], key=lambda x: x.get("id", "")), start=1):
            rid = registry_id(ch, i)
            pod = POD_BY_CHAPTER.get(ch, "sema")
            units.append(
                {
                    "id": rid,
                    "st_id": st_id(rid),
                    "lrm_clause_id": c.get("id"),
                    "lrm_section": c.get("lrm_section"),
                    "title": c.get("title"),
                    "support_status": c.get("support_status"),
                    "backend": c.get("backend"),
                    "pod": pod,
                    "chapter": ch,
                    "status": "pending",
                }
            )
    return units, by_ch


def chapter_gates(by_ch: dict[str, list[dict]]) -> list[dict]:
    gates: list[dict] = []
    for ch in sorted(by_ch.keys(), key=lambda x: (x == "misc", x)):
        gid = chapter_gate_id(ch)
        title = CHAPTER_TITLES.get(ch, f"Chapter {ch}")
        gates.append(
            {
                "id": gid,
                "phase": "owned-lrm",
                "track": "orchestrator",
                "title": f"Chapter gate — {title} ({len(by_ch[ch])} clauses)",
                "status": "pending",
                "depends_on": ["ST-OWNED-GATE-W0"],
                "verification": f"all ST-OWNED-{ch}-* in chapter {ch} completed",
                "agent": "orchestrator",
                "metadata": {"chapter": ch, "clause_count": len(by_ch[ch])},
            }
        )
    return gates


def clause_subtasks(units: list[dict]) -> list[dict]:
    tasks: list[dict] = []
    for u in units:
        ch = u["chapter"]
        gid = chapter_gate_id(ch)
        track = POD_TO_TRACK.get(u["pod"], "B")
        title = u.get("title") or u["lrm_clause_id"]
        tasks.append(
            {
                "id": u["st_id"],
                "phase": "owned-lrm",
                "track": track,
                "title": f"OWNED: {title}",
                "status": "pending",
                "depends_on": [gid],
                "deliverables": [
                    f"contracts/{u['st_id']}.yaml",
                    "sv_frontend: owned implementation",
                    f"SV_UPF_SPEC: promote {u['lrm_clause_id']} to supported/owned",
                ],
                "verification": (
                    f"slang parity >=0.99; lrm_clause_id={u['lrm_clause_id']}; "
                    "run_autopilot_gate.sh"
                ),
                "agent": "generalPurpose",
                "metadata": {
                    "registry_id": u["id"],
                    "lrm_clause_id": u["lrm_clause_id"],
                    "lrm_section": u["lrm_section"],
                    "pod": u["pod"],
                    "from_status": u["support_status"],
                    "from_backend": u["backend"],
                },
            }
        )
    return tasks


def write_registry(ws: dict, clauses: list[dict], units: list[dict], by_ch: dict) -> None:
    summary = {
        "total_indexed": len(clauses),
        "gap_units": len(units),
        "by_chapter": {ch: len(by_ch[ch]) for ch in sorted(by_ch.keys())},
        "by_status": {
            s: sum(1 for c in clauses if c.get("support_status") == s)
            for s in ("supported", "partial", "unsupported", "delegated")
        },
    }
    doc = {
        "version": 1,
        "workspace": "SV_OWNED_LRM",
        "generated_from": str(ws["_index_path"]),
        "program": "docs/plans/OWNED_FULL_LRM_PROGRAM.md",
        "summary": summary,
        "units": [
            {
                "id": u["id"],
                "st_id": u["st_id"],
                "lrm_clause_id": u["lrm_clause_id"],
                "lrm_section": u["lrm_section"],
                "title": u["title"],
                "support_status": u["support_status"],
                "backend": u["backend"],
                "pod": u["pod"],
                "chapter": u["chapter"],
                "status": u["status"],
                "contract_template": "schemas/clause_factory_contract.yaml",
            }
            for u in units
        ],
    }
    OUT_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    OUT_REGISTRY.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    OUT_SUMMARY.write_text(yaml.safe_dump(summary, sort_keys=True), encoding="utf-8")


def load_status_overlay() -> dict[str, str]:
    if not OVERLAY.is_file():
        return {}
    doc = yaml.safe_load(OVERLAY.read_text(encoding="utf-8")) or {}
    return dict(doc.get("status_by_id") or {})


def apply_status_overlay(subtasks: list[dict], overlay: dict[str, str]) -> None:
    for row in subtasks:
        if row["id"] in overlay:
            row["status"] = overlay[row["id"]]


def write_backlog(wave0: list[dict], gates: list[dict], clauses: list[dict]) -> None:
    header = {
        "version": 1,
        "program": "SV_OWNED_LRM",
        "description": (
            "Generated ST-OWNED-* backlog for full owned IEEE 1800. "
            "Regenerate: python3 scripts/generate_owned_backlog.py"
        ),
        "do_not_edit_ids": True,
    }
    subtasks = wave0 + gates + clauses
    apply_status_overlay(subtasks, load_status_overlay())
    doc = {**header, "subtasks": subtasks}
    OUT_BACKLOG.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def check() -> None:
    ws = load_workspace()
    data = yaml.safe_load(ws["_index_path"].read_text(encoding="utf-8"))
    clauses = data.get("clauses", [])
    units, _ = build_units(clauses)
    if not OUT_REGISTRY.is_file() or not OUT_BACKLOG.is_file():
        raise SystemExit("missing generated files — run without --check")
    reg = yaml.safe_load(OUT_REGISTRY.read_text(encoding="utf-8"))
    backlog = yaml.safe_load(OUT_BACKLOG.read_text(encoding="utf-8"))
    n_reg = len(reg.get("units", []))
    n_st = sum(1 for s in backlog.get("subtasks", []) if s["id"].startswith("ST-OWNED-") and "GATE" not in s["id"])
    if n_reg != len(units) or n_st != len(units):
        raise SystemExit(f"stale: registry={n_reg} st={n_st} expected={len(units)}")
    print(f"OK: {len(units)} gap clauses, {len(backlog['subtasks'])} backlog rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
        return

    ws = load_workspace()
    data = yaml.safe_load(ws["_index_path"].read_text(encoding="utf-8"))
    clauses = data.get("clauses", [])
    units, by_ch = build_units(clauses)
    wave0 = wave0_subtasks()
    gates = chapter_gates(by_ch)
    clause_tasks = clause_subtasks(units)

    write_registry(ws, clauses, units, by_ch)
    write_backlog(wave0, gates, clause_tasks)

    print(f"Wrote {OUT_REGISTRY} ({len(units)} units)")
    print(f"Wrote {OUT_BACKLOG} ({len(wave0) + len(gates) + len(clause_tasks)} subtasks)")
    print(f"  wave0={len(wave0)} chapter_gates={len(gates)} clause_tasks={len(clause_tasks)}")


if __name__ == "__main__":
    main()
