#!/usr/bin/env python3
"""Detect or deterministically collapse duplicate verified patent-family rows."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from evidence_first_lib import ValidationError, command_error, dump_jsonl, load_jsonl

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("case_dir", type=Path); p.add_argument("--check", action="store_true"); args=p.parse_args()
    try:
        path=args.case_dir/"work/sources.jsonl"; rows=load_jsonl(path,"sources")
        seen={}; duplicates=[]; retained=[]
        for row in rows:
            family=row.get("family_id") if row.get("source_type")=="patent" else None
            if family and family in seen:
                duplicates.append((row["source_id"], family)); continue
            if family: seen[family]=row["source_id"]
            retained.append(row)
        if args.check:
            if duplicates: raise ValidationError("duplicate patent families: " + ", ".join(f"{sid} ({family})" for sid,family in duplicates))
            print("VALID: no duplicate patent families"); return 0
        dump_jsonl(path, retained); print(f"DEDUPED: removed {len(duplicates)} duplicate patent family record(s)"); return 0
    except ValidationError as exc: return command_error(exc)
if __name__ == "__main__": sys.exit(main())
