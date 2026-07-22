#!/usr/bin/env python3
"""Persist the controlling-request language for an auto-language local case."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from evidence_first_lib import (
    ValidationError, case_paths, command_error, dump_json, expected_stage_hashes,
    load_case_yaml, load_json, reset_downstream_stages,
)

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("case_dir",type=Path); p.add_argument("--language",choices=["zh-CN","en-US"],required=True); a=p.parse_args()
    try:
        if load_case_yaml(a.case_dir/"case.yaml").get("language") != "auto": raise ValidationError("case language is not auto")
        paths = case_paths(a.case_dir); path = paths["stages"]; stages = load_json(path)
        if not isinstance(stages, list) or not stages or not isinstance(stages[0], dict) or stages[0].get("stage") != 1:
            raise ValidationError("stage_status: stage 1 required for auto language resolution")
        changed = stages[0].get("resolved_language") != a.language
        stages[0]["resolved_language"] = a.language
        if changed:
            reset_downstream_stages(paths, 1, stages)
        # expected_stage_hashes reads the persisted resolution as part of stage one.
        dump_json(path, stages)
        if stages[0].get("status") == "complete":
            stages[0]["input_hash"], stages[0]["output_hash"] = expected_stage_hashes(paths)[1]
        dump_json(path, stages)
        print(f"RESOLVED: {a.language}"); return 0
    except ValidationError as exc: return command_error(exc)
if __name__=="__main__": sys.exit(main())
