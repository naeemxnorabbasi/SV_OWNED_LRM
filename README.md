# SV_OWNED_LRM — full owned IEEE 1800 commercial product

Separate program workspace for **100% LRM-compliant, owned C++** SystemVerilog front-end development.

## Separation from legacy program

| Workspace | Role |
|-----------|------|
| **SV_UPF_SPEC** + **sv_frontend** (v1.x) | Hybrid commercial product, council SCOPE-LOCK, cert tags |
| **SV_OWNED_LRM** (this repo) | Owned-full-LRM north star, megaswarm backlog, v4.0 cert target |

Legacy repos are **not replaced**. This workspace:

- Reads `lrm_clause_index.yaml` from `SV_UPF_SPEC` for truth.
- Implements in `sv_frontend` via focused PRs (file ownership pods).
- Promotes index rows back to `SV_UPF_SPEC` when gates pass.

## Quick start

```bash
cd ~/SV_OWNED_LRM
python3 scripts/generate_owned_backlog.py
python3 scripts/generate_owned_backlog.py --check

# Run legacy gates (inherited)
cd ~/sv_frontend && bash scripts/run_autopilot_gate.sh
```

## Generated artifacts

| File | Purpose |
|------|---------|
| `docs/orchestration/OWNED_WAVE_REGISTRY.yaml` | One row per gap clause (`OWNED-*`) |
| `docs/orchestration/phase_backlog_owned.yaml` | `ST-OWNED-*` subtasks for orchestrator |
| `docs/orchestration/program_state.yaml` | Live megaswarm metrics |

## Program doc

`docs/plans/OWNED_FULL_LRM_PROGRAM.md`

## Agent dispatch

See `AGENTS.md` and `docs/orchestration/FILE_OWNERSHIP.yaml`.
