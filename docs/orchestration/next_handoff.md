# Autopilot handoff

**Generated:** 2026-05-26T10:46:14Z
**Autopilot level:** 3
**Plan:** `docs/plans/2026-05-28-owned-lrm-full-autopilot.md`

## Task 1: `ST-OWNED-11-001`

- **Action:** `defer_roadmap`
- **Title:** OWNED: foreach loop (roadmap)
- **Track:** C
- **LRM clause:** `LRM-FOREACH-UNSUPPORTED`
- **Pod:** `lower`
- **Score:** 9999

### Agent steps

1. Do **not** set `support_status: supported` in the index.
2. Record deferral in contract stub if useful.
3. Run: `python3 scripts/pick_next_owned_task.py --apply-defer <ST-ID>`
4. Commit overlay + program_state when batch of defers done.

## Gates (after implement)

```bash
cd ~/sv_frontend && source .venv/bin/activate && bash scripts/run_autopilot_gate.sh
```
