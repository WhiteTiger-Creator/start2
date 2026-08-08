# Batch Scheduler — Governance Review Log
Scheduling governance archive for the failed batch-platform rollout (2026-Q1 through 2026-Q2).

## Executive Summary
This archive records the scheduling governance board's decisions for the single-machine batch scheduler. It is a record of where the board departed from ordinary shop practice, not a restatement of it: anything the board did not rule on is left to standard production-scheduling convention and is not repeated here. The February draft proposals were revisited during the 2026-05 governance review and several were reversed; two March interim decisions were revised in the same review. Where a draft or interim conflicts with a later decision, the later dated decision governs. `/app/docs/report_spec.json` is the output contract only and carries no board decision.

## Governance Review Archive
Routine entries are context only. #SCH-ticketed proposal and decision quotes are the authoritative record for scheduler behaviour.

### Review entry 2000 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2000. Fixture jigs recertified; no scheduler-relevant configuration changed.
Reviewers should reconcile behaviour questions against #SCH governance decisions rather than chat excerpts.

### Review entry 2001 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2001. Coolant audit sampled cross-shift logs; no scheduler-relevant findings for this cell.
> **Recovery draft proposal (2026-02-05 - #SCH-5004)** Anders: the objective is total UNWEIGHTED tardiness; the job weights are recorded for reporting only and do not enter it *(Superseded — reversed in the 2026-05 governance review.)*
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2002 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2002. Synthetic job injection verified dispatch to the cell operators for this line.
> **Recovery draft proposal (2026-02-06 - #SCH-5006)** Rosa: the first scheduled job incurs NO setup — the machine starts ready — and a setup applies only between consecutive jobs *(Superseded — reversed in the 2026-05 governance review.)*
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2003 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2003. Noise review: repeated dispatch traced to a flapping terminal, suppressed at the source.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2004 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2004. Quarterly access recertification touched this line; nothing scheduler-relevant changed.
> **Recovery draft proposal (2026-02-07 - #SCH-5008)** Anders: a job's setup is applied AFTER its processing rather than before it, on the reasoning that the changeover tears the fixture down for the next family *(Superseded — reversed in the 2026-05 governance review.)*
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2005 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2005. Capacity review noted rising job volume; thresholds unchanged outside the governance process.
> **Recovery draft proposal (2026-02-08 - #SCH-5010)** Rosa: when two orders tie on the objective, prefer the one with the smaller makespan; if still tied, prefer the smaller total completion time *(Superseded — reversed in the 2026-05 governance review.)*
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2006 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2006. Replica sync drill completed; dispatch stayed within the governance SLO.
> **Recovery draft proposal (2026-02-09 - #SCH-5012)** Anders: dispatch may keep the existing greedy weighted-shortest-processing-time order; an approximate order within a few percent of optimal is acceptable for release *(Superseded — reversed in the 2026-05 governance review.)*
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2007 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2007. Change-board reviewed stale exception approvals; owners pinged before the next cycle.
> **Recovery draft proposal (2026-02-12 - #SCH-5020)** Rosa: a released job names one routing template and takes that template's own fields; templates do not chain, and a release entry's own fields are advisory annotations that never displace a template value *(Superseded — reversed in the 2026-05 governance review.)*
No scheduler semantics changed elsewhere in this entry; parameters remain as approved by the governance board.

### Review entry 2008 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2008. Rule-set rollback rehearsal ran clean; no changes to scheduler parameters were approved.
Reviewers should reconcile behaviour questions against #SCH governance decisions rather than chat excerpts.

### Review entry 2009 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2009. Vendor ticket on terminal retries closed; dispatch within contractual budget.
> **Governance decision (2026-03-06 - #SCH-5109)** Priya: interim grace rule — a single global grace of 3 time units is allowed before a job's tardiness begins to accrue, regardless of its family *(Revised — see the 2026-05 governance review.)*
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2010 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2010. Dashboard tiles for job volume lagged during rule refresh; attributed to terminal staleness.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2011 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2011. Topology audit sampled cross-account roles; no scheduler-relevant findings for this line.
> **Governance decision (2026-03-08 - #SCH-5115)** Priya: interim weighting — the objective uses the raw job weight; any per-family `weight_multiplier` in the policy file is advisory and does not scale it *(Revised — see the 2026-05 governance review.)*
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2012 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2012. Synthetic job injection verified dispatch to the cell operators for this line.
> **Governance decision (2026-03-12 - #SCH-5122)** Lena: interim routing expansion — follow a template's `extends` one level beyond the template the release names and no further; a job id released more than once takes its LATEST release; the expanded set is written in release order *(Revised — see the 2026-05 governance review.)*
No scheduler semantics changed elsewhere in this entry; parameters remain as approved by the governance board.

### Review entry 2013 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2013. Noise review: repeated dispatch traced to a flapping terminal, suppressed at the source.
Reviewers should reconcile behaviour questions against #SCH governance decisions rather than chat excerpts.

### Review entry 2014 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2014. Quarterly access recertification touched this line; nothing scheduler-relevant changed.
> **Governance decision (2026-05-02 - #SCH-5101)** Yusuf: machine state at the start of the horizon (final, reversing the drafts #SCH-5006 and #SCH-5008). The machine is NOT changeover-neutral at time zero: it stands in the setup matrix's `initial_family`, and the first scheduled job incurs the changeover into its own family exactly as any later job does. A changeover is taken BEFORE the job it prepares for, never after it. The board declines to carry any release, ready or availability date: the horizon opens at time zero for every job
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2015 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2015. Capacity review noted rising job volume; thresholds unchanged outside the governance process.
> **Governance decision (2026-05-03 - #SCH-5102)** Yusuf: grace and weighting (final, reversing #SCH-5004 and revising #SCH-5109 and #SCH-5115). The objective stays total weighted tardiness, with two local departures. A job's family carries a grace period — the resolved `tardiness_grace` — that is allowed to elapse past its due date before any tardiness accrues, and the grace is per family rather than the single global figure the interim allowed. The weight a job contributes is its own weight scaled by its family's resolved `weight_multiplier`; the multiplier is no longer advisory
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2016 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2016. Replica sync drill completed; dispatch stayed within the governance SLO.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2017 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2017. Change-board reviewed stale exception approvals; owners pinged before the next cycle.
> **Governance decision (2026-05-04 - #SCH-5108)** Lena: the instance's `precedence` pairs are a HARD constraint, not a preference the objective may trade away. An order that violates one is rejected outright rather than penalised, however good its objective
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2018 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2018. Vendor ticket on terminal retries closed; dispatch within contractual budget.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2019 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2019. Rule-set rollback rehearsal ran clean; no changes to scheduler parameters were approved.
> **Governance decision (2026-05-06 - #SCH-5120)** Marek: optimisation target (final, reversing the greedy-approximation draft #SCH-5012). The scheduler must emit an order that attains the PROVEN MINIMUM of the objective over all precedence-feasible orders. An approximation is not acceptable: on the shipped instances a weighted-shortest-processing-time or an earliest-due-date order is strictly worse than that minimum, and the board will not accept either
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2020 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2020. Dashboard tiles for job volume lagged during rule refresh; attributed to terminal staleness.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2021 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2021. Topology audit sampled cross-account roles; no scheduler-relevant findings for this line.
> **Governance decision (2026-05-20 - #SCH-5160)** Lena: routing expansion (final, superseding the draft #SCH-5020 and revising the interim #SCH-5122). The releases in /app/data/job_routings.json carry no operation data of their own; each names a routing template in /app/data/routing_templates.json, and a template may itself extend another. Expansion is bounded: follow `extends` at most FOUR templates beyond the one the release names, and ignore anything further out. Each of family, processing time, due date and weight takes the nearest value that supplies it — a release entry's own field displaces every template, the named template displaces the one it extends, and so on outward. A routing name with no entry in the template library contributes nothing and ends the chain there; a template entry that supplies no fields of its own contributes nothing but does not end it. Anything still unset takes the shop calendar baseline in /app/data/machine_calendar.json — `default_cell_family`, `nominal_operation_time`, `standard_lead_time`, `default_priority_weight`. Where a job id is released more than once the FIRST release in file order stands and the later ones are discarded. The expanded set is written to /app/data/jobs.json in ascending job-id order and carries the released precedence pairs in file order with exact duplicates dropped; the three source files are left as they are, and the scheduler reads nothing but the expanded instance
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2022 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2022. Synthetic job injection verified dispatch to the cell operators for this line.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2023 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2023. Noise review: repeated dispatch traced to a flapping terminal, suppressed at the source.
> **Governance decision (2026-05-10 - #SCH-5145)** Yusuf: tie-break (final, reversing the makespan draft #SCH-5010). When more than one precedence-feasible order attains the minimum, emit the one whose job-id sequence is LEXICOGRAPHICALLY SMALLEST — compare the ordered lists of job-id strings element by element and take the smallest. This makes the accepted schedule unique. Makespan and total completion time do NOT break ties
Thread archived; see the #SCH decision entries for anything affecting scheduler behaviour.

### Review entry 2024 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2024. Quarterly access recertification touched this line; nothing scheduler-relevant changed.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2025 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2025. Capacity review noted rising job volume; thresholds unchanged outside the governance process.
Reviewers should reconcile behaviour questions against #SCH governance decisions rather than chat excerpts.

### Review entry 2026 — line C (press cell)
Shift lead logged a routine observation for the press cell during review window 2026. Replica sync drill completed; dispatch stayed within the governance SLO.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2027 — line D (weld cell)
Shift lead logged a routine observation for the weld cell during review window 2027. Change-board reviewed stale exception approvals; owners pinged before the next cycle.
> **Governance decision (2026-05-18 - #SCH-5150)** Priya: scheduling policy baseline, read from /app/data/scheduling_policy.json. Any field the policy file omits keeps its baseline: `weight_multiplier` = 1, `tardiness_grace` = 0. The baseline applies per family before any override
Historical spreadsheet exports remain archived and non-authoritative for the JSON scheduler acceptance.

### Review entry 2028 — line A (forge cell)
Shift lead logged a routine observation for the forge cell during review window 2028. Synthetic job injection verified dispatch to the cell operators for this line.
No scheduler semantics changed in this entry; parameters remain as approved by the governance board.

### Review entry 2029 — line B (mill cell)
Shift lead logged a routine observation for the mill cell during review window 2029. Rule-set rollback rehearsal ran clean; no changes to scheduler parameters were approved.
> **Governance decision (2026-05-18 - #SCH-5152)** Priya: policy resolution, per family, in three layers. Start from the #SCH-5150 baseline; overlay every field the policy file's `default` object supplies, which need not be complete — an omitted field keeps its baseline; then overlay every field that family's entry in `family_overrides` supplies, an override naming only the fields it changes and inheriting the rest. A family with no entry resolves to the `default` layer
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
