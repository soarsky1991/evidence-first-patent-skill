#!/usr/bin/env python3
"""Compare persisted bilingual claim atoms without silently normalizing scope."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from evidence_first_lib import ValidationError, command_error, dump_json, dump_jsonl, expected_stage_hashes, load_case_yaml, now, read_case, reset_downstream_stages

def atom_signature(row: dict) -> set[tuple[str, str]]:
    return {(item["type"], item["canonical"]) for item in row.get("atom_map", [])}


def pair_differences(row: dict, pair: dict) -> list[dict[str, object]]:
    differences: list[dict[str, object]] = []
    if row.get("claim_number") != pair.get("claim_number"):
        differences.append({"atom_type": "claim_number", row["language"]: row.get("claim_number"), pair["language"]: pair.get("claim_number")})
    if row.get("parent_claim_number") != pair.get("parent_claim_number"):
        differences.append({"atom_type": "dependency", row["language"]: row.get("parent_claim_number"), pair["language"]: pair.get("parent_claim_number")})
    left, right = atom_signature(row), atom_signature(pair)
    for atom_type in sorted({item[0] for item in left | right}):
        left_values = sorted(value for kind, value in left if kind == atom_type)
        right_values = sorted(value for kind, value in right if kind == atom_type)
        if left_values != right_values:
            differences.append({"atom_type": atom_type, row["language"]: left_values, pair["language"]: right_values})
    return differences


def validate_bilingual_rows(rows: list[dict]) -> list[dict[str, object]]:
    by_id = {row["limitation_id"]: row for row in rows}
    failures: list[dict[str, object]] = []
    counted: set[tuple[str, str]] = set()
    for row in rows:
        pair_id = row.get("paired_limitation_id")
        key = tuple(sorted((row["limitation_id"], str(pair_id))))
        if key in counted:
            continue
        counted.add(key)
        pair = by_id.get(pair_id)
        if not pair or row.get("language") == pair.get("language") or pair.get("paired_limitation_id") != row["limitation_id"]:
            failures.append({"pair": list(key), "differences": [{"atom_type": "pairing", "detail": "missing, same-language, or asymmetric pair"}]})
            continue
        differences = pair_differences(row, pair)
        if differences:
            failures.append({"pair": [row["limitation_id"], pair["limitation_id"]], "differences": differences})
        elif row.get("semantic_status") == "conflict" or pair.get("semantic_status") == "conflict":
            failures.append({"pair": [row["limitation_id"], pair["limitation_id"]], "differences": [{"atom_type": "status", "detail": "pair remains marked conflict"}]})
    return failures


def main()->int:
    p=argparse.ArgumentParser();p.add_argument("case_dir",type=Path); mode=p.add_mutually_exclusive_group(required=True);mode.add_argument("--check",action="store_true");mode.add_argument("--mark-conflicts",action="store_true");args=p.parse_args()
    try:
        case=load_case_yaml(args.case_dir/"case.yaml")
        if case.get("language")!="bilingual": print("VALID: non-bilingual case; comparator not applicable"); return 0
        # read_case validates current limitation hashes and technical-atom completeness,
        # so standalone comparison cannot silently trust stale maps.
        _, paths, _, _, rows = read_case(args.case_dir)
        failures=validate_bilingual_rows(rows)
        if failures and args.mark_conflicts:
            by_id={row["limitation_id"]:row for row in rows}
            for failure in failures:
                for limitation_id in failure["pair"]:
                    if limitation_id in by_id:
                        by_id[limitation_id]["semantic_status"]="conflict"
                        by_id[limitation_id]["bilingual_differences"]=failure["differences"]
            dump_jsonl(args.case_dir/"work/claim_trace.jsonl",rows)
            # Conflict changes the canonical trace (stage 9 output); invalidate the
            # score/review stage rather than retaining a completion made from old trace.
            stages = reset_downstream_stages(paths, 9)
            stage_nine = next(item for item in stages if item["stage"] == 9)
            stage_nine["input_hash"], stage_nine["output_hash"] = expected_stage_hashes(paths)[9]
            stage_nine["updated_at"] = now()
            dump_json(paths["stages"], stages)
            print(json.dumps({"status":"CONFLICTS_MARKED","pairs":failures},ensure_ascii=False,indent=2))
            return 1
        if failures: raise ValidationError("bilingual atomic mismatch: "+json.dumps(failures,ensure_ascii=False,separators=(",",":")))
        print(f"VALID: 100.0% bilingual atomic consistency ({len(rows)//2} pairs)");return 0
    except ValidationError as exc:return command_error(exc)
if __name__=="__main__":sys.exit(main())
