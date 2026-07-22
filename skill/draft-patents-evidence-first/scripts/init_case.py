#!/usr/bin/env python3
"""Initialize a portable Evidence-First Patent case directory."""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path
from evidence_first_lib import SCHEMA_VERSION, LANGUAGES, PATENT_TYPES, case_paths, dump_case_yaml, dump_json, dump_jsonl, ensure_output_template, now

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("case_dir", type=Path); p.add_argument("--case-id", required=True)
    p.add_argument("--language", required=True, choices=sorted(LANGUAGES)); p.add_argument("--patent-type", required=True, choices=sorted(PATENT_TYPES)); p.add_argument("--critical-date")
    args = p.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", args.case_id):
        print("ERROR: --case-id must match ^[a-z0-9][a-z0-9-]{2,63}$", file=sys.stderr); return 2
    if args.case_dir.exists() and any(args.case_dir.iterdir()):
        print("ERROR: CASE_DIR already exists and is not empty", file=sys.stderr); return 2
    if args.critical_date:
        import datetime as dt
        try: dt.date.fromisoformat(args.critical_date)
        except ValueError: print("ERROR: --critical-date must be YYYY-MM-DD", file=sys.stderr); return 2
    args.case_dir.mkdir(parents=True, exist_ok=True); paths = case_paths(args.case_dir)
    paths["input"].mkdir(); paths["output"].mkdir(); paths["package"].mkdir(); paths["sources"].parent.mkdir()
    dump_case_yaml(paths["case"], {"schema_version": SCHEMA_VERSION, "case_id": args.case_id, "language": args.language, "jurisdiction": "CN", "patent_type": args.patent_type, "critical_date": args.critical_date, "priority_claimed": False, "confidentiality_mode": "local_only", "human_gate": {"selected_concept_id": None, "approved_by": None, "approved_at": None, "public_boundary_confirmed": False}})
    for key in ("sources", "evidence", "trace"): dump_jsonl(paths[key], [])
    dump_json(paths["scorecard"], {"schema_version": SCHEMA_VERSION, "generated_at": now(), "evidence_coverage_pct": 0.0, "unsupported_measured_claims": 0, "duplicate_patent_families": 0, "claim_trace_coverage_pct": 0.0, "bilingual_atomic_consistency_pct": None, "confidentiality_findings": 0, "blocking_findings": ["human selection gate not recorded"], "status": "BLOCKED"})
    dump_json(paths["stages"], [{"stage": i, "status": "pending", "input_hash": None, "output_hash": None, "updated_at": now(), "blocking_reasons": []} for i in range(1,11)])
    ensure_output_template(paths)
    print(args.case_dir); return 0

if __name__ == "__main__": sys.exit(main())
