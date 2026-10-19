"""Promote docs/library-map.json (tools/library_scanner2.py) into layout/manifest.json.

Library _TEXT area [0x9613, 0xb510): one KNOWN_LIBRARY region per CS.LIB
module (id LIB_<MODULE>_<FILEHEX>) plus PADDING for linker alignment.
DGROUP: C0S _DATA, the _INIT_ table (SETUPIO/SETENVP entries) and every
library _DATA contribution become KNOWN_LIBRARY (classification data), with
PADDING for word/paragraph alignment. Everything is carved out of
RAW_UNKNOWN; existing KNOWN_LIBRARY regions in the library _TEXT area are
replaced by the new, complete tiling. Runs extract_raw + reconstruct and
restores the manifest on failure. Idempotent.

Usage: python tools/apply_library_map.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import reconstruct  # noqa: E402

MANIFEST = ROOT / "layout" / "manifest.json"
LIBMAP = json.loads((ROOT / "docs" / "library-map.json").read_text())
LIB_TEXT = (0x9613, 0xB510)


def new_regions():
    out = []
    for m in LIBMAP["modules"]:
        out.append({"id": f"LIB_{m['module']}_{m['start']:X}", "start": m["start"], "end": m["end"],
                    "kind": "KNOWN_LIBRARY", "classification": "code",
                    "library_module": f"CS.LIB:{m['module']}",
                    "description": f"CS.LIB module {m['module']} _TEXT (library index {m['library_index']})",
                    "matching_status": "EXACT_FIXUPS_VERIFIED",
                    "matching_status_note": "tools/library_scanner2.py: non-fixup bytes equal; fixups "
                                            "recomputed from the layout (docs/library-map.json)"})
        d = m.get("data")
        if d and d.get("size"):
            out.append({"id": f"LIBDATA_{m['module']}_{d['start']:X}", "start": d["start"], "end": d["end"],
                        "kind": "KNOWN_LIBRARY", "classification": "data",
                        "library_module": f"CS.LIB:{m['module']}",
                        "description": f"CS.LIB module {m['module']} _DATA contribution"})
    for m in LIBMAP["data_only_modules"]:
        d = m["data"]
        out.append({"id": f"LIBDATA_{m['module']}_{d['start']:X}", "start": d["start"], "end": d["end"],
                    "kind": "KNOWN_LIBRARY", "classification": "data",
                    "library_module": f"CS.LIB:{m['module']}",
                    "description": f"CS.LIB data-only module {m['module']} _DATA"})
    for p in LIBMAP["padding"]:
        out.append({"id": f"PAD_{p['start']:X}", "start": p["start"], "end": p["end"], "kind": "PADDING",
                    "classification": "padding", "description": f"{p['where']}: {p['reason']}"})
    c0s = LIBMAP["c0s_segments_accounted"]["_DATA"]
    out.append({"id": "C0S_DATA", "start": c0s[0], "end": c0s[1], "kind": "KNOWN_LIBRARY",
                "library_module": "C0S.OBJ",
                "classification": "data", "description": "C0S.OBJ _DATA (DS 0x0000-0x00A8)"})
    out.append({"id": "INIT_TABLE", "start": 0x256C0, "end": 0x256CC, "kind": "KNOWN_LIBRARY",
                "library_module": "CS.LIB:SETUPIO+SETENVP",
                "classification": "data",
                "description": "_INIT_ segment (paragraph 0x254C): SETUPIO and SETENVP startup entries"})
    # de-duplicate (a module's data may also be listed elsewhere)
    seen, uniq = set(), []
    for r in sorted(out, key=lambda r: r["start"]):
        if (r["start"], r["end"]) not in seen:
            seen.add((r["start"], r["end"]))
            uniq.append(r)
    return uniq


def main():
    backup = MANIFEST.read_text()
    manifest = json.loads(backup)
    regions = sorted(manifest["regions"], key=lambda r: r["start"])
    # 1. dissolve the library _TEXT area into RAW
    lo, hi = LIB_TEXT
    kept, area = [], []
    for r in regions:
        if r["end"] <= lo or r["start"] >= hi:
            kept.append(r)
        elif r["kind"] in ("RAW_UNKNOWN", "KNOWN_LIBRARY", "PADDING") and r["start"] >= lo and r["end"] <= hi:
            area.append(r)
        elif r["kind"] == "RAW_UNKNOWN":
            # straddles: split
            if r["start"] < lo:
                kept.append({**r, "end": lo})
            if r["end"] > hi:
                kept.append({**r, "start": hi})
        else:
            raise SystemExit(f"unexpected region {r['id']} in library area")
    kept.append({"id": "tmp", "start": lo, "end": hi, "kind": "RAW_UNKNOWN", "classification": "unknown"})
    regions = sorted(kept, key=lambda r: r["start"])
    # 2. carve every new region out of RAW
    for n in new_regions():
        idx = next((i for i, r in enumerate(regions)
                    if r["kind"] == "RAW_UNKNOWN" and r["start"] <= n["start"] and n["end"] <= r["end"]), None)
        if idx is None:
            same = [i for i, r in enumerate(regions) if (r["start"], r["end"]) == (n["start"], n["end"])
                    and r["kind"] == n["kind"]]
            if same:
                regions[same[0]] = {**n, "artifact": f"raw/{n['id']}.bin"}   # refresh fields
                continue
            raise SystemExit(f"{n['id']} [{n['start']:#x},{n['end']:#x}) is not inside RAW_UNKNOWN")
        old = regions[idx]
        rep = []
        if old["start"] < n["start"]:
            rep.append({**old, "end": n["start"]})
        rep.append({**n, "artifact": f"raw/{n['id']}.bin"})
        if n["end"] < old["end"]:
            rep.append({**old, "start": n["end"]})
        regions[idx:idx + 1] = rep
    for r in regions:
        if r["kind"] == "RAW_UNKNOWN":
            r["id"] = f"RAW_{r['start']:X}_{r['end']:X}"
            r["artifact"] = f"raw/{r['id']}.bin"
    manifest["regions"] = regions
    reconstruct.validate_ownership(manifest)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        for tool in ("extract_raw.py", "reconstruct.py"):
            p = subprocess.run([sys.executable, str(ROOT / "tools" / tool)], cwd=ROOT,
                               capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError(f"{tool}: {p.stdout[-1500:]} {p.stderr[-1500:]}")
    except Exception:
        MANIFEST.write_text(backup)
        raise
    print(f"applied: {len(regions)} regions")


if __name__ == "__main__":
    main()
