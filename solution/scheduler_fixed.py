#!/usr/bin/env python3
"""Single-machine batch scheduler — governance dialect (exact optimizer).

Assigns an order to the jobs on one machine to minimise total weighted
tardiness under sequence-dependent (family) setup times and precedence
constraints, then emits the schedule, the objective breakdown and a summary.

This objective (1 | s_ij, prec | sum w_j T_j) is NP-hard: no greedy priority
rule (WSPT, EDD, ...) is optimal on the shipped instances, and no standard
library solves it. The optimum is computed exactly by a subset dynamic program
over (scheduled_mask, last_family). Because the jobs already scheduled fix the
sum of their processing times, a partial schedule's clock is determined by the
setup time it has accumulated, so each state carries a Pareto frontier of
(accumulated_setup, best_value) points and drops every dominated point: a point
with at least as much accumulated setup and a value no better than another
point of the same state can never lead to a better completion, because the
remaining jobs, their feasible orders and their setups are identical and the
cost of every completion is non-decreasing in the clock. That dominance pruning
is what keeps the state space tractable; enumerating (mask, last_family, clock)
without it does not finish.

The governance tie-break (lexicographically smallest job-id sequence among all
orders attaining the minimum) is carried inside the dynamic program instead of
being reconstructed afterwards: each state's value packs the objective in the
high digits and the sequence of job ranks so far in the low digits of a single
integer, so comparing values compares objective first and the job-id order
second, and the dominance rule stays exact. Standard library only, fully
deterministic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
# Exact optimizer: subset DP over (scheduled_mask, last_family) carrying a
# dominance-pruned Pareto frontier over accumulated setup, with the governance
# lexicographic tie-break folded into the state value (#SCH-5101..#SCH-5145).
# --------------------------------------------------------------------------
def _predecessor_masks(jobs: list[dict], precedence: list, index: dict) -> list[int]:
    pred = [0] * len(jobs)
    for edge in precedence:
        before, after = str(edge[0]), str(edge[1])
        if before in index and after in index:
            pred[index[after]] |= 1 << index[before]
    return pred


def optimize(jobs: list[dict], precedence: list, setup: dict, initial_family: str,
             policy_data: dict) -> tuple[int, list[str]]:
    """Return (minimum total weighted tardiness, lexicographically smallest optimal order)."""
    jobs = sorted(jobs, key=lambda j: j["id"])
    n = len(jobs)
    if n == 0:
        return 0, []

    family_names = sorted(setup)
    family_index = {name: k for k, name in enumerate(family_names)}
    setup_cost = [[setup[a][b] for b in family_names] for a in family_names]

    family_of = [family_index[j["family"]] for j in jobs]
    processing = [j["processing_time"] for j in jobs]
    policies = [resolve_policy(j["family"], policy_data) for j in jobs]
    deadline = [jobs[i]["due_date"] + policies[i]["tardiness_grace"] for i in range(n)]
    weight = [jobs[i]["weight"] * policies[i]["weight_multiplier"] for i in range(n)]
    index = {j["id"]: i for i, j in enumerate(jobs)}
    pred = _predecessor_masks(jobs, precedence, index)

    # Value packing: value = objective * lex_scale + lexicographic key, where the
    # lexicographic key is the base-`radix` number whose digits are the job ranks
    # (rank = position in ascending job-id order) in machine-run order. Every
    # state at a given depth holds the same number of digits, so comparing packed
    # values compares the objective first and the job-id sequence second.
    radix = n if n > 1 else 2
    lex_scale = radix ** n
    digit_weight = [radix ** (n - 1 - depth) for depth in range(n)]

    full = (1 << n) - 1
    processing_sum = [0] * (1 << n)
    for mask in range(1, 1 << n):
        low = mask & -mask
        processing_sum[mask] = processing_sum[mask ^ low] + processing[low.bit_length() - 1]

    # layer: {scheduled_mask: {last_family: [(accumulated_setup, packed_value), ...]}}
    layer: dict = {0: {family_index[initial_family]: [(0, 0)]}}
    for depth in range(n):
        weight_here = digit_weight[depth]
        nxt: dict = {}
        for mask, by_family in layer.items():
            eligible = []
            rest = ~mask & full
            while rest:
                low = rest & -rest
                rest ^= low
                job = low.bit_length() - 1
                if pred[job] & ~mask == 0:
                    eligible.append((family_of[job], mask | low, processing_sum[mask] + processing[job],
                                     deadline[job], weight[job], job * weight_here))
            for last_family, frontier in by_family.items():
                row = setup_cost[last_family]
                for family, new_mask, base_clock, due, job_weight, lex_add in eligible:
                    changeover = row[family]
                    target = nxt.get(new_mask)
                    if target is None:
                        target = nxt[new_mask] = {}
                    reached = target.get(family)
                    if reached is None:
                        reached = target[family] = {}
                    reached_get = reached.get
                    for accumulated, value in frontier:
                        setup_total = accumulated + changeover
                        late = base_clock + setup_total - due
                        new_value = value + lex_add
                        if late > 0:
                            new_value += job_weight * late * lex_scale
                        seen = reached_get(setup_total)
                        if seen is None or new_value < seen:
                            reached[setup_total] = new_value
        # Dominance pruning: walking accumulated setup upwards, keep a point only
        # if it strictly improves on every point reachable with less setup.
        for by_family in nxt.values():
            for last_family, reached in by_family.items():
                best = None
                frontier = []
                for setup_total in sorted(reached):
                    value = reached[setup_total]
                    if best is None or value < best:
                        frontier.append((setup_total, value))
                        best = value
                by_family[last_family] = frontier
        layer = nxt

    best = None
    for by_family in layer.values():
        for frontier in by_family.values():
            for _setup_total, value in frontier:
                if best is None or value < best:
                    best = value
    objective, lex_key = divmod(best, lex_scale)
    ranks = []
    for _ in range(n):
        lex_key, digit = divmod(lex_key, radix)
        ranks.append(digit)
    ranks.reverse()
    return objective, [jobs[rank]["id"] for rank in ranks]


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
    family_by_id = {j["id"]: j["family"] for j in jobs}
    transitions = set()
    prev = initial_family
    for jid in sequence:
        fam = family_by_id[jid]
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
