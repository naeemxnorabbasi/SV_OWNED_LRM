#!/usr/bin/env bash
# Owned-LRM implementation loop: refresh backlog, gate, oracle sample.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="$(cd "$ROOT/../sv_frontend" && pwd)"
source "$ROOT/scripts/git_commit_env.sh" 2>/dev/null || true

echo "== generate backlog =="
python3 "$ROOT/scripts/generate_owned_backlog.py"
python3 "$ROOT/scripts/check_workspace.py"

echo "== autopilot gate (legacy product) =="
if [[ -f "$WS/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1090
  source "$WS/.venv/bin/activate"
fi
bash "$WS/scripts/run_autopilot_gate.sh"

echo "== oracle farm sample =="
bash "$WS/scripts/run_oracle_farm.sh" --stem case_inside
bash "$WS/scripts/run_oracle_farm.sh" --stem assign_continuous

echo "OK: implementation loop passed"
