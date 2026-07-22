#!/usr/bin/env python3
"""Validate the shipped media ledger against actual repository assets."""
from __future__ import annotations
import argparse, hashlib, re, sys
from pathlib import Path
from evidence_first_lib import ValidationError, command_error

REQUIRED=("asset_path","source_url","creator","license","license_url","retrieved_at","modifications","sha256")
ALLOWED={"CC0","CC BY 4.0","CC BY-SA 4.0","public-domain"}
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--ledger",type=Path,default=Path("public-assets/media-ledger.md"));p.add_argument("--root",type=Path);a=p.parse_args()
 try:
  lines=a.ledger.read_text(encoding="utf-8").splitlines(); header=None; rows=[]
  for line in lines:
   if line.startswith("| asset_path "): header=[x.strip() for x in line.strip("|").split("|")]; continue
   if header and line.startswith("| `"):
    values=[x.strip().strip('`') for x in line.strip("|").split("|")]; rows.append(dict(zip(header,values)))
  if not rows: raise ValidationError("media ledger has no asset rows")
  root=a.root.resolve() if a.root else a.ledger.resolve().parents[1]
  for row in rows:
   if any(not row.get(k) for k in REQUIRED): raise ValidationError("media ledger missing required field")
   if row["license"] not in ALLOWED or not row["license_url"].startswith("https://"): raise ValidationError("media ledger has unsupported license")
   if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",row["retrieved_at"]): raise ValidationError("media ledger invalid retrieval date")
   asset=root/row["asset_path"]
   if not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest()!=row["sha256"]: raise ValidationError("media ledger asset hash mismatch")
  print(f"VALID: {len(rows)} media assets");return 0
 except (OSError,ValidationError) as e:return command_error(e)
if __name__=='__main__':sys.exit(main())
