#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Step 1: expand the released routings into the graded instance (#SCH-5160) ---
# The rollout left /app/data/jobs.json holding a stale partial instance. Expand the
# releases against the routing template library and the shop calendar and write the
# result back to that path; nothing the scheduler emits is correct until this is done.

python3 "${SCRIPT_DIR}/expand_routing.py"

# --- Step 2: restore the scheduler and produce the schedule artifacts ---

cp "${SCRIPT_DIR}/scheduler_fixed.py" /app/workflow/scheduler.py
python3 /app/workflow/scheduler.py --output-dir /app/output
