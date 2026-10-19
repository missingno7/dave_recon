"""Structured-data generators for STRUCTURED_DATA manifest regions.

A STRUCTURED_DATA region names a generator; tools/reconstruct.py obtains the
region's bytes by ENCODING the structured representation (never a raw copy).
Game data is not committed, so each representation is materialised under
build/ by decoding the original files once (`materialise`), and the encoder
is the component under test.

Generators:
  levels       g_levels, DS:0x173A, 10 x 0x500 records (tools/levels.py):
               build/levels/levelNN.json -> bytes
  demos        far segment 0x0B31, attract-mode recordings (tools/demos.py)
  tileset_cga  far segment 0x0C42, RLE CGA tileset (tools/tilesets.py + rle.py)
  tileset_vga  far segment 0x11EF, RLE VGA tileset (tools/tilesets.py + rle.py)
  sounds       far segment 0x1C2E, SPK PC-speaker bank (tools/sounds.py)
  picfile_cga  far segment 0x1D58, config-screen font + icons (tools/picfiles.py)
  picfile_ega  far segment 0x1E84
  picfile_vga  far segment 0x20CC
The far-segment extents come from the MZ relocation table (tools/far_data.py)
and span whole segments, alignment padding included.

Usage:
    python tools/structured.py promote levels   # carve the region into the manifest
    python tools/structured.py check            # every generator == original bytes
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


def _far(name: str, generate, description: str) -> dict:
    def extent():
        import far_data
        return far_data.extent(name, EXE)
    return {"extent": extent, "generate": generate, "description": description}


def _gen(module: str, *args):
    def generate() -> bytes:
        return __import__(module).generate(*args)
    return generate


GENERATORS = {
    "palette": {"extent": lambda: __import__("palette").extent(),
                "generate": lambda: __import__("palette").generate(),
                "description": "g_vga_palette: 256 x 6-bit RGB VGA DAC palette, DS:0x143A; "
                               "codec tools/palette.py"},
    "levels": {"extent": _levels_extent, "generate": _levels_generate,
               "description": "g_levels: 10 level records (256-byte monster path, 100x10 tile map, "
                              "24 unread bytes), DS:0x173A; codec tools/levels.py"},
    "demos": _far("demos", _gen("demos"),
                  "far segment 0x0B31: 5 attract-mode demo recordings (start level + input "
                  "event stream) + zero padding; codec tools/demos.py"),
    "tileset_cga": _far("tileset_cga", _gen("tilesets", "cga"),
                        "far segment 0x0C42: CGA tileset (53 tiles + 186 sprites, 2bpp), compressed "
                        "with the game's own RLE encoder (0x7F41), + its 1 over-read byte + zero "
                        "padding; codec tools/tilesets.py, tools/rle.py"),
    "tileset_vga": _far("tileset_vga", _gen("tilesets", "vga"),
                        "far segment 0x11EF: VGA tileset (53 tiles + 105 sprites, 8bpp), compressed "
                        "with the game's own RLE encoder (0x7F41), + its 22 over-read bytes + zero "
                        "padding; codec tools/tilesets.py, tools/rle.py"),
    "sounds": _far("sounds", _gen("sounds"),
                   "far segment 0x1C2E: SPK PC-speaker bank, 63 directory entries (12 sounds), "
                   "PIT divisor lists + zero padding; codec tools/sounds.py"),
    "picfile_cga": _far("picfile_cga", _gen("picfiles", "cga"),
                        "far segment 0x1D58: CGA config-screen picfile (header, 8x8 font, 13 "
                        "32x24 icons, 2bpp); codec tools/picfiles.py"),
    "picfile_ega": _far("picfile_ega", _gen("picfiles", "ega"),
                        "far segment 0x1E84: EGA config-screen picfile (header, 8x8 font, 13 "
                        "32x24 icons, 4 planes); codec tools/picfiles.py"),
    "picfile_vga": _far("picfile_vga", _gen("picfiles", "vga"),
                        "far segment 0x20CC: VGA config-screen picfile (header, 8x8 font, 13 "
                        "32x24 icons, 8bpp); codec tools/picfiles.py"),
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


def check() -> int:
    exe = EXE.read_bytes()
    rc = 0
    for name, g in GENERATORS.items():
        a, b = g["extent"]()
        ok = generate(name) == exe[a:b]
        print(f"{name:12s} [{a:#07x},{b:#07x}) {b - a:6d} bytes  {'EXACT' if ok else 'MISMATCH'}")
        rc |= not ok
    return rc


if __name__ == "__main__":
    if sys.argv[1:2] == ["promote"]:
        promote(sys.argv[2])
    elif sys.argv[1:2] == ["check"]:
        sys.exit(check())
    else:
        sys.exit(__doc__)
