# ops/ — Orchestration Utilities

Small local tools that keep ATLAS responsive while background work runs.

## Scripts

- `dispatch.py` — task tracker (active/completed queue)
  - `python ops/dispatch.py status`
  - `python ops/dispatch.py add "Task title" --type task --priority high`
  - `python ops/dispatch.py complete T004 --result "done"`

- `monitor.py` — quick runtime monitor (training/screens/backfill)
  - `python ops/monitor.py`
  - `python ops/monitor.py --screens`
  - `python ops/monitor.py --json`

- `sync_training_tasks.py` — keeps QUASAR training task status in sync with real logs/screens
  - `python ops/sync_training_tasks.py`
  - `python ops/sync_training_tasks.py --dry-run`

## Recommended heartbeat flow

```bash
python /workspace/clawd/ops/monitor.py
python /workspace/clawd/ops/sync_training_tasks.py
python /workspace/clawd/ops/dispatch.py status
```
