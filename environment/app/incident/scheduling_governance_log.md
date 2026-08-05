# Batch Scheduler — Governance Review Log
Scheduling governance archive for the failed batch-platform rollout (2026-Q1 through 2026-Q2).

## Executive Summary
How the single-machine batch scheduler is *meant* to behave — how completion times accumulate under sequence-dependent family setups, how tardiness is weighted, how precedence constrains the order, what the optimisation target is, and how ties between equally-good orders are broken — was settled incrementally by the scheduling governance board, and those decisions live in the review entries below, not in any single summary. The board's target is the PROVEN minimum total weighted tardiness: a greedy priority rule (weighted-shortest-processing-time, earliest-due-date) is precedence-feasible but strictly suboptimal on the shipped instances, so shipping a heuristic order produces the wrong answer. The February draft proposals were revisited during the 2026-05 governance review and several were reversed; where a draft or interim conflicts with a later decision, the later dated decision governs. `/app/docs/report_spec.json` is the output contract only.

## Governance Review Archive
Routine entries are context only. #SCH-ticketed proposal and decision quotes are the authoritative record for scheduler behaviour.

### Review entry 2000 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2000. Fixture jigs recertified; no scheduler-relevant configuration changed.
Reviewers should reconcile behaviour questions against #SCH governance decisions rather than chat excerpts.

### Review entry 2001 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2001. Coolant audit sampled cross-shift logs; no scheduler-relevant findings for this cell.
> **Recovery draft proposal (2026-02-05 - #SCH-5004)** Anders: the objective is total UNWEIGHTED tardiness — sum over jobs of max(0, completion - due); job weights are recorded for reporting only and do not enter the objective *(Superseded — reversed in the 2026-05 governance review.)*
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2002 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2002. Synthetic job injection verified dispatch to the cell operators for this line.
> **Recovery draft proposal (2026-02-06 - #SCH-5006)** Rosa: the first scheduled job incurs NO setup — the machine starts ready — and setup[i][j] is added only between consecutive jobs i then j *(Superseded — reversed in the 2026-05 governance review.)*
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2003 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2003. Noise review: repeated dispatch traced to a flapping terminal, suppressed at the source.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2004 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2004. Quarterly access recertification touched this line; nothing scheduler-relevant changed.
> **Recovery draft proposal (2026-02-07 - #SCH-5008)** Anders: a job's setup is applied AFTER its processing (setup tears down the fixture for the next family), so completion = previous_completion + processing + setup_to_next *(Superseded — reversed in the 2026-05 governance review.)*
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2005 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2005. Capacity review noted rising job volume; thresholds unchanged outside the governance process.
> **Recovery draft proposal (2026-02-08 - #SCH-5010)** Rosa: when two orders tie on the objective, prefer the one with the smaller makespan (last completion time); if still tied, prefer the smaller total completion time *(Superseded — reversed in the 2026-05 governance review.)*
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2006 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2006. Replica sync drill completed; dispatch stayed within the governance SLO.
> **Recovery draft proposal (2026-02-09 - #SCH-5012)** Anders: dispatch may keep the existing greedy weighted-shortest-processing-time order (smallest processing_time / weight among eligible jobs); an approximate order within a few percent of optimal is acceptable for release *(Superseded — reversed in the 2026-05 governance review.)*
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2007 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2007. Change-board reviewed stale exception approvals; owners pinged before the next cycle.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2008 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2008. Rule-set rollback rehearsal ran clean; no changes to scheduler parameters were approved.
Reviewers should reconcile behaviour questions against #SCH governance decisions rather than chat excerpts.

### Review entry 2009 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2009. Vendor ticket on terminal retries closed; dispatch within contractual budget.
> **Governance decision (2026-03-06 - #SCH-5109)** Priya: interim tardiness rule — a single global grace of 3 time units applies to every job's tardiness regardless of family: tardiness = max(0, completion - due - 3) *(Revised — see the 2026-05 governance review.)*
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2010 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2010. Dashboard tiles for job volume lagged during rule refresh; attributed to terminal staleness.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2011 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2011. Topology audit sampled cross-account roles; no scheduler-relevant findings for this line.
> **Governance decision (2026-03-08 - #SCH-5115)** Priya: interim weighting — the effective weight used in the objective is the raw job weight; any per-family weight multiplier in the policy file is advisory and does not scale the objective *(Revised — see the 2026-05 governance review.)*
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2012 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2012. Synthetic job injection verified dispatch to the cell operators for this line.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2013 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2013. Noise review: repeated dispatch traced to a flapping terminal, suppressed at the source.
Reviewers should reconcile behaviour questions against #SCH governance decisions rather than chat excerpts.

### Review entry 2014 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2014. Quarterly access recertification touched this line; nothing scheduler-relevant changed.
> **Governance decision (2026-05-02 - #SCH-5101)** Yusuf: objective time model (final, reversing the drafts #SCH-5006 and #SCH-5008): the machine begins in the setup matrix's `initial_family` state; jobs run one at a time from time 0. For each job, its SETUP is applied BEFORE its processing. The first scheduled job DOES incur a setup, equal to setup[initial_family][job.family]; between consecutive jobs a then b the setup is setup[a.family][b.family]. A job's start_time = running_time + that setup; its completion_time = start_time + processing_time; the running time then becomes that completion_time. setup_from_prev on a placement is exactly that setup value
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2015 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2015. Capacity review noted rising job volume; thresholds unchanged outside the governance process.
> **Governance decision (2026-05-03 - #SCH-5102)** Yusuf: tardiness and weighting (final, reversing #SCH-5004 and #SCH-5115): a job's tardiness = max(0, completion_time - due_date - grace), where grace is the resolved per-family `tardiness_grace` policy value. effective_weight = job.weight * the resolved per-family `weight_multiplier`. weighted_tardiness = effective_weight * tardiness. The objective is the SUM of weighted_tardiness over all jobs. Job weights and the family multiplier DO enter the objective
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2016 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2016. Replica sync drill completed; dispatch stayed within the governance SLO.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2017 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2017. Change-board reviewed stale exception approvals; owners pinged before the next cycle.
> **Governance decision (2026-05-04 - #SCH-5108)** Lena: precedence is a HARD constraint. Each edge [a, b] in the instance's `precedence` list requires job a to complete before job b starts — equivalently, a appears before b in the sequence. A job may be placed only once every one of its precedence predecessors has already been placed. The emitted order must be precedence-feasible; an infeasible order is rejected outright
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2018 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2018. Vendor ticket on terminal retries closed; dispatch within contractual budget.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2019 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2019. Rule-set rollback rehearsal ran clean; no changes to scheduler parameters were approved.
> **Governance decision (2026-05-06 - #SCH-5120)** Marek: optimisation target (final, reversing the greedy-approximation draft #SCH-5012): the scheduler must emit an order that attains the PROVEN MINIMUM total weighted tardiness over all precedence-feasible orders — the exact optimum, not a priority-rule approximation. On the shipped instances a weighted-shortest-processing-time or earliest-due-date order is strictly worse than this minimum and is not acceptable. The minimum is well-defined; because setups are sequence-dependent, completion times depend on the whole order, so the optimiser must reason over orderings, not sort by a per-job key
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2020 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2020. Dashboard tiles for job volume lagged during rule refresh; attributed to terminal staleness.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2021 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2021. Topology audit sampled cross-account roles; no scheduler-relevant findings for this line.
> **Governance decision (2026-05-07 - #SCH-5140)** Lena: setup-matrix canonicalization: read `initial_family`, `families` and the `setup` map from /app/data/setup_matrix.json at that fixed absolute path (--input never relocates it). Normalize every family name (source, target, initial and each job's family) via str(...).strip().lower(); coerce every setup cell and every job field to int with the contract coercion. The setup between a job of family f run immediately after family g is setup[g][f]; the machine's starting family is `initial_family`
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2022 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2022. Synthetic job injection verified dispatch to the cell operators for this line.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2023 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2023. Noise review: repeated dispatch traced to a flapping terminal, suppressed at the source.
> **Governance decision (2026-05-10 - #SCH-5145)** Yusuf: tie-break (final, reversing the makespan draft #SCH-5010): when more than one precedence-feasible order attains the minimum objective, emit the one whose job-id sequence is LEXICOGRAPHICALLY SMALLEST — compare the ordered lists of job-id strings element by element and take the smallest. This makes the optimal schedule unique. Makespan and total completion time do NOT break ties
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2024 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2024. Quarterly access recertification touched this line; nothing scheduler-relevant changed.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2025 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2025. Capacity review noted rising job volume; thresholds unchanged outside the governance process.
> **Governance decision (2026-05-11 - #SCH-5148)** Marek: summary aggregation domains: total_weighted_tardiness, total_tardiness, tardy_job_count (jobs with tardiness > 0), max_tardiness, total_setup_time and total_completion_time are sums/maxima over EVERY placement in the emitted order; makespan is the last job's completion_time (0 for an empty instance). weighted_tardiness_by_family maps each family PRESENT among the jobs (ascending) to the sum of its jobs' weighted_tardiness, 0 when none are tardy. distinct_family_transitions counts distinct (from_family, to_family) pairs traversed including the initial-family transition into the first job
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2026 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2026. Replica sync drill completed; dispatch stayed within the governance SLO.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2027 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2027. Change-board reviewed stale exception approvals; owners pinged before the next cycle.
> **Governance decision (2026-05-18 - #SCH-5150)** Priya: scheduling policy baseline (read from /app/data/scheduling_policy.json at that fixed absolute path). Any field the policy file omits keeps its baseline: weight_multiplier = 1; tardiness_grace = 0. The baseline applies per family before any override
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2028 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2028. Synthetic job injection verified dispatch to the cell operators for this line.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2029 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2029. Rule-set rollback rehearsal ran clean; no changes to scheduler parameters were approved.
> **Governance decision (2026-05-18 - #SCH-5152)** Priya: policy resolution, per family, in three layers: start from the #SCH-5150 baseline; overlay every field the policy file's `default` object supplies (it need not be complete — an omitted field keeps its baseline); then overlay every field that family's entry in `family_overrides` supplies (an override names only the fields it changes and inherits the rest). Coerce every policy value to int. policy_checksum is the SHA-256 hex digest of one line per resolved policy — first `default`, then each family named in `family_overrides` in ascending name order — each line being the name followed by the field values in the order weight_multiplier, tardiness_grace, joined by `|`, lines joined by a single newline with no trailing newline, hashed over UTF-8
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2030 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2030. Dashboard tiles for job volume lagged during rule refresh; attributed to terminal staleness.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2031 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2031. Topology audit sampled cross-account roles; no scheduler-relevant findings for this line.
Reviewers should reconcile behaviour questions against #SCH governance decisions rather than chat excerpts.

### Review entry 2032 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2032. Vendor ticket on terminal retries closed; dispatch within contractual budget.
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.
