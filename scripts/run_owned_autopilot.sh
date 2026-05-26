#!/usr/bin/env bash
# AP-02: Owned-LRM autopilot driver — refresh backlog, pick, write handoff.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HANDOFF="${ROOT}/docs/orchestration/next_handoff.md"
BATCH=1

usage() {
  echo "Usage: $0 [--batch N] [--handoff PATH] [--pick-only] [--execute] [--auto [N]]"
  echo "  --execute   Run execute_autopilot_handoff.sh after pick (defer/close_gate)"
  echo "  --auto N    Repeat tick+execute up to N times until an implement pick stops"
  exit 1
}

PICK_ONLY=0
EXECUTE=0
AUTO_LOOPS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --batch) BATCH="$2"; shift 2 ;;
    --handoff) HANDOFF="$2"; shift 2 ;;
    --pick-only) PICK_ONLY=1; shift ;;
    --execute) EXECUTE=1; shift ;;
    --auto)
      if [[ "${2:-}" =~ ^[0-9]+$ ]]; then
        AUTO_LOOPS="$2"
        shift 2
      else
        AUTO_LOOPS=50
        shift
      fi
      EXECUTE=1
      ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

# shellcheck disable=SC1090
source "$ROOT/scripts/git_commit_env.sh" 2>/dev/null || true

run_execute() {
  bash "$ROOT/scripts/execute_autopilot_handoff.sh"
}

run_tick() {
  echo "== owned autopilot tick =="
  echo "== regenerate backlog =="
  python3 "$ROOT/scripts/generate_owned_backlog.py"
  python3 "$ROOT/scripts/generate_owned_backlog.py" --check

  echo "== workspace check =="
  python3 "$ROOT/scripts/check_workspace.py"

  echo "== pick next task(s) =="
  python3 "$ROOT/scripts/pick_next_owned_task.py" \
    --batch "$BATCH" \
    --write-handoff "$HANDOFF" \
    --update-program-state \
    --json
}

bump_autopilot_metrics() {
  python3 - <<'PY' "$ROOT"
import sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

root = Path(sys.argv[1])
path = root / "docs/orchestration/program_state.yaml"
prog = yaml.safe_load(path.read_text(encoding="utf-8"))
auto = dict(prog.get("autopilot") or {})
auto["ticks_total"] = int(auto.get("ticks_total") or 0) + 1
auto["last_tick_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
prog["autopilot"] = auto
path.write_text(yaml.safe_dump(prog, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
PY
}

if [[ "$AUTO_LOOPS" != "0" ]]; then
  echo "== owned autopilot AUTO mode (max $AUTO_LOOPS loops) =="
  for ((i = 1; i <= AUTO_LOOPS; i++)); do
    echo ""
    echo "== auto loop $i / $AUTO_LOOPS =="
    if ! run_tick; then
      echo "Auto loop: no more tasks."
      break
    fi
    bump_autopilot_metrics
    echo "Handoff: $HANDOFF"
    if run_execute; then
      continue
    fi
    echo "Auto loop stopped at implement pick (loop $i). See $HANDOFF"
    exit 0
  done
  echo "OK: auto loop finished"
  exit 0
fi

if ! run_tick; then
  echo "WARN: no eligible tasks (exit 2)" >&2
  exit 2
fi

bump_autopilot_metrics
echo ""
echo "Handoff: $HANDOFF"

if [[ "$EXECUTE" -eq 1 ]]; then
  echo "== execute handoff =="
  if run_execute; then
    echo "OK: machine actions applied"
  else
    echo "STOP: implement pick — complete handoff manually, then re-run with --execute"
    exit 3
  fi
else
  echo "Execute: bash scripts/execute_autopilot_handoff.sh  (or re-run with --execute)"
fi

if [[ "$PICK_ONLY" -eq 0 ]]; then
  PRODUCT="$(cd "$ROOT/../sv_frontend" && pwd)"
  if [[ -f "$PRODUCT/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1090
    source "$PRODUCT/.venv/bin/activate"
  fi
  if [[ -d "$PRODUCT" && -f "$PRODUCT/scripts/run_autopilot_gate.sh" ]]; then
    echo "== baseline gate (pre-implement health) =="
    bash "$PRODUCT/scripts/run_autopilot_gate.sh"
  fi
fi

echo "OK: owned autopilot tick complete"
