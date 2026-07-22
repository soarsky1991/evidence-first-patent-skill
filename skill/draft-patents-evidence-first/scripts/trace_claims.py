#!/usr/bin/env python3
"""Check claim limitation trace coverage and blocking semantic states."""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from evidence_first_lib import ValidationError, command_error, load_jsonl

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("case_dir", type=Path); p.add_argument("--check", action="store_true", required=True); args=p.parse_args()
    try:
        evidence={r["evidence_id"] for r in load_jsonl(args.case_dir/"work/evidence.jsonl","evidence")}; rows=load_jsonl(args.case_dir/"work/claim_trace.jsonl","claim trace")
        if not rows: raise ValidationError("no claim limitation traces")
        failures=[]
        for row in rows:
            if row.get("semantic_status") in {"missing","conflict"}: failures.append(f"{row.get('limitation_id')}: {row.get('semantic_status')}")
            if not row.get("evidence_ids") or any(e not in evidence for e in row["evidence_ids"]): failures.append(f"{row.get('limitation_id')}: unresolved evidence")
        if failures: raise ValidationError("; ".join(failures))
        print(f"VALID: 100.0% trace coverage ({len(rows)} limitations)"); return 0
    except ValidationError as exc: return command_error(exc)
if __name__ == "__main__": sys.exit(main())
