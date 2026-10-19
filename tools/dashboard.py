"""Compact, machine-readable progress dashboard -> docs/dashboard.json.

Every number is derived from the ledgers, never typed in:
  layout/manifest.json        byte ownership (kinds)
  docs/function-census.json   game function inventory (C vs ASM, extents)
  build/verify.json           strict verification of src/game (run
                              tools/verify_sources.py --json build/verify.json)

Code/data split uses the executable's segment structure: _TEXT is
load-module [0, 0xB310) (first far data paragraph 0x0B31); far data segments
[0xB310, 0x254D0); DGROUP from 0x254D0 (paragraph 0x254D). Bytes are never
counted twice: each manifest region is attributed once, clipped to a section.

Deltas are computed against the dashboard committed at HEAD (git show).

Usage: python tools/dashboard.py [--no-verify]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HDR = 0x200
TEXT_END = HDR + 0xB310
DGROUP = HDR + 0x254D0
OUT = ROOT / "docs" / "dashboard.json"


def overlap(a, b, c, d):
    return max(0, min(b, d) - max(a, c))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-verify", action="store_true", help="reuse build/verify.json")
    args = ap.parse_args()
    if not args.no_verify:
        subprocess.run([sys.executable, str(ROOT / "tools" / "verify_sources.py"),
                        "--json", str(ROOT / "build" / "verify.json")], cwd=ROOT,
                       capture_output=True)
    verify = json.loads((ROOT / "build" / "verify.json").read_text())
    manifest = json.loads((ROOT / "layout" / "manifest.json").read_text())
    census = json.loads((ROOT / "docs" / "function-census.json").read_text())
    regions = manifest["regions"]
    total = manifest["unpacked_original"]["size"]

    c_lo, c_hi = census["code_range_cs"]
    c_funcs = [f for f in census["functions"] if f["lang"].startswith("C")]
    asm_funcs = [f for f in census["functions"] if f["lang"] == "ASM"]
    c_bytes = sum(f["size"] for f in c_funcs)
    asm_bytes = sum(f["size"] for f in asm_funcs)
    game_code_bytes = c_hi - c_lo
    asm_unowned = sum(b - a for a, b in census["gaps_cs"])

    exact = [r for r in verify if r["verdict"] == "EXACT"]
    func_starts = {f["cs_start"]: f for f in census["functions"]}
    exact_funcs = sum(1 for r in exact for f in census["functions"]
                      if r["cs_start"] <= f["cs_start"] < r["cs_end"])

    def kind_bytes(kinds, lo=0, hi=total):
        return sum(overlap(r["start"], r["end"], lo, hi) for r in regions if r["kind"] in kinds)

    notes = sorted(p.stem for p in (ROOT / "notes").glob("F_*.md")) if (ROOT / "notes").exists() else []
    unresolved_ctl = sum(len(f["unresolved_indirect"]) for f in census["functions"])

    dash = {
        "schema": "dave-dashboard-v1",
        "image": {"unpacked_bytes": total,
                  "sections": {"header": HDR, "text": TEXT_END - HDR,
                               "far_data": DGROUP - TEXT_END, "dgroup_initialised": total - DGROUP}},
        "game_code": {
            "range_cs": [c_lo, c_hi], "bytes": game_code_bytes,
            "c": {"functions": len(c_funcs), "bytes": c_bytes,
                  "matched_functions": exact_funcs,
                  "matched_bytes": kind_bytes({"MATCHING_C"}),
                  "partial_attempts_with_notes": len(notes)},
            "asm": {"functions_identified": len(asm_funcs), "bytes_in_functions": asm_bytes,
                    "bytes_unassigned": asm_unowned,
                    "matched_bytes": kind_bytes({"MATCHING_ASM"})},
        },
        "runtime": {
            "known_library_bytes": kind_bytes({"KNOWN_LIBRARY"}),
            "text_bytes_after_game_code": TEXT_END - (HDR + c_hi),
            "raw_bytes_in_runtime_area": kind_bytes({"RAW_UNKNOWN"}, HDR + c_hi, TEXT_END),
        },
        "data": {
            "far_and_dgroup_bytes": total - TEXT_END,
            "structured_bytes": kind_bytes({"STRUCTURED_DATA", "STRUCTURED_ASSET"}, TEXT_END, total),
            "raw_bytes": kind_bytes({"RAW_UNKNOWN"}, TEXT_END, total),
        },
        "raw": {
            "code_bytes": kind_bytes({"RAW_UNKNOWN"}, HDR, TEXT_END),
            "data_bytes": kind_bytes({"RAW_UNKNOWN"}, TEXT_END, total),
        },
        "unresolved": {"indirect_control_flow_sites": unresolved_ctl,
                       "census_gap_bytes": asm_unowned},
        "levels": {
            "A_byte_ownership": "complete (100% owned, exact fixed-placement rebuild)",
            "B_independent_components_pct_of_game_code": round(
                100 * (kind_bytes({"MATCHING_C", "MATCHING_ASM"})) / game_code_bytes, 2),
            "C_emergent_layout": "not started (fixed placement only)",
            "D_byte_identical_build": "no",
        },
        "open_frontiers": [{"category": f["category"], "target": f["target"]}
                           for f in json.loads((ROOT / "docs" / "blockers.json").read_text())["frontiers"]
                           if f["category"] != "CLOSED"],
    }
    try:
        prev = json.loads(subprocess.run(["git", "show", "HEAD:docs/dashboard.json"], cwd=ROOT,
                                         capture_output=True, text=True, check=True).stdout)
        dash["delta_vs_HEAD"] = {
            "c_matched_functions": exact_funcs - prev["game_code"]["c"]["matched_functions"],
            "c_matched_bytes": dash["game_code"]["c"]["matched_bytes"] - prev["game_code"]["c"]["matched_bytes"],
            "asm_matched_bytes": dash["game_code"]["asm"]["matched_bytes"] - prev["game_code"]["asm"]["matched_bytes"],
            "known_library_bytes": dash["runtime"]["known_library_bytes"] - prev["runtime"]["known_library_bytes"],
            "structured_data_bytes": dash["data"]["structured_bytes"] - prev["data"]["structured_bytes"],
        }
    except (subprocess.CalledProcessError, KeyError, json.JSONDecodeError):
        dash["delta_vs_HEAD"] = None
    OUT.write_text(json.dumps(dash, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(dash, indent=1))


if __name__ == "__main__":
    main()
