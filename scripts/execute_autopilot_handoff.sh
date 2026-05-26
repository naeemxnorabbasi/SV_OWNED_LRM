#!/usr/bin/env bash
# Execute machine-actionable steps from the current autopilot pick(s).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PICKER="$ROOT/scripts/pick_next_owned_task.py"
CONTRACTS="$ROOT/contracts"

write_defer_contract() {
  local st_id="$1"
  local lrm_id="$2"
  local title="$3"
  local path="$CONTRACTS/${st_id}.yaml"
  cat >"$path" <<EOF
schema_version: "1.0"
st_id: ${st_id}
lrm_clause_id: ${lrm_id}
title: ${title}
status: deferred
reason: >-
  Roadmap-sized LRM surface; honest defer for owned-full-LRM program.
  Do not promote to supported until dedicated tranche.
promotion:
  to_status: unsupported
  blocked: true
EOF
  echo "  wrote $path"
}

apply_pick() {
  local id="$1"
  local action="$2"
  local lrm_id="${3:-}"
  local title="${4:-}"

  case "$action" in
    defer_roadmap)
      python3 "$PICKER" --apply-defer "$id"
      if [[ -n "$lrm_id" ]]; then
        write_defer_contract "$id" "$lrm_id" "$title"
      fi
      ;;
    close_gate)
      python3 "$PICKER" --apply-complete "$id"
      ;;
    implement)
      echo "  implement: $id (agent must execute — not auto-coded)"
      return 1
      ;;
    *)
      echo "  unknown action: $action" >&2
      return 1
      ;;
  esac
}

main() {
  local json
  json="$(python3 "$PICKER" --json)"
  local count
  count="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('picks',[])))" <<<"$json")"
  if [[ "$count" -eq 0 ]]; then
    echo "No picks to execute."
    exit 2
  fi

  local failed=0
  local deferred=0
  local completed=0
  while read -r line; do
    id="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$line")"
    action="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['action'])" "$line")"
    lrm="$(python3 -c "import json,sys; m=json.loads(sys.argv[1]).get('metadata') or {}; print(m.get('lrm_clause_id',''))" "$line")"
    title="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('title',''))" "$line")"
    echo "== execute $id ($action) =="
    if apply_pick "$id" "$action" "$lrm" "$title"; then
      [[ "$action" == "defer_roadmap" ]] && deferred=$((deferred + 1))
      [[ "$action" == "close_gate" ]] && completed=$((completed + 1))
    else
      failed=1
    fi
  done < <(python3 -c "import json,sys; [print(json.dumps(p)) for p in json.load(sys.stdin)['picks']]" <<<"$json")

  python3 "$ROOT/scripts/generate_owned_backlog.py" >/dev/null

  if [[ "$deferred" -gt 0 || "$completed" -gt 0 ]]; then
    python3 - <<PY "$ROOT" "$deferred" "$completed"
import sys
from pathlib import Path
import yaml

root = Path(sys.argv[1])
deferred = int(sys.argv[2])
completed = int(sys.argv[3])
path = root / "docs/orchestration/program_state.yaml"
prog = yaml.safe_load(path.read_text(encoding="utf-8"))
auto = dict(prog.get("autopilot") or {})
if deferred:
    auto["tasks_deferred"] = int(auto.get("tasks_deferred") or 0) + deferred
if completed:
    auto["chapter_gates_closed"] = int(auto.get("chapter_gates_closed") or 0) + completed
prog["autopilot"] = auto
path.write_text(yaml.safe_dump(prog, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
PY
  fi
  return "$failed"
}

main "$@"
