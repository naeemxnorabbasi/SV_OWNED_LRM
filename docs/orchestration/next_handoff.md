# Autopilot handoff

**Generated:** 2026-05-26T11:02:41Z
**Autopilot level:** 3
**Plan:** `docs/plans/2026-05-28-owned-lrm-full-autopilot.md`

## Task 1: `ST-OWNED-9-001`

- **Action:** `implement`
- **Title:** OWNED: active_clocked region NBA after posedge
- **Track:** B
- **LRM clause:** `LRM-ACTIVE-CLOCKED-REGION-SIM`
- **Pod:** `parser_always`
- **Score:** 7459

### Deliverables

- contracts/ST-OWNED-9-001.yaml
- sv_frontend: owned implementation
- SV_UPF_SPEC: promote LRM-ACTIVE-CLOCKED-REGION-SIM to supported/owned

### Verification

- slang parity >=0.99; lrm_clause_id=LRM-ACTIVE-CLOCKED-REGION-SIM; run_autopilot_gate.sh

### Agent steps

1. Copy `schemas/clause_factory_contract.yaml` → `contracts/<ST-ID>.yaml` and fill.
2. Implement only in pod paths from `FILE_OWNERSHIP.yaml`.
3. Add feature test stem + M5 test in `sv_frontend`.
4. Promote `lrm_clause_index.yaml` + matrix; run gates.
5. Commit all three repos with footer `Owned-Tranche: <ST-ID>`.

## Gates (after implement)

```bash
cd ~/sv_frontend && source .venv/bin/activate && bash scripts/run_autopilot_gate.sh
```
