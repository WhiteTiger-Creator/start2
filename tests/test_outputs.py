"""Verifier tests for the single-machine batch-scheduler optimizer task."""

from __future__ import annotations

import ast
import hashlib
import itertools
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

WORKFLOW_PATH = Path("/app/workflow/scheduler.py")
ORIGINAL_WORKFLOW_PATH = Path("/app/workflow/.scheduler.original")
DEFAULT_INPUT = Path("/app/data/jobs.json")
SETUP_PATH = Path("/app/data/setup_matrix.json")
POLICY_PATH = Path("/app/data/scheduling_policy.json")
SPEC_PATH = Path("/app/docs/report_spec.json")
LOG_PATH = Path("/app/incident/scheduling_governance_log.md")
EXPECTED_FIXTURE = Path("/tests/fixtures/expected_report.json")
ALT_INPUT = Path("/tests/fixtures/alt_jobs.json")

FIXTURE = json.loads(EXPECTED_FIXTURE.read_text())
SPEC = json.loads(SPEC_PATH.read_text())

POLICY_FIELDS = ("weight_multiplier", "tardiness_grace")
POLICY_BASELINE = {"weight_multiplier": 1, "tardiness_grace": 0}

SCHEDULE_KEYS = set(SPEC["schedule_json"]["required_fields"])
OBJECTIVE_KEYS = set(SPEC["objective_json"]["required_fields"])
SUMMARY_KEYS = set(SPEC["summary_json"]["required_fields"])

# Documented wall-clock budget for one full scheduler run on a graded instance.
# instruction.md and report_spec.json state the same number; it is ~6x the
# reference optimizer's measured time on these instances, so a dominance-pruned
# exact optimizer has ample headroom while an unpruned state enumeration cannot
# finish. Kept as a literal here (never read from the mutable /app spec) so the
# budget cannot be relaxed by editing the environment.
RUNTIME_BUDGET_SEC = 240.0
# Hard kill for a runaway submission, so one hung run cannot consume the whole
# verifier timeout. Comfortably above the graded budget.
HARD_TIMEOUT_SEC = 300

# Tiny crafted instance: proves the governance optimum genuinely deviates from a
# weighted-shortest-processing-time order.
MICRO_JOBS = [
    {"id": "m00", "family": "mill", "processing_time": 6, "due_date": 59, "weight": 4},
    {"id": "m01", "family": "weld", "processing_time": 7, "due_date": 41, "weight": 1},
    {"id": "m02", "family": "forge", "processing_time": 7, "due_date": 8, "weight": 3},
    {"id": "m03", "family": "forge", "processing_time": 3, "due_date": 30, "weight": 4},
    {"id": "m04", "family": "press", "processing_time": 4, "due_date": 9, "weight": 3},
]
MICRO_PREC = [["m00", "m04"], ["m01", "m04"], ["m02", "m03"]]
MICRO_OPT = FIXTURE["micro_optimum"]
MICRO_WSPT = FIXTURE["micro_wspt"]

# Small instance used by the policy / source-path influence and idempotency
# checks, so those runs stay cheap and the whole suite stays far inside the
# verifier timeout. The graded instances are the big ones.
SMALL_JOBS = [
    {"id": "s00", "family": "forge", "processing_time": 12, "due_date": 41, "weight": 3},
    {"id": "s01", "family": "plate", "processing_time": 8, "due_date": 7, "weight": 1},
    {"id": "s02", "family": "press", "processing_time": 4, "due_date": 27, "weight": 4},
    {"id": "s03", "family": "forge", "processing_time": 13, "due_date": 23, "weight": 1},
    {"id": "s04", "family": "mill", "processing_time": 7, "due_date": 36, "weight": 2},
    {"id": "s05", "family": "weld", "processing_time": 12, "due_date": 36, "weight": 1},
    {"id": "s06", "family": "mill", "processing_time": 8, "due_date": 14, "weight": 5},
    {"id": "s07", "family": "plate", "processing_time": 8, "due_date": 39, "weight": 5},
]
SMALL_PREC = [["s00", "s05"], ["s01", "s05"], ["s01", "s07"], ["s03", "s05"], ["s05", "s06"]]


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


# --- verifier execution isolation -------------------------------------------------
# The submitted /app/workflow/scheduler.py is untrusted once the separate verifier runs it.
# We execute it under an unprivileged UID (65534 / nobody) via setpriv, so it cannot write the
# reward path, read the held-out fixtures under /tests, or interfere with the verifier. Inputs are
# staged into a candidate-writable work area; the setup matrix and policy under /app keep their
# fixed paths.
_CWORK = Path("/candidate-work")
_run_ctr = itertools.count()
_SETPRIV = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--no-new-privs"]
# The submitted program never inherits the verifier's environment: it is handed a
# minimal explicit one, so nothing about the grading process (paths, tokens,
# python configuration) leaks into it and it cannot depend on it.
CHILD_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/candidate-work", "LANG": "C.UTF-8"}


def _candidate_dir() -> Path:
    d = _CWORK / f"run-{next(_run_ctr)}"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o777)
    return d


def _run_agent(argv, cwd: Path):
    return subprocess.run(
        _SETPRIV + argv, check=True, capture_output=True, text=True, cwd=str(cwd),
        env=dict(CHILD_ENV), timeout=HARD_TIMEOUT_SEC,
    )


def _run_pipeline(tmp_path: Path, script_path: Path = WORKFLOW_PATH, input_path: Path = DEFAULT_INPUT):
    """Run the submitted scheduler once; returns its outputs and its wall-clock time."""
    work = _candidate_dir()
    out_dir = work / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o777)
    staged_input = work / "input.json"
    shutil.copy(str(input_path), str(staged_input))
    os.chmod(staged_input, 0o644)
    started = time.monotonic()
    result = _run_agent(
        [sys.executable, str(script_path), "--input", str(staged_input), "--output-dir", str(out_dir)],
        cwd=work,
    )
    elapsed = time.monotonic() - started
    assert result.returncode == 0
    schedule = _load_json(out_dir / "schedule.json")
    objective = _load_json(out_dir / "objective.json")
    summary = _load_json(out_dir / "summary.json")
    return out_dir, summary, schedule, objective, elapsed


def _run_instance(tmp_path: Path, jobs, precedence):
    """Run the submitted scheduler on an instance defined inline (kept small)."""
    input_path = _candidate_dir() / "instance.json"
    _write_json(input_path, {"jobs": jobs, "precedence": precedence})
    os.chmod(input_path, 0o644)
    return _run_pipeline(tmp_path, input_path=input_path)


# The graded instances are run once each for the whole session and every test
# reuses those outputs: the exact optimizer is the expensive part of the suite.
@pytest.fixture(scope="session")
def primary_outputs(tmp_path_factory):
    return _run_pipeline(tmp_path_factory.mktemp("primary"))


@pytest.fixture(scope="session")
def alternate_outputs(tmp_path_factory):
    return _run_pipeline(tmp_path_factory.mktemp("alternate"), input_path=ALT_INPUT)


# --------------------------------------------------------------------------
# Independent governance objective simulator + greedy heuristics (verifier side).
# These re-derive the objective from an order; they never solve the NP-hard problem.
# --------------------------------------------------------------------------
def _resolve_policy(family, policy_data):
    resolved = dict(POLICY_BASELINE)
    for k, v in policy_data.get("default", {}).items():
        if k in resolved:
            resolved[k] = int(v)
    override = policy_data.get("family_overrides", {}).get(family)
    if isinstance(override, dict):
        for k, v in override.items():
            if k in resolved:
                resolved[k] = int(v)
    return resolved


def _load_instance(path):
    data = _load_json(path)
    jobs = [
        {"id": str(j["id"]), "family": str(j["family"]).strip().lower(),
         "processing_time": int(j["processing_time"]), "due_date": int(j["due_date"]),
         "weight": int(j["weight"])}
        for j in data["jobs"]
    ]
    prec = [[str(a), str(b)] for a, b in data.get("precedence", [])]
    return jobs, prec


def _load_setup():
    data = _load_json(SETUP_PATH)
    setup = {str(s).strip().lower(): {str(d).strip().lower(): int(w) for d, w in row.items()}
             for s, row in data["setup"].items()}
    return setup, str(data["initial_family"]).strip().lower()


def _replay_rows(sequence, jobs, setup, initial_family, policy_data):
    """Independently re-derive the placement rows the contract asks for from an order."""
    by_id = {j["id"]: j for j in jobs}
    rows = []
    prev = initial_family
    t = 0
    for position, jid in enumerate(sequence):
        j = by_id[jid]
        fam = j["family"]
        pol = _resolve_policy(fam, policy_data)
        s = setup[prev][fam]
        start = t + s
        comp = start + j["processing_time"]
        tard = max(0, comp - j["due_date"] - pol["tardiness_grace"])
        rows.append({
            "position": position,
            "job_id": jid,
            "setup_from_prev": s,
            "start_time": start,
            "completion_time": comp,
            "tardiness": tard,
            "weighted_tardiness": j["weight"] * pol["weight_multiplier"] * tard,
        })
        prev = fam
        t = comp
    return rows


def _objective_of(sequence, jobs, setup, initial_family, policy_data):
    rows = _replay_rows(sequence, jobs, setup, initial_family, policy_data)
    return sum(r["weighted_tardiness"] for r in rows)


def _weighted_tardiness_by_family(sequence, jobs, setup, initial_family, policy_data):
    family_of = {j["id"]: j["family"] for j in jobs}
    totals = {j["family"]: 0 for j in jobs}
    for row in _replay_rows(sequence, jobs, setup, initial_family, policy_data):
        totals[family_of[row["job_id"]]] += row["weighted_tardiness"]
    return {f: totals[f] for f in sorted(totals)}


def _is_feasible(sequence, jobs, precedence):
    ids = [j["id"] for j in jobs]
    if sorted(sequence) != sorted(ids):
        return False
    pos = {jid: i for i, jid in enumerate(sequence)}
    return all(pos[a] < pos[b] for a, b in precedence)


def _greedy(jobs, precedence, key, setup, initial_family, policy_data):
    idx = {j["id"]: i for i, j in enumerate(jobs)}
    pred = {i: set() for i in range(len(jobs))}
    for a, b in precedence:
        pred[idx[b]].add(idx[a])
    remaining = set(range(len(jobs)))
    scheduled = set()
    seq = []
    while remaining:
        eligible = [i for i in remaining if pred[i] <= scheduled]
        eligible.sort(key=lambda i: (key(jobs[i]), jobs[i]["id"]))
        pick = eligible[0]
        seq.append(jobs[pick]["id"])
        remaining.discard(pick)
        scheduled.add(pick)
    return seq, _objective_of(seq, jobs, setup, initial_family, policy_data)


def _wspt(jobs, precedence, setup, initial_family, policy_data):
    return _greedy(jobs, precedence,
                   lambda j: j["processing_time"] / max(j["weight"], 1),
                   setup, initial_family, policy_data)


def _edd(jobs, precedence, setup, initial_family, policy_data):
    return _greedy(jobs, precedence, lambda j: j["due_date"], setup, initial_family, policy_data)


# --------------------------------------------------------------------------
# Checksum vectors + primary fixtures
# --------------------------------------------------------------------------
def test_checksum_serialization_contract_vectors():
    vectors = SPEC["summary_json"]["checksum_test_vectors"]
    for prefix in ("jobs", "policy", "schedule"):
        payload = vectors[f"{prefix}_payload"].encode("utf-8")
        assert hashlib.sha256(payload).hexdigest() == vectors[f"{prefix}_sha256"]


def test_cli_exists():
    assert WORKFLOW_PATH.exists()


def test_output_dir_contains_exactly_three_files(primary_outputs):
    out_dir, _, _, _, _ = primary_outputs
    names = sorted(p.name for p in out_dir.iterdir() if p.is_file())
    assert names == ["objective.json", "schedule.json", "summary.json"]


def test_primary_summary_matches_fixture(primary_outputs):
    _, summary, _, _, _ = primary_outputs
    assert summary == FIXTURE["primary"]["summary"]


def test_primary_schedule_matches_fixture(primary_outputs):
    _, _, schedule, _, _ = primary_outputs
    assert schedule == FIXTURE["primary"]["schedule"]


def test_primary_objective_matches_fixture(primary_outputs):
    _, _, _, objective, _ = primary_outputs
    assert objective == FIXTURE["primary"]["objective"]


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------
def test_summary_schema(primary_outputs):
    _, summary, _, _, _ = primary_outputs
    assert set(summary) == SUMMARY_KEYS
    assert summary["schema_version"] == "sched-wt-v1"
    assert isinstance(summary["weighted_tardiness_by_family"], dict)
    for field in ("jobs_checksum", "policy_checksum", "schedule_checksum"):
        assert len(summary[field]) == 64


def test_objective_schema(primary_outputs):
    _, _, _, objective, _ = primary_outputs
    assert set(objective) == OBJECTIVE_KEYS
    assert objective["schema_version"] == "sched-wt-v1"
    assert objective["job_count"] == len(objective["sequence"])
    assert len(set(objective["sequence"])) == objective["job_count"]


def test_schedule_schema_and_ordering(primary_outputs):
    _, _, schedule, _, _ = primary_outputs
    assert set(schedule) == {"sequence", "initial_family", "placements"}
    setup, initial = _load_setup()
    assert schedule["initial_family"] == initial
    placements = schedule["placements"]
    assert [p["position"] for p in placements] == list(range(len(placements)))
    assert [p["job_id"] for p in placements] == schedule["sequence"]
    for row in placements:
        assert set(row) == SCHEDULE_KEYS
    # Every placement value is re-derived independently from the instance, the
    # setup matrix and the resolved policy for the order the agent emitted.
    jobs, _prec = _load_instance(DEFAULT_INPUT)
    policy = _load_json(POLICY_PATH)
    assert placements == _replay_rows(schedule["sequence"], jobs, setup, initial, policy)


def test_schedule_objective_summary_consistent(primary_outputs):
    _, summary, schedule, objective, _ = primary_outputs
    assert schedule["sequence"] == objective["sequence"]
    assert summary["job_count"] == objective["job_count"] == len(schedule["sequence"])
    placements = schedule["placements"]
    assert objective["total_weighted_tardiness"] == sum(p["weighted_tardiness"] for p in placements)
    assert objective["total_setup_time"] == sum(p["setup_from_prev"] for p in placements)
    assert objective["makespan"] == placements[-1]["completion_time"]
    assert summary["total_tardiness"] == sum(p["tardiness"] for p in placements)
    assert summary["tardy_job_count"] == sum(1 for p in placements if p["tardiness"] > 0)
    for field in ("total_weighted_tardiness", "makespan"):
        assert summary[field] == objective[field]
    jobs, _prec = _load_instance(DEFAULT_INPUT)
    setup, initial = _load_setup()
    policy = _load_json(POLICY_PATH)
    assert summary["weighted_tardiness_by_family"] == _weighted_tardiness_by_family(
        schedule["sequence"], jobs, setup, initial, policy)
    assert summary["schedule_checksum"] == hashlib.sha256(
        "|".join(schedule["sequence"]).encode("utf-8")).hexdigest()
    assert summary["jobs_checksum"] == hashlib.sha256("\n".join(
        f"{j['id']}|{j['family']}|{j['processing_time']}|{j['due_date']}|{j['weight']}"
        for j in sorted(jobs, key=lambda j: j["id"])).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# The hard core: the emitted order must be OPTIMAL and feasible; heuristics fail.
# --------------------------------------------------------------------------
def test_agent_schedule_is_optimal_and_feasible(primary_outputs):
    _, _, schedule, objective, _ = primary_outputs
    jobs, prec = _load_instance(DEFAULT_INPUT)
    setup, initial = _load_setup()
    policy = _load_json(POLICY_PATH)
    seq = schedule["sequence"]
    assert _is_feasible(seq, jobs, prec), "emitted order violates precedence or is not a permutation"
    recomputed = _objective_of(seq, jobs, setup, initial, policy)
    assert recomputed == FIXTURE["primary_optimum"], "emitted order does not attain the optimum"
    assert objective["total_weighted_tardiness"] == FIXTURE["primary_optimum"]


def test_greedy_heuristics_are_strictly_suboptimal():
    jobs, prec = _load_instance(DEFAULT_INPUT)
    setup, initial = _load_setup()
    policy = _load_json(POLICY_PATH)
    opt = FIXTURE["primary_optimum"]
    _, w = _wspt(jobs, prec, setup, initial, policy)
    _, e = _edd(jobs, prec, setup, initial, policy)
    assert w > opt, f"WSPT ({w}) must be strictly worse than the optimum ({opt})"
    assert e > opt, f"EDD ({e}) must be strictly worse than the optimum ({opt})"


def test_agent_optimal_and_greedy_suboptimal_on_alternate(alternate_outputs):
    _, _, schedule, objective, _ = alternate_outputs
    jobs, prec = _load_instance(ALT_INPUT)
    setup, initial = _load_setup()
    policy = _load_json(POLICY_PATH)
    opt = FIXTURE["alternate_optimum"]
    assert _is_feasible(schedule["sequence"], jobs, prec)
    assert _objective_of(schedule["sequence"], jobs, setup, initial, policy) == opt
    assert objective["total_weighted_tardiness"] == opt
    _, w = _wspt(jobs, prec, setup, initial, policy)
    _, e = _edd(jobs, prec, setup, initial, policy)
    assert w > opt and e > opt


def test_optimum_beats_wspt_on_crafted_instance(tmp_path: Path):
    """A weighted-shortest-processing-time order is precedence-feasible but strictly
    worse than the governance optimum the agent must emit."""
    setup, initial = _load_setup()
    policy = _load_json(POLICY_PATH)
    _, w = _wspt(MICRO_JOBS, MICRO_PREC, setup, initial, policy)
    assert w == MICRO_WSPT
    _, _, schedule, objective, _ = _run_instance(tmp_path / "run", MICRO_JOBS, MICRO_PREC)
    assert _is_feasible(schedule["sequence"], MICRO_JOBS, MICRO_PREC)
    assert objective["total_weighted_tardiness"] == MICRO_OPT
    assert _objective_of(schedule["sequence"], MICRO_JOBS, setup, initial, policy) == MICRO_OPT
    # the greedy order is strictly worse: the optimum genuinely deviates from WSPT.
    assert MICRO_OPT < MICRO_WSPT
    assert objective["total_weighted_tardiness"] != MICRO_WSPT


# --------------------------------------------------------------------------
# Original / broken snapshot
# --------------------------------------------------------------------------
def test_original_snapshot_preserved():
    assert ORIGINAL_WORKFLOW_PATH.exists()
    digest = hashlib.sha256(ORIGINAL_WORKFLOW_PATH.read_bytes()).hexdigest()
    assert digest == FIXTURE["broken_pipeline_sha256"]


def test_broken_snapshot_is_wrong(tmp_path: Path):
    _, broken_summary, broken_schedule, broken_obj, _ = _run_pipeline(
        tmp_path, script_path=ORIGINAL_WORKFLOW_PATH)
    broken_hash = hashlib.sha256(json.dumps(broken_summary, sort_keys=True).encode("utf-8")).hexdigest()
    assert broken_hash == FIXTURE["broken_summary_sha256"]
    assert broken_schedule["sequence"] == FIXTURE["broken_sequence"]
    # the greedy snapshot's objective is strictly larger than the optimum: it is wrong.
    assert broken_obj["total_weighted_tardiness"] == FIXTURE["broken_objective"]
    assert broken_obj["total_weighted_tardiness"] > FIXTURE["primary_optimum"]


# --------------------------------------------------------------------------
# Runtime budget: the documented wall-clock ceiling on one full graded run.
# --------------------------------------------------------------------------
def test_graded_runs_meet_documented_runtime_budget(primary_outputs, alternate_outputs):
    """Each full scheduler run on a graded instance must finish inside the budget
    instruction.md states. A pruned exact optimizer has ample headroom; an
    unpruned enumeration of scheduler states does not."""
    _, _, _, _, primary_elapsed = primary_outputs
    _, _, _, _, alternate_elapsed = alternate_outputs
    print(f"scheduler run: shipped instance {primary_elapsed:.1f}s, "
          f"alternate instance {alternate_elapsed:.1f}s, budget {RUNTIME_BUDGET_SEC:.0f}s")
    assert primary_elapsed < RUNTIME_BUDGET_SEC, (
        f"the shipped instance took {primary_elapsed:.1f}s, over the {RUNTIME_BUDGET_SEC:.0f}s budget"
    )
    assert alternate_elapsed < RUNTIME_BUDGET_SEC, (
        f"the alternate instance took {alternate_elapsed:.1f}s, over the {RUNTIME_BUDGET_SEC:.0f}s budget"
    )


def test_runtime_budget_is_stated_in_the_contract():
    """The budget the verifier enforces is the one the environment documents."""
    assert SPEC["workflow_repair"]["runtime_budget_seconds"] == int(RUNTIME_BUDGET_SEC)


# --------------------------------------------------------------------------
# Generalization / idempotency / CLI
# --------------------------------------------------------------------------
def test_pipeline_rerun_idempotent(tmp_path: Path):
    _, sa, wa, qa, _ = _run_instance(tmp_path / "a", SMALL_JOBS, SMALL_PREC)
    _, sb, wb, qb, _ = _run_instance(tmp_path / "b", SMALL_JOBS, SMALL_PREC)
    assert (sa, wa, qa) == (sb, wb, qb)


def test_pipeline_supports_alternate_input(alternate_outputs):
    _, summary, schedule, objective, _ = alternate_outputs
    assert summary == FIXTURE["alternate"]["summary"]
    assert schedule == FIXTURE["alternate"]["schedule"]
    assert objective == FIXTURE["alternate"]["objective"]


def test_cli_defaults_work_and_match_explicit_run(primary_outputs):
    _, explicit_summary, _, _, _ = primary_outputs
    # The no-argument run writes to the default /app/output; clear any root-owned artifacts from
    # solve.sh and make the dir candidate-writable so the unprivileged program can populate it.
    default_out = Path("/app/output")
    shutil.rmtree(default_out, ignore_errors=True)
    default_out.mkdir(parents=True, exist_ok=True)
    os.chmod(default_out, 0o777)
    _run_agent([sys.executable, str(WORKFLOW_PATH)], cwd=_candidate_dir())
    assert _load_json(default_out / "summary.json") == explicit_summary


# --------------------------------------------------------------------------
# Source-path influence (run on the small instance: these probe where the inputs
# are read from, not the optimizer, so they need not pay for a graded run)
# --------------------------------------------------------------------------
def test_setup_matrix_source_path_affects_output(tmp_path: Path):
    original = SETUP_PATH.read_text(encoding="utf-8")
    try:
        _, summary_a, sched_a, obj_a, _ = _run_instance(tmp_path / "a", SMALL_JOBS, SMALL_PREC)
        data = json.loads(original)
        for src in data["setup"]:
            for dst in data["setup"][src]:
                data["setup"][src][dst] = int(data["setup"][src][dst]) + 100
        SETUP_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        _, summary_b, sched_b, obj_b, _ = _run_instance(tmp_path / "b", SMALL_JOBS, SMALL_PREC)
        # The setup matrix is read from its fixed path, so perturbing it must move
        # the emitted schedule and objective, not just a checksum.
        assert obj_a["total_weighted_tardiness"] != obj_b["total_weighted_tardiness"]
        assert obj_a["total_setup_time"] != obj_b["total_setup_time"]
        assert sched_a["placements"] != sched_b["placements"]
        assert summary_a != summary_b
    finally:
        SETUP_PATH.write_text(original, encoding="utf-8")


def test_policy_source_path_affects_output(tmp_path: Path):
    original = POLICY_PATH.read_text(encoding="utf-8")
    try:
        _, summary_a, _, _, _ = _run_instance(tmp_path / "a", SMALL_JOBS, SMALL_PREC)
        data = json.loads(original)
        data.setdefault("default", {})["weight_multiplier"] = 7
        POLICY_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        _, summary_b, _, _, _ = _run_instance(tmp_path / "b", SMALL_JOBS, SMALL_PREC)
        assert summary_a["policy_checksum"] != summary_b["policy_checksum"]
        assert summary_a != summary_b
    finally:
        POLICY_PATH.write_text(original, encoding="utf-8")


# --------------------------------------------------------------------------
# Policy resolution
# --------------------------------------------------------------------------
def _resolve_fields(family, data):
    return {f: _resolve_policy(family, data)[f] for f in POLICY_FIELDS}


def test_sparse_override_inherits_remaining_fields():
    data = _load_json(POLICY_PATH)
    overrides = data.get("family_overrides", {})
    sparse = [f for f, o in overrides.items() if len(o) == 1]
    assert sparse, "the shipped policy must exercise a single-field override"
    default_resolved = _resolve_fields("__absent__", data)
    for family in sparse:
        resolved = _resolve_fields(family, data)
        named = next(iter(overrides[family]))
        assert resolved[named] == int(overrides[family][named])
        for field in POLICY_FIELDS:
            if field != named:
                assert resolved[field] == default_resolved[field]


def test_policy_baseline_fallback_for_omitted_fields():
    data = _load_json(POLICY_PATH)
    omitted = [f for f in POLICY_FIELDS if f not in data.get("default", {})]
    assert omitted, "the shipped policy default must omit at least one field to exercise fallback"
    resolved = _resolve_fields("__absent__", data)
    for field in omitted:
        assert resolved[field] == POLICY_BASELINE[field]


def test_policy_checksum_consistent(primary_outputs):
    _, summary, _, _, _ = primary_outputs
    data = _load_json(POLICY_PATH)
    lines = ["default|" + "|".join(str(_resolve_fields("__default__", data)[f]) for f in POLICY_FIELDS)]
    for family in sorted(data.get("family_overrides", {})):
        lines.append(family + "|" + "|".join(str(_resolve_fields(family, data)[f]) for f in POLICY_FIELDS))
    assert summary["policy_checksum"] == hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Anti-delegation: static AST ban on solver libraries + dynamic execution
# --------------------------------------------------------------------------
def test_scheduler_does_not_import_solver_engines():
    tree = ast.parse(WORKFLOW_PATH.read_text(encoding="utf-8"))
    banned = set(SPEC["workflow_repair"]["prohibited_imports"])
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    offending = banned & found
    assert not offending, f"scheduler must not delegate to a solver/graph engine: {offending}"


def test_ast_check_catches_ortools_importing_engine(tmp_path: Path):
    """The AST ban is real: an ortools-importing delegate is detected."""
    shim = tmp_path / "delegating_engine.py"
    shim.write_text("from ortools.sat.python import cp_model\n\n\ndef run():\n    return cp_model.CpModel()\n")
    tree = ast.parse(shim.read_text())
    imported = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    banned = set(SPEC["workflow_repair"]["prohibited_imports"])
    assert "ortools" in imported
    assert banned & imported


def test_scheduler_has_no_dynamic_execution():
    tree = ast.parse(WORKFLOW_PATH.read_text(encoding="utf-8"))
    banned = set(SPEC["workflow_repair"]["prohibited_dynamic_execution"])
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in banned:
            used.add(node.func.id)
    assert not used, f"scheduler must not build the answer via dynamic execution: {used}"


# --------------------------------------------------------------------------
# Governance-log discoverability
# --------------------------------------------------------------------------
def test_governing_entry_index_is_complete():
    import re

    listed = {e for v in SPEC["governing_entry_index"]["stages"].values() for e in v}
    log_text = LOG_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\*\*(?:Governance decision|Recovery draft proposal) \(\d{4}-\d{2}-\d{2} - (#SCH-\d+)\)\*\*([^\n]*)"
    )
    governing = {
        m.group(1)
        for m in pattern.finditer(log_text)
        if "*(superseded" not in m.group(2).lower() and "*(revised" not in m.group(2).lower()
    }
    assert governing, "no governing entries found -- parser drifted from the log format"
    assert not sorted(governing - listed), f"absent from index: {sorted(governing - listed)}"
    assert not sorted(listed - governing), f"index lists non-governing: {sorted(listed - governing)}"


def test_pipeline_does_not_reference_test_artifacts():
    code = WORKFLOW_PATH.read_text(encoding="utf-8")
    for token in ("/tests", "expected_report.json", "alt_jobs.json"):
        assert token not in code


def test_submitted_program_runs_unprivileged_and_cannot_write_reward(tmp_path: Path):
    """The isolation itself works: code run the way the verifier runs the agent is unprivileged
    (uid 65534) and cannot write the reward path."""
    os.makedirs("/logs/verifier", exist_ok=True)
    reward = Path("/logs/verifier/reward.txt")
    if not reward.exists():
        reward.write_text("0")
    os.chmod("/logs/verifier", 0o755)
    os.chmod(reward, 0o644)
    probe = _candidate_dir() / "probe.py"
    probe.write_text(
        "import os\n"
        "print(os.getuid())\n"
        "open('/logs/verifier/reward.txt', 'w').write('1')\n",
        encoding="utf-8",
    )
    os.chmod(probe, 0o644)
    res = subprocess.run(
        _SETPRIV + [sys.executable, str(probe)],
        capture_output=True, text=True, cwd=str(_CWORK), check=False,
        env=dict(CHILD_ENV), timeout=HARD_TIMEOUT_SEC,
    )
    assert res.stdout.strip().splitlines()[0] == "65534", "submitted program must run as uid 65534"
    assert res.returncode != 0 and "Permission denied" in res.stderr, (
        "unprivileged submitted program must not be able to write the reward path"
    )


# --------------------------------------------------------------------------
# Host containment end-states (checklist is data at /app/data). All targets are
# under /app so they arrive with the artifact; grading is content/existence
# based (not file-mode or uid, which need not survive the artifact copy into a
# separate verifier container).
# --------------------------------------------------------------------------
HOST_AUTH_KEYS = Path("/app/host/authorized_keys")
SUDOERS_DROPIN = Path("/app/host/sudoers.d/batch-rollout")
EXPOSED_SECRET = Path("/app/host/exposed/scheduler_signing.key")
ROGUE_KEY_COMMENT = "batch-rollout-automation"
SIGNING_SECRET = "scheduler-signing-synthetic-3d2c1b0a9f8e-DO-NOT-USE"
APP_ROOT = Path("/app")
# The containment checklist is the one file that legitimately quotes the secret:
# it declares the end-state ("this string must not appear"). It is exempt from the
# scan only while it is byte-identical to the shipped checklist, so it cannot be
# used as a hiding place; a rewritten checklist (an agent redacting it is fine) is
# scanned like everything else. Every other file under /app must be clear of the
# secret, so relocating it is not containment.
CHECKLIST_PATH = Path("/app/data/containment_checklist.json")


def _secret_quote_allowed(path: Path) -> bool:
    return (
        path == CHECKLIST_PATH
        and hashlib.sha256(path.read_bytes()).hexdigest() == FIXTURE["containment_checklist_sha256"]
    )


def test_rogue_ssh_key_line_revoked():
    assert HOST_AUTH_KEYS.exists(), "the host authorized_keys file must remain in place"
    text = HOST_AUTH_KEYS.read_text(encoding="utf-8")
    assert ROGUE_KEY_COMMENT not in text


def test_sudoers_escalation_removed():
    assert not SUDOERS_DROPIN.exists()


def test_exposed_signing_secret_removed():
    if EXPOSED_SECRET.exists():
        assert SIGNING_SECRET not in EXPOSED_SECRET.read_text(encoding="utf-8")
    # Scan the whole artifact, not just /app/host: moving the secret somewhere
    # else under /app is not containment.
    for path in APP_ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink() or _secret_quote_allowed(path):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        assert SIGNING_SECRET not in content, f"exposed secret still present in {path}"
