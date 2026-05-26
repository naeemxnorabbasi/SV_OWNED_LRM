#!/usr/bin/env python3
"""Pick next ST-OWNED-* work from phase_backlog_owned.yaml (AP-01).

Priority: closeable chapter gates → active wave → chapter-9 weight → other pending.
Roadmap titles classify as defer_roadmap. Honors depends_on + backlog_status_overlay.yaml.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "docs" / "orchestration" / "phase_backlog_owned.yaml"
OVERLAY = ROOT / "docs" / "orchestration" / "backlog_status_overlay.yaml"
PROGRAM_STATE = ROOT / "docs" / "orchestration" / "program_state.yaml"
FILE_OWNERSHIP = ROOT / "docs" / "orchestration" / "FILE_OWNERSHIP.yaml"
GAP_SUMMARY = ROOT / "docs" / "orchestration" / "owned_gap_summary.yaml"
HANDOFF_PLAN = ROOT / "docs" / "plans" / "2026-05-28-owned-lrm-full-autopilot.md"
IMPLEMENT_TRANCHE = ROOT / "scripts" / "implement_tranche.py"


def registered_implement_ids() -> frozenset[str]:
    if not IMPLEMENT_TRANCHE.is_file():
        return frozenset()
    spec = importlib.util.spec_from_file_location("implement_tranche", IMPLEMENT_TRANCHE)
    if spec is None or spec.loader is None:
        return frozenset()
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tranches = getattr(mod, "TRANCHES", {})
    return frozenset(tranches.keys())


TERMINAL = frozenset({"completed", "deferred", "cancelled"})
ACTIVE_STATUSES = frozenset({"pending", "in_progress", "blocked"})


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_overlay() -> dict[str, str]:
    if not OVERLAY.is_file():
        return {}
    doc = load_yaml(OVERLAY)
    return dict(doc.get("status_by_id") or {})


def save_overlay(overlay: dict[str, str]) -> None:
    doc = {
        "version": 1,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status_by_id": dict(sorted(overlay.items())),
    }
    OVERLAY.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def effective_status(task: dict[str, Any], overlay: dict[str, str]) -> str:
    return overlay.get(task["id"], task.get("status", "pending"))


def apply_overlay_to_tasks(tasks: list[dict[str, Any]], overlay: dict[str, str]) -> None:
    for t in tasks:
        if t["id"] in overlay:
            t["status"] = overlay[t["id"]]


def is_gate(task_id: str) -> bool:
    return "GATE" in task_id


def is_clause_task(task_id: str) -> bool:
    return task_id.startswith("ST-OWNED-") and not is_gate(task_id) and not task_id.startswith("ST-W0-")


def chapter_from_clause_id(task_id: str) -> str | None:
    m = re.match(r"ST-OWNED-(\d+)-\d+$", task_id)
    return m.group(1) if m else None


def gate_chapter(task: dict[str, Any]) -> str | None:
    meta = task.get("metadata") or {}
    ch = meta.get("chapter")
    return str(ch) if ch is not None else None


def is_chapter_gate_id(dep_id: str) -> bool:
    return dep_id.startswith("ST-OWNED-GATE-CH")


def deps_satisfied(task: dict[str, Any], status_by_id: dict[str, str]) -> bool:
    """Clause work is blocked only by real deps (e.g. W0), not open chapter gates."""
    for dep in task.get("depends_on") or []:
        if is_chapter_gate_id(dep):
            continue
        st = status_by_id.get(dep, "pending")
        if st not in TERMINAL:
            return False
    return True


def is_roadmap(task: dict[str, Any]) -> bool:
    return "(roadmap)" in (task.get("title") or "").lower()


def classify(task: dict[str, Any]) -> str:
    if is_gate(task["id"]):
        return "close_gate"
    if is_roadmap(task):
        return "defer_roadmap"
    return "implement"


def clause_tasks_for_gate(gate_id: str, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in tasks if gate_id in (t.get("depends_on") or []) and is_clause_task(t["id"])]


def gate_ready_to_close(
    gate: dict[str, Any], tasks: list[dict[str, Any]], status_by_id: dict[str, str]
) -> bool:
    st = status_by_id.get(gate["id"], gate.get("status", "pending"))
    if st != "pending":
        return False
    if not deps_satisfied(gate, status_by_id):
        return False
    children = clause_tasks_for_gate(gate["id"], tasks)
    if not children:
        return True
    return all(status_by_id.get(c["id"], c.get("status")) in TERMINAL for c in children)


def chapter_weight(ch: str | None, summary: dict[str, Any]) -> int:
    if not ch:
        return 0
    by_ch = summary.get("by_chapter") or {}
    return int(by_ch.get(ch, by_ch.get(str(ch), 0)))


def active_wave_boost(task: dict[str, Any], active_phase: str) -> int:
    # owned-lrm-wave1-active → prefer chapter 11 closure then chapter 9
    if "wave1" in active_phase and chapter_from_clause_id(task["id"]) in ("9", "11"):
        return 500
    return 0


def pods_conflict(pods: list[str], ownership: dict[str, Any]) -> bool:
    blocked = ownership.get("blocked_pairs") or []
    for i, a in enumerate(pods):
        for b in pods[i + 1 :]:
            if [a, b] in blocked or [b, a] in blocked:
                return True
    return False


def task_pod(task: dict[str, Any]) -> str:
    meta = task.get("metadata") or {}
    return str(meta.get("pod") or "sema")


def score_task(
    task: dict[str, Any],
    action: str,
    program: dict[str, Any],
    summary: dict[str, Any],
) -> int:
    score = 0
    active = program.get("active_phase") or ""
    ch = chapter_from_clause_id(task["id"]) or gate_chapter(task)

    if action == "close_gate":
        score += 10_000
    elif action == "defer_roadmap":
        score += 8_000
        if ch == "11":
            score += 2_000
    else:
        score += 1_000
        score += chapter_weight(ch, summary) * 10
        score += active_wave_boost(task, active)

    if action == "implement" and ch == "9":
        score += 5_000

    m = re.search(r"-(\d+)$", task["id"])
    if m:
        score -= int(m.group(1))

    return score


def pick_candidates(
    tasks: list[dict[str, Any]],
    status_by_id: dict[str, str],
    program: dict[str, Any],
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    picks: list[dict[str, Any]] = []

    for t in tasks:
        if not is_gate(t["id"]):
            continue
        if not gate_ready_to_close(t, tasks, status_by_id):
            continue
        if status_by_id.get(t["id"], t.get("status")) != "pending":
            continue
        picks.append(
            {
                "id": t["id"],
                "action": "close_gate",
                "title": t.get("title"),
                "track": t.get("track"),
                "metadata": t.get("metadata") or {},
                "score": score_task(t, "close_gate", program, summary),
            }
        )

    for t in tasks:
        tid = t["id"]
        st = status_by_id.get(tid, t.get("status", "pending"))
        if st not in ACTIVE_STATUSES:
            continue
        if is_gate(tid) or tid.startswith("ST-W0-"):
            continue
        if not deps_satisfied(t, status_by_id):
            continue
        action = classify(t)
        if (
            os.environ.get("OWNED_AUTOPILOT_AUTO") == "1"
            and action == "implement"
            and tid not in registered_implement_ids()
        ):
            continue
        picks.append(
            {
                "id": tid,
                "action": action,
                "title": t.get("title"),
                "track": t.get("track"),
                "metadata": t.get("metadata") or {},
                "deliverables": t.get("deliverables") or [],
                "verification": t.get("verification"),
                "score": score_task(t, action, program, summary),
            }
        )

    picks.sort(key=lambda p: (-p["score"], p["id"]))
    return picks


def select_batch(
    candidates: list[dict[str, Any]],
    tasks_by_id: dict[str, dict[str, Any]],
    ownership: dict[str, Any],
    max_n: int,
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    selected: list[dict[str, Any]] = []
    pods_used: list[str] = []
    for cand in candidates:
        if len(selected) >= max_n:
            break
        if cand["action"] == "close_gate":
            selected.append(cand)
            continue
        t = tasks_by_id.get(cand["id"])
        if not t:
            continue
        pod = task_pod(t)
        trial = pods_used + [pod]
        if pods_conflict(trial, ownership):
            continue
        selected.append(cand)
        pods_used.append(pod)
    return selected


def write_handoff(path: Path, batch: list[dict[str, Any]], program: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Autopilot handoff",
        "",
        f"**Generated:** {now}",
        f"**Autopilot level:** {(program.get('autopilot') or {}).get('level', 3)}",
        f"**Plan:** `{HANDOFF_PLAN.relative_to(ROOT)}`",
        "",
    ]
    if not batch:
        lines.extend(
            [
                "## Status",
                "",
                "No eligible tasks. Regenerate backlog or update overlay / index promotions.",
                "",
            ]
        )
    else:
        for i, pick in enumerate(batch, start=1):
            meta = pick.get("metadata") or {}
            lines.extend(
                [
                    f"## Task {i}: `{pick['id']}`",
                    "",
                    f"- **Action:** `{pick['action']}`",
                    f"- **Title:** {pick.get('title', '')}",
                    f"- **Track:** {pick.get('track', '')}",
                    f"- **LRM clause:** `{meta.get('lrm_clause_id', '—')}`",
                    f"- **Pod:** `{meta.get('pod', '—')}`",
                    f"- **Score:** {pick.get('score', 0)}",
                    "",
                ]
            )
            if pick["action"] == "implement":
                lines.append("### Deliverables")
                lines.append("")
                for d in pick.get("deliverables") or []:
                    lines.append(f"- {d}")
                lines.append("")
                lines.append("### Verification")
                lines.append("")
                lines.append(f"- {pick.get('verification', 'run_autopilot_gate.sh')}")
                lines.append("")
                lines.append("### Agent steps")
                lines.append("")
                lines.append("1. Copy `schemas/clause_factory_contract.yaml` → `contracts/<ST-ID>.yaml` and fill.")
                lines.append("2. Implement only in pod paths from `FILE_OWNERSHIP.yaml`.")
                lines.append("3. Add feature test stem + M5 test in `sv_frontend`.")
                lines.append("4. Promote `lrm_clause_index.yaml` + matrix; run gates.")
                lines.append("5. Commit all three repos with footer `Owned-Tranche: <ST-ID>`.")
                lines.append("")
            elif pick["action"] == "defer_roadmap":
                lines.append("### Agent steps")
                lines.append("")
                lines.append("1. Do **not** set `support_status: supported` in the index.")
                lines.append("2. Record deferral in contract stub if useful.")
                lines.append("3. Run: `python3 scripts/pick_next_owned_task.py --apply-defer <ST-ID>`")
                lines.append("4. Commit overlay + program_state when batch of defers done.")
                lines.append("")
            elif pick["action"] == "close_gate":
                lines.append("### Agent steps")
                lines.append("")
                lines.append("1. Confirm all chapter clause tasks are `completed` or `deferred`.")
                lines.append("2. Run: `python3 scripts/pick_next_owned_task.py --apply-complete <ST-ID>`")
                lines.append("3. Update `program_state.yaml` chapter note.")
                lines.append("")

    lines.extend(
        [
            "## Gates (after implement)",
            "",
            "```bash",
            "cd ~/sv_frontend && source .venv/bin/activate && bash scripts/run_autopilot_gate.sh",
            "```",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def update_program_state(batch: list[dict[str, Any]], overlay: dict[str, str]) -> None:
    prog = load_yaml(PROGRAM_STATE)
    auto = dict(prog.get("autopilot") or {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    auto["level"] = auto.get("level", 3)
    auto["last_tick_at"] = now
    auto["last_pick_ids"] = [p["id"] for p in batch]
    auto["last_pick_actions"] = [p["action"] for p in batch]
    auto["picker_script"] = "scripts/pick_next_owned_task.py"
    auto["driver_script"] = "scripts/run_owned_autopilot.sh"
    if batch:
        auto["next_pick"] = batch[0]
    else:
        auto.pop("next_pick", None)
    prog["autopilot"] = auto
    prog["updated"] = now[:10]
    if batch:
        actions = [f"{p['id']}: {p['action']}" for p in batch[:3]]
        prog["next_orchestrator_actions"] = actions + (prog.get("next_orchestrator_actions") or [])[3:]
    PROGRAM_STATE.write_text(
        yaml.safe_dump(prog, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print pick JSON to stdout")
    parser.add_argument("--batch", type=int, default=None, help="Max parallel picks (default: program_state)")
    parser.add_argument("--write-handoff", type=Path, metavar="PATH")
    parser.add_argument("--update-program-state", action="store_true")
    parser.add_argument("--apply-defer", metavar="ST_ID")
    parser.add_argument("--apply-complete", metavar="ST_ID")
    args = parser.parse_args()

    overlay = load_overlay()

    if args.apply_defer:
        overlay[args.apply_defer] = "deferred"
        save_overlay(overlay)
        print(f"OK: {args.apply_defer} -> deferred")
        return 0

    if args.apply_complete:
        overlay[args.apply_complete] = "completed"
        save_overlay(overlay)
        print(f"OK: {args.apply_complete} -> completed")
        return 0

    backlog = load_yaml(BACKLOG)
    tasks: list[dict[str, Any]] = backlog.get("subtasks") or []
    apply_overlay_to_tasks(tasks, overlay)

    status_by_id = {t["id"]: t.get("status", "pending") for t in tasks}
    program = load_yaml(PROGRAM_STATE)
    summary = load_yaml(GAP_SUMMARY) if GAP_SUMMARY.is_file() else {}
    ownership = load_yaml(FILE_OWNERSHIP)

    max_n = args.batch
    if max_n is None:
        max_n = int((program.get("parallel_dispatch") or {}).get("max", 1))

    candidates = pick_candidates(tasks, status_by_id, program, summary)
    tasks_by_id = {t["id"]: t for t in tasks}
    batch = select_batch(candidates, tasks_by_id, ownership, max_n)

    if args.json:
        print(json.dumps({"picks": batch}, indent=2))

    if args.write_handoff:
        write_handoff(args.write_handoff, batch, program)

    if args.update_program_state:
        update_program_state(batch, overlay)

    if not args.json and not args.write_handoff:
        if not batch:
            print("No eligible tasks.")
            return 2
        for p in batch:
            print(f"{p['id']}\t{p['action']}\tscore={p['score']}")

    return 0 if batch else 2


if __name__ == "__main__":
    sys.exit(main())
