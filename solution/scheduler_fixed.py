#!/usr/bin/env python3
"""Single-machine batch scheduler — governance dialect (EXACT optimizer).

Assigns an order to the jobs on one machine to MINIMISE total weighted
tardiness under sequence-dependent (family) setup times and precedence
constraints, then emits the schedule, the objective breakdown and a summary.

This objective (1 | s_ij, prec | sum w_j T_j) is NP-hard: no greedy priority
rule (WSPT, EDD, ...) is optimal on crafted instances, and no standard library
solves it for you. The optimum here is computed exactly with a subset dynamic
program over (remaining jobs, last family, current time); among all sequences
that attain the minimum objective the governance tie-break selects the
lexicographically-smallest job-id order. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

DEFAULT_INPUT = "/app/data/jobs.json"
DEFAULT_OUTPUT_DIR = "/app/output"
SETUP_PATH = "/app/data/setup_matrix.json"
POLICY_PATH = "/app/data/scheduling_policy.json"

SCHEMA_VERSION = "sched-wt-v1"

# Governance policy baseline (#SCH-5150). Any field the policy file omits keeps
# these values; the policy file may override per default and per family.
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


# --------------------------------------------------------------------------
# Policy resolution (#SCH-5150, #SCH-5152)
# --------------------------------------------------------------------------
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


def policy_checksum(policy_data: dict) -> str:
    lines = ["default|" + "|".join(str(resolve_policy("__default__", policy_data)[f]) for f in POLICY_FIELDS)]
    for family in sorted(policy_data.get("family_overrides", {})):
        lines.append(family + "|" + "|".join(str(resolve_policy(family, policy_data)[f]) for f in POLICY_FIELDS))
    return _sha256("\n".join(lines))


# --------------------------------------------------------------------------
# Exact optimizer: subset DP over (remaining_mask, last_family, current_time)
# with governance lexicographic-minimum tie-break (#SCH-5120..#SCH-5146)
# --------------------------------------------------------------------------
def _pred_masks(jobs: list[dict], precedence: list) -> list[int]:
    idx = {j["id"]: i for i, j in enumerate(jobs)}
    pred = [0] * len(jobs)
    for edge in precedence:
        a, b = edge[0], edge[1]      # a must run before b
        if a in idx and b in idx:
            pred[idx[b]] |= (1 << idx[a])
    return pred


def optimize(jobs: list[dict], precedence: list, setup: dict, initial_family: str,
             policy_data: dict) -> tuple[int, list[str]]:
    n = len(jobs)
    fam = [j["family"] for j in jobs]
    p = [j["processing_time"] for j in jobs]
    d = [j["due_date"] for j in jobs]
    w = [j["weight"] for j in jobs]
    pol = [resolve_policy(f, policy_data) for f in fam]
    eff_w = [w[i] * pol[i]["weight_multiplier"] for i in range(n)]
    grace = [pol[i]["tardiness_grace"] for i in range(n)]
    pred = _pred_masks(jobs, precedence)
    full = (1 << n) - 1

    sys.setrecursionlimit(100000)
    memo: dict = {}

    def g(remaining: int, last_family: str, t: int) -> int:
        if remaining == 0:
            return 0
        key = (remaining, last_family, t)
        cached = memo.get(key)
        if cached is not None:
            return cached
        best = None
        m = remaining
        while m:
            bit = m & (-m)
            m ^= bit
            i = bit.bit_length() - 1
            if pred[i] & remaining:
                continue                      # a predecessor is still unscheduled
            newt = t + setup[last_family][fam[i]] + p[i]
            cost = eff_w[i] * max(0, newt - d[i] - grace[i])
            total = cost + g(remaining ^ bit, fam[i], newt)
            if best is None or total < best:
                best = total
        memo[key] = best
        return best

    opt = g(full, initial_family, 0)

    # Governance tie-break: reconstruct the lexicographically-smallest job-id
    # order among all optimal sequences.
    order = sorted(range(n), key=lambda i: jobs[i]["id"])
    seq: list[str] = []
    remaining = full
    last_family = initial_family
    t = 0
    while remaining:
        picked = None
        for i in order:
            bit = 1 << i
            if not (remaining & bit) or (pred[i] & remaining):
                continue
            newt = t + setup[last_family][fam[i]] + p[i]
            cost = eff_w[i] * max(0, newt - d[i] - grace[i])
            if cost + g(remaining ^ bit, fam[i], newt) == g(remaining, last_family, t):
                picked, pnewt = i, newt
                break
        if picked is None:
            raise RuntimeError("reconstruction failed; DP inconsistent")
        seq.append(jobs[picked]["id"])
        remaining ^= (1 << picked)
        last_family = fam[picked]
        t = pnewt
    return opt, seq


# --------------------------------------------------------------------------
# Deterministic replay of a full sequence -> placements + objective
# --------------------------------------------------------------------------
def replay(sequence: list[str], jobs: list[dict], setup: dict, initial_family: str,
           policy_data: dict) -> tuple[list[dict], dict]:
    by_id = {j["id"]: j for j in jobs}
    placements: list[dict] = []
    total_wt = total_t = tardy = max_t = total_setup = total_comp = 0
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
        eff_w = j["weight"] * pol["weight_multiplier"]
        wtard = eff_w * tard
        row = {
            "position": pos,
            "job_id": jid,
            "family": fam,
            "processing_time": j["processing_time"],
            "due_date": j["due_date"],
            "weight": j["weight"],
            "effective_weight": eff_w,
            "tardiness_grace": pol["tardiness_grace"],
            "setup_from_prev": s,
            "start_time": start,
            "completion_time": comp,
            "tardiness": tard,
            "weighted_tardiness": wtard,
        }
        row["placement_digest"] = _placement_digest(row)
        placements.append(row)
        total_wt += wtard
        total_t += tard
        tardy += 1 if tard > 0 else 0
        max_t = max(max_t, tard)
        total_setup += s
        total_comp += comp
        prev_family = fam
        t = comp
    objective = {
        "total_weighted_tardiness": total_wt,
        "total_tardiness": total_t,
        "tardy_job_count": tardy,
        "max_tardiness": max_t,
        "makespan": t,
        "total_setup_time": total_setup,
        "total_completion_time": total_comp,
    }
    return placements, objective


# --------------------------------------------------------------------------
# Digests / checksums (contract in report_spec.json)
# --------------------------------------------------------------------------
def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _placement_digest(row: dict) -> str:
    payload = "|".join(str(x) for x in (
        row["position"], row["job_id"], row["family"], row["setup_from_prev"],
        row["start_time"], row["completion_time"], row["tardiness"], row["weighted_tardiness"],
    ))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def jobs_checksum(jobs: list[dict]) -> str:
    rows = sorted(jobs, key=lambda j: j["id"])
    payload = "\n".join(
        f"{j['id']}|{j['family']}|{j['processing_time']}|{j['due_date']}|{j['weight']}"
        for j in rows
    )
    return _sha256(payload)


def setup_matrix_checksum(setup: dict) -> str:
    rows = []
    for src in sorted(setup):
        for dst in sorted(setup[src]):
            rows.append(f"{src}|{dst}|{setup[src][dst]}")
    return _sha256("\n".join(rows))


def precedence_checksum(precedence: list) -> str:
    pairs = sorted((str(e[0]), str(e[1])) for e in precedence)
    return _sha256("\n".join(f"{a}|{b}" for a, b in pairs))


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

    opt, sequence = optimize(jobs, precedence, setup, initial_family, policy_data)
    placements, objective = replay(sequence, jobs, setup, initial_family, policy_data)
    assert objective["total_weighted_tardiness"] == opt

    families_present = sorted({j["family"] for j in jobs})
    transitions = set()
    prev = initial_family
    for jid in sequence:
        fam = next(j["family"] for j in jobs if j["id"] == jid)
        transitions.add((prev, fam))
        prev = fam

    wt_by_family = {f: 0 for f in families_present}
    for row in placements:
        wt_by_family[row["family"]] += row["weighted_tardiness"]

    schedule = {
        "sequence": sequence,
        "initial_family": initial_family,
        "placements": placements,
    }
    objective_out = {
        "schema_version": SCHEMA_VERSION,
        "job_count": len(jobs),
        "sequence": sequence,
        **objective,
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "job_count": len(jobs),
        "precedence_edge_count": len(precedence),
        "family_count": len(families_present),
        "distinct_family_transitions": len(transitions),
        "initial_family": initial_family,
        "total_weighted_tardiness": objective["total_weighted_tardiness"],
        "total_tardiness": objective["total_tardiness"],
        "tardy_job_count": objective["tardy_job_count"],
        "max_tardiness": objective["max_tardiness"],
        "makespan": objective["makespan"],
        "total_setup_time": objective["total_setup_time"],
        "total_completion_time": objective["total_completion_time"],
        "weighted_tardiness_by_family": wt_by_family,
        "jobs_checksum": jobs_checksum(jobs),
        "setup_matrix_checksum": setup_matrix_checksum(setup),
        "precedence_checksum": precedence_checksum(precedence),
        "policy_checksum": policy_checksum(policy_data),
        "schedule_checksum": _sha256("|".join(sequence)),
        "placement_digest_checksum": _sha256("|".join(r["placement_digest"] for r in placements)),
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "schedule.json").write_text(json.dumps(schedule, indent=2) + "\n", encoding="utf-8")
    (out / "objective.json").write_text(json.dumps(objective_out, indent=2) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-machine batch scheduler (exact)")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    run(args.input, args.output_dir)


if __name__ == "__main__":
    main()
