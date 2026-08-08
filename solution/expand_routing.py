#!/usr/bin/env python3
"""Expand the released routings into the concrete job instance the scheduler reads.

Implements the scheduling governance board's final routing decision (#SCH-5160 in
/app/incident/scheduling_governance_log.md), which supersedes the #SCH-5020 draft
and revises the #SCH-5122 interim: follow a routing template's ``extends`` chain
up to four templates beyond the one the release names, take for each of family,
processing time, due date and weight the nearest value that supplies it (the
release entry's own field first, then the named template, then outwards), treat a
routing name absent from the template library as contributing nothing and ending
the chain, treat a template that supplies no fields of its own as contributing
nothing without ending it, fall back to the shop calendar baseline for anything
still unset, keep only the first release of a repeated job id, and write the
expanded set to /app/data/jobs.json in ascending job-id order with the released
precedence pairs in file order and exact duplicates dropped.
"""

from __future__ import annotations

import json
from pathlib import Path

ROUTINGS_PATH = Path("/app/data/job_routings.json")
TEMPLATES_PATH = Path("/app/data/routing_templates.json")
CALENDAR_PATH = Path("/app/data/machine_calendar.json")
INSTANCE_PATH = Path("/app/data/jobs.json")

OPERATION_FIELDS = ("family", "processing_time", "due_date", "weight")
EXTENDS_BOUND = 4  # templates followed beyond the one the release names


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


def expand(releases: list[dict], templates: dict, calendar: dict) -> list[dict]:
    baseline = {
        "family": canon_name(calendar["default_cell_family"]),
        "processing_time": coerce_int(calendar["nominal_operation_time"]),
        "due_date": coerce_int(calendar["standard_lead_time"]),
        "weight": coerce_int(calendar["default_priority_weight"]),
    }
    seen: set[str] = set()
    jobs: list[dict] = []
    for release in releases:
        job_id = str(release["id"]).strip()
        if job_id in seen:  # a repeated id keeps its FIRST release
            continue
        seen.add(job_id)
        values = {f: release[f] for f in OPERATION_FIELDS if f in release}
        name = canon_name(release.get("routing", ""))
        hops = 0
        while hops <= EXTENDS_BOUND:
            node = templates.get(name)
            if node is None:  # unresolved routing: contributes nothing, ends the chain
                break
            for field in OPERATION_FIELDS:
                if field in node and field not in values:
                    values[field] = node[field]
            if "extends" not in node:
                break
            name = canon_name(node["extends"])
            hops += 1
        jobs.append({
            "id": job_id,
            "family": canon_name(values["family"]) if "family" in values else baseline["family"],
            "processing_time": coerce_int(values.get("processing_time", baseline["processing_time"])),
            "due_date": coerce_int(values.get("due_date", baseline["due_date"])),
            "weight": coerce_int(values.get("weight", baseline["weight"])),
        })
    jobs.sort(key=lambda job: job["id"])
    return jobs


def dedupe_precedence(pairs: list) -> list:
    out: list = []
    for pair in pairs:
        edge = [str(pair[0]).strip(), str(pair[1]).strip()]
        if edge not in out:
            out.append(edge)
    return out


def main() -> None:
    released = json.loads(ROUTINGS_PATH.read_text(encoding="utf-8"))
    templates = {
        canon_name(name): node
        for name, node in json.loads(TEMPLATES_PATH.read_text(encoding="utf-8")).items()
    }
    calendar = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    instance = {
        "jobs": expand(released["jobs"], templates, calendar),
        "precedence": dedupe_precedence(released.get("precedence", [])),
    }
    INSTANCE_PATH.write_text(json.dumps(instance, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
