#!/usr/bin/env python3
"""Single-machine batch scheduler (INCIDENT SNAPSHOT — DO NOT SHIP).

This is the scheduler as it stood after the failed batch-platform rollout. It
orders jobs with a GREEDY weighted-shortest-processing-time (WSPT) priority
rule: at each step it picks, among the precedence-eligible jobs, the one with
the smallest processing_time / weight ratio. That heuristic ignores the
sequence-dependent family setup times and the global weighted-tardiness
interaction, so on the shipped instances it produces a SUBOPTIMAL order and an
objective strictly larger than the true minimum. The governance target is the
EXACT minimum total weighted tardiness; restore the optimizer to the board's
final decisions recorded in /app/incident/scheduling_governance_log.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_INPUT = "/app/data/jobs.json"
DEFAULT_OUTPUT_DIR = "/app/output"
SETUP_PATH = "/app/data/setup_matrix.json"
POLICY_PATH = "/app/data/scheduling_policy.json"

SCHEMA_VERSION = "sched-wt-v1"

POLICY_FIELDS = ("weight_multiplier", "tardiness_grace")
POLICY_BASELINE = {"weight_multiplier": 1, "tardiness_grace": 0}


def coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return 0


def canon_name(value: object) -> str:
    text = str(value).strip().lower()
    return text if text else "unknown"


def resolve_policy(family: str, policy_data: dict) -> dict:
    resolved = dict(POLICY_BASELINE)
    for field, val in policy_data.get("default", {}).items():
        if field in resolved:
            resolved[field] = coerce_int(val)
    override = policy_data.get("family_overrides", {}).get(family)
    if isinstance(override, dict):
        for field, val in override.items():
            if field in resolved:
                resolved[field] = coerce_int(val)
    return resolved


def _pred_masks(jobs: list[dict], precedence: list) -> list[int]:
    idx = {j["id"]: i for i, j in enumerate(jobs)}
    pred = [0] * len(jobs)
    for edge in precedence:
        a, b = edge[0], edge[1]
        if a in idx and b in idx:
            pred[idx[b]] |= (1 << idx[a])
    return pred


def order_jobs(jobs: list[dict], precedence: list) -> list[str]:
    # GREEDY WSPT (the incident heuristic): smallest processing_time / weight
    # among precedence-eligible jobs, ties broken by job id ascending.
    n = len(jobs)
    pred = _pred_masks(jobs, precedence)
    full = (1 << n) - 1
    scheduled = 0
    seq: list[str] = []
    remaining = set(range(n))
    while remaining:
        eligible = [i for i in remaining if not (pred[i] & ~scheduled & full)]
        eligible.sort(key=lambda i: (jobs[i]["processing_time"] / max(jobs[i]["weight"], 1), jobs[i]["id"]))
        pick = eligible[0]
        seq.append(jobs[pick]["id"])
        remaining.discard(pick)
        scheduled |= (1 << pick)
    return seq


def replay(sequence: list[str], jobs: list[dict], setup: dict, initial_family: str,
           policy_data: dict) -> tuple[list[dict], dict, dict]:
    by_id = {j["id"]: j for j in jobs}
    placements: list[dict] = []
    by_family = {j["family"]: 0 for j in jobs}
    total_wt = total_t = tardy = total_setup = 0
    prev_family = initial_family
    t = 0
    for pos, jid in enumerate(sequence):
        j = by_id[jid]
        fam = j["family"]
        pol = resolve_policy(fam, policy_data)
        s = setup[prev_family][fam]
        start = t + s
        comp = start + j["processing_time"]
        tard = max(0, comp - j["due_date"] - pol["tardiness_grace"])
        wtard = j["weight"] * pol["weight_multiplier"] * tard
        placements.append({
            "position": pos, "job_id": jid, "setup_from_prev": s,
            "start_time": start, "completion_time": comp,
            "tardiness": tard, "weighted_tardiness": wtard,
        })
        by_family[fam] += wtard
        total_wt += wtard
        total_t += tard
        tardy += 1 if tard > 0 else 0
        total_setup += s
        prev_family = fam
        t = comp
    objective = {
        "total_weighted_tardiness": total_wt, "total_tardiness": total_t,
        "tardy_job_count": tardy, "makespan": t, "total_setup_time": total_setup,
    }
    return placements, objective, {f: by_family[f] for f in sorted(by_family)}


def run(input_path: str, output_dir: str) -> None:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    raw_jobs = payload["jobs"]
    precedence = payload.get("precedence", [])
    setup_data = json.loads(Path(SETUP_PATH).read_text(encoding="utf-8"))
    policy_data = json.loads(Path(POLICY_PATH).read_text(encoding="utf-8"))

    setup = {
        canon_name(src): {canon_name(dst): coerce_int(w) for dst, w in row.items()}
        for src, row in setup_data["setup"].items()
    }
    initial_family = canon_name(setup_data["initial_family"])

    jobs = [
        {
            "id": str(j["id"]),
            "family": canon_name(j["family"]),
            "processing_time": coerce_int(j["processing_time"]),
            "due_date": coerce_int(j["due_date"]),
            "weight": coerce_int(j["weight"]),
        }
        for j in raw_jobs
    ]

    sequence = order_jobs(jobs, precedence)
    placements, objective, wt_by_family = replay(sequence, jobs, setup, initial_family, policy_data)

    schedule = {"sequence": sequence, "initial_family": initial_family, "placements": placements}
    objective_out = {
        "schema_version": SCHEMA_VERSION,
        "job_count": len(jobs),
        "sequence": sequence,
        "total_weighted_tardiness": objective["total_weighted_tardiness"],
        "makespan": objective["makespan"],
        "total_setup_time": objective["total_setup_time"],
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "job_count": len(jobs),
        "total_weighted_tardiness": objective["total_weighted_tardiness"],
        "total_tardiness": objective["total_tardiness"],
        "tardy_job_count": objective["tardy_job_count"],
        "makespan": objective["makespan"],
        "weighted_tardiness_by_family": wt_by_family,
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "schedule.json").write_text(json.dumps(schedule, indent=2) + "\n", encoding="utf-8")
    (out / "objective.json").write_text(json.dumps(objective_out, indent=2) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-machine batch scheduler")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    run(args.input, args.output_dir)


if __name__ == "__main__":
    main()
