#!/usr/bin/env bash
# AP-02: Owned-LRM autopilot driver — refresh backlog, pick, write handoff.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HANDOFF="${ROOT}/docs/orchestration/next_handoff.md"
BATCH=1

usage() {
  echo "Usage: $0 [--batch N] [--handoff PATH] [--pick-only]"
  exit 1
}

PICK_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --batch) BATCH="$2"; shift 2 ;;
    --handoff) HANDOFF="$2"; shift 2 ;;
    --pick-only) PICK_ONLY=1; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

# shellcheck disable=SC1090
source "$ROOT/scripts/git_commit_env.sh" 2>/dev/null || true

echo "== owned autopilot tick =="
echo "== regenerate backlog =="
python3 "$ROOT/scripts/generate_owned_backlog.py"
python3 "$ROOT/scripts/generate_owned_backlog.py" --check

echo "== workspace check =="
python3 "$ROOT/scripts/check_workspace.py"

echo "== pick next task(s) =="
if ! python3 "$ROOT/scripts/pick_next_owned_task.py" \
  --batch "$BATCH" \
  --write-handoff "$HANDOFF" \
  --update-program-state \
  --json; then
  echo "WARN: no eligible tasks (exit 2)" >&2
  exit 2
fi

echo ""
echo "Handoff: $HANDOFF"
echo "Execute the handoff in Cursor, then run gates and commit tranche."

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
