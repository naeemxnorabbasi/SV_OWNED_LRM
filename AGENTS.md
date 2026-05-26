# SV_OWNED_LRM — agent instructions

## Mission

Deliver **100% IEEE 1800-2017** on the **owned C++** backend with commercial quality (tests, parity vs slang oracle, honest index).

## Do not

- Weaken legacy v1.x SCOPE-LOCK claims in `SV_UPF_SPEC` without council addendum.
- Mark `supported` without owned implementation + M5/corpus proof.
- Edit `sv_frontend/cpp/compiler/src/parser.cpp` if your pod owns another parser TU (see FILE_OWNERSHIP.yaml).

## Read first

1. `workspace.yaml`
2. `docs/plans/OWNED_FULL_LRM_PROGRAM.md`
3. `docs/orchestration/program_state.yaml`
4. `docs/orchestration/phase_backlog_owned.yaml` (generated)

## Pick work (autopilot)

```bash
bash scripts/run_owned_autopilot.sh              # tick + handoff + baseline gate
bash scripts/run_owned_autopilot.sh --execute    # tick + auto defer/close_gate
bash scripts/run_owned_autopilot.sh --auto 80    # loop until implement pick stops
python3 scripts/pick_next_owned_task.py          # print next task only
```

Manual backlog check:

```bash
python3 scripts/generate_owned_backlog.py --check
```

Claim a row → fill `contracts/<ST-OWNED-id>.yaml` from `schemas/clause_factory_contract.yaml` → implement in `sv_frontend` → PR to product + spec index.

## Verification (mandatory)

```bash
cd ~/sv_frontend && bash scripts/run_autopilot_gate.sh
cd ~/sv_frontend && bash scripts/run_oracle_farm.sh --stem <feature_test_stem>
python3 ~/SV_OWNED_LRM/scripts/check_workspace.py
```
