"""Structured-data generators for STRUCTURED_DATA manifest regions.

A STRUCTURED_DATA region names a generator; tools/reconstruct.py obtains the
region's bytes by ENCODING the structured representation (never a raw copy).
Game data is not committed, so each representation is materialised under
build/ by decoding the original files once (`materialise`), and the encoder
is the component under test.

Generators:
  levels   g_levels, DS:0x173A, 10 x 0x500 records (tools/levels.py):
           build/levels/levelNN.json -> bytes

Usage:
    python tools/structured.py promote levels   # carve the region into the manifest
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
EXE = ROOT / "build" / "DAVE_unpacked.exe"


def _levels_extent():
    import levels
    _, base, _ = levels.find_levels_base(EXE.read_bytes())
    return base, base + levels.NUM_LEVELS * levels.RECORD_SIZE


def _levels_generate() -> bytes:
    import levels
    d = ROOT / "build" / "levels"
    if not (d / "level10.json").exists():
        levels.main(["decode", "--out", str(d)])
    recs = [json.loads((d / f"level{i:02d}.json").read_text())
            for i in range(1, levels.NUM_LEVELS + 1)]
    return levels.encode_levels(recs)


GENERATORS = {
    "levels": {"extent": _levels_extent, "generate": _levels_generate,
               "description": "g_levels: 10 level records (256-byte monster path, 100x10 tile map, "
                              "24 unread bytes), DS:0x173A; codec tools/levels.py"},
}


def generate(name: str) -> bytes:
    return GENERATORS[name]["generate"]()


def promote(name: str):
    import reconstruct
    g = GENERATORS[name]
    a, b = g["extent"]()
    manifest_path = ROOT / "layout" / "manifest.json"
    backup = manifest_path.read_text()
    manifest = json.loads(backup)
    regions = sorted(manifest["regions"], key=lambda r: r["start"])
    if any(r["kind"] == "STRUCTURED_DATA" and r.get("generator") == name for r in regions):
        print("already promoted")
        return
    idx = next(i for i, r in enumerate(regions)
               if r["kind"] == "RAW_UNKNOWN" and r["start"] <= a and b <= r["end"])
    old = regions[idx]
    rep = []
    if old["start"] < a:
        rep.append({**old, "end": a, "id": f"RAW_{old['start']:X}_{a:X}", "artifact": f"raw/RAW_{old['start']:X}_{a:X}.bin"})
    rep.append({"id": f"DATA_{name.upper()}", "start": a, "end": b, "kind": "STRUCTURED_DATA",
                "classification": "data", "generator": name, "description": g["description"],
                "matching_status": "EXACT_ROUNDTRIP"})
    if b < old["end"]:
        rep.append({**old, "start": b, "id": f"RAW_{b:X}_{old['end']:X}", "artifact": f"raw/RAW_{b:X}_{old['end']:X}.bin"})
    regions[idx:idx + 1] = rep
    manifest["regions"] = regions
    reconstruct.validate_ownership(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        for tool in ("extract_raw.py", "reconstruct.py"):
            p = subprocess.run([sys.executable, str(ROOT / "tools" / tool)], cwd=ROOT,
                               capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError(f"{tool}: {p.stdout[-1500:]} {p.stderr[-1500:]}")
    except Exception:
        manifest_path.write_text(backup)
        raise
    print(f"promoted {name}: [{a:#x},{b:#x})")


if __name__ == "__main__":
    if sys.argv[1:2] == ["promote"]:
        promote(sys.argv[2])
