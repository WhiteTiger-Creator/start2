#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Step 1: contain the host to match /app/data/containment_checklist.json ---

# Revoke the rollout automation's SSH persistence, preserving any other keys.
if [ -f /app/host/authorized_keys ]; then
  grep -v 'batch-rollout-automation' /app/host/authorized_keys > /app/host/authorized_keys.tmp || true
  mv /app/host/authorized_keys.tmp /app/host/authorized_keys
fi

# Remove the passwordless sudoers escalation entirely.
rm -f /app/host/sudoers.d/batch-rollout

# Remove the exposed world-readable plaintext scheduler signing secret so the
# secret string no longer appears anywhere under /app.
rm -f /app/host/exposed/scheduler_signing.key

# --- Step 2: restore the scheduler and produce the schedule artifacts ---

cp "${SCRIPT_DIR}/scheduler_fixed.py" /app/workflow/scheduler.py
python3 /app/workflow/scheduler.py --output-dir /app/output
