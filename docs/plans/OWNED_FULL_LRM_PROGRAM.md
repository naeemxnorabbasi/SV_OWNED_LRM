---
title: Owned full IEEE 1800 commercial product
type: program
status: active
date: 2026-05-28
workspace: SV_OWNED_LRM
cert_target: v4.0-owned-lrm-cert
---

# Owned full IEEE 1800 — commercial product program

## Relationship to legacy (SV_UPF_SPEC / v1.x)

| Aspect | Legacy v1.x | This program |
|--------|-------------|--------------|
| Goal | Honest hybrid GA (B+C council) | **100% owned LRM** |
| Elaborator sold | Owned subset + slang oracle | **Owned only** (slang = CI oracle) |
| Index | Same `lrm_clause_index.yaml` | Read + promote via PR |
| Code | `sv_frontend` | Same repo; **FILE_OWNERSHIP** pods |
| Workspace | `SV_UPF_SPEC` orchestration | **`SV_OWNED_LRM`** orchestration |

Legacy tags (`v1.2-lrm-index`, etc.) are frozen. No breaking changes to legacy marketing without explicit council addendum.

## North star

Every indexed clause: `support_status: supported`, `backend: owned`, slang structural parity ≥0.99 on corpus, commercial gates green.

## Generated orchestration

```bash
python3 scripts/generate_owned_backlog.py
```

Produces:

- `docs/orchestration/OWNED_WAVE_REGISTRY.yaml` — `OWNED-*` units
- `docs/orchestration/phase_backlog_owned.yaml` — `ST-OWNED-*` + chapter gates

## Waves

| Wave | Focus |
|------|--------|
| 0 | Platform (this workspace, generator, ownership, parser split) |
| 1 | Lexical / preprocess |
| 2 | Hierarchy / generate / interfaces |
| 3 | Types / constants |
| 4 | Procedural (ch 9) |
| 5 | SVA |
| 6 | Constraints |
| 7 | Classes |
| 8 | Coverage |
| 9 | Simulation |
| 10 | Reference SoCs |
| 11 | v4.0 cert |

## Promotion (strict)

1. Owned implements LRM-sold behavior.
2. `feature_tests/<stem>` + M5 test.
3. Parity ≥0.99 vs slang.
4. `lrm_clause_index.yaml` + matrix same PR.
5. `run_autopilot_gate.sh` green.

## Agent scale

- **1 agent = 1 `ST-OWNED-*` row** (see backlog).
- **1 pod = 1 parser/sema file group** (no concurrent `parser.cpp` edits).
- Integrators merge serially; chapter gates close when all `ST-OWNED-CH-*` done.

## Inheritance (now and future)

`workspace.yaml` lists paths. When legacy adds features:

- New index rows → re-run generator → new `ST-OWNED-*` appear automatically.
- Reuse `sv_frontend` gates; do not duplicate compiler in this repo.
