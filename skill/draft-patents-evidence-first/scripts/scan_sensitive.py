#!/usr/bin/env python3
"""Scan local text-like content for blocking confidentiality markers."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from evidence_first_lib import sensitive_findings

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("target",type=Path);p.add_argument("--denylist",type=Path);p.add_argument("--format",choices=["text","json"],default="text");args=p.parse_args()
    if not args.target.exists(): print("ERROR: target does not exist",file=sys.stderr);return 2
    findings=sensitive_findings(args.target,args.denylist)
    if args.format=="json": print(json.dumps({"findings":findings,"count":len(findings)},ensure_ascii=False,indent=2))
    else:
        for item in findings: print(f"{item['kind']}: {item['path']}")
        print(f"findings: {len(findings)}")
    return 1 if findings else 0
if __name__=="__main__":sys.exit(main())
