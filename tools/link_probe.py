"""Link probe: let TLINK 3.0 lay out the whole program and compare with the original.

Objects, in link order (after C0S):
  src/DAVE.C, src/CONFIG.C, src/HARDWARE.C   compiled with the pinned TCC (tools/tcc.py)
  src/asm/lowlevel.asm, src/asm/tiles.asm    assembled with the pinned TASM (tools/asm.py),
                                             from build copies whose `_D_XXXX` externs are
                                             renamed to the C units' symbols (see below)
  DAVEDATA.OBJ   stand-in (tools/omf_writer.py) for the data-only module after the
                 assembly: _DATA = the original DS [0x143A,0x493A), publics
                 _g_vga_palette (+0) and _g_levels (+0x300)
  FARDATA.OBJ    stand-in for the seven far data blobs: one FAR_DATA segment each
                 (paragraph aligned, as TCC emits far data), the original bytes up to
                 each blob's data end, public _g_demo_bank ... at +0
then CS.LIB. Nothing is placed by hand: TLINK decides every address.

The assembly modules still name C-owned variables by placeholder (`_D_8604`
...). The probe rewrites them in a build copy to the symbol that the C
objects actually export at that address (`_g_pic_table`, or `_g_tileset+2`
for the segment word of a far pointer); the list is printed and written to
the report so the assembly sources can adopt the names.

Then the linked EXE is compared with build/DAVE_unpacked.exe: MZ header
fields, the relocation set, and the load module byte for byte (differences
are attributed to manifest regions).

    python tools/link_probe.py [--json build/link_probe/report.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import asm  # noqa: E402
import match_function as mf  # noqa: E402
import omf  # noqa: E402
import tcc  # noqa: E402
import tlink  # noqa: E402
from omf_writer import OmfWriter  # noqa: E402

WORK = ROOT / "build" / "link_probe"
DGROUP_FILE = mf.DGROUP_FILE
DATA_MODULE = (0x143A, 0x493A)        # palette + g_levels (docs/data-layout.md)
FAR_NAMES = {0x0B31: "_g_demo_bank", 0x0C42: "_g_tileset_cga", 0x11EF: "_g_tileset_vga",
             0x1C2E: "_g_sound_bank", 0x1D58: "_g_picfile_cga", 0x1E84: "_g_picfile_ega",
             0x20CC: "_g_picfile_vga"}


def mz(image: bytes) -> dict:
    h = struct.unpack_from("<14H", image, 0)
    size = (h[2] - 1) * 512 + (h[1] or 512) if h[1] else h[2] * 512
    relocs = sorted(struct.unpack_from("<H", image, h[12] + 4 * i)[0]
                    + 16 * struct.unpack_from("<H", image, h[12] + 4 * i + 2)[0] for i in range(h[3]))
    return {"header_paragraphs": h[4], "load_size": size - h[4] * 16, "minalloc": h[5],
            "maxalloc": h[6], "ss": h[7], "sp": h[8], "ip": h[10], "cs": h[11],
            "relocations": relocs, "load_module": image[h[4] * 16:size]}


def compile_units(work: pathlib.Path) -> list:
    srcs = sorted(p for p in (ROOT / "src").glob("*.[cC]") if p.suffix in (".C", ".c"))
    order = {"DAVE": 0, "CONFIG": 1, "HARDWARE": 2}
    srcs.sort(key=lambda p: order.get(p.stem.upper(), 99))
    objs = tcc.compile_many(srcs, work=work / "tcc")
    out = []
    for s, o in zip(srcs, objs):
        if o is None:
            raise SystemExit(f"{s} failed to compile")
        dst = work / f"{s.stem.upper()}.OBJ"
        shutil.copyfile(o, dst)
        out.append((s, dst))
    return out


def unit_data_symbols(units) -> list:
    """[(ds, name)] of every data public of the placed units, sorted."""
    syms = []
    for src, obj in units:
        text = src.read_text(encoding="latin1")
        mod = omf.OmfReader().read(obj.read_bytes(), src.stem)
        for name, kind, addr in mf.object_symbols(mod, mf.parse_at(text), mf.parse_directives(text)):
            if kind == "data":
                syms.append((addr, name))
    syms += [(DATA_MODULE[0], "_g_vga_palette"), (DATA_MODULE[0] + 0x300, "_g_levels")]
    return sorted(syms)


def renamed_asm(work: pathlib.Path, data_syms) -> tuple[list, dict]:
    """Copies of src/asm/*.asm with `_D_XXXX` externs bound to C symbols."""
    adir = work / "asm_src"
    if adir.exists():
        shutil.rmtree(adir)
    adir.mkdir(parents=True)
    renames = {}
    out = []
    for src in sorted((ROOT / "src" / "asm").glob("*")):
        text = src.read_text(encoding="latin1")
        if src.suffix.lower() == ".asm":
            declared = set()

            def sym_for(ds):
                cand = [(a, n) for a, n in data_syms if a <= ds]
                a, n = cand[-1]
                return n, ds - a

            def extrn(m):
                ds = int(m.group(1), 16)
                n, off = sym_for(ds)
                renames[f"_D_{m.group(1)}"] = n + (f"+{off}" if off else "")
                if n in declared:
                    return f"; extrn {n} (already declared)"
                declared.add(n)
                return f"extrn\t{n}:{m.group(2)}"
            text = re.sub(r"extrn\s+_D_([0-9A-F]{4}):(\w+)", extrn, text)
            text = re.sub(r"\b_D_([0-9A-F]{4})\b", lambda m: renames[m.group(0)], text)
            out.append(adir / src.name)
        (adir / src.name).write_text(text, encoding="latin1")
    return out, renames


def standins(work: pathlib.Path, image: bytes) -> list:
    layout = json.loads((ROOT / "docs" / "data-layout.json").read_text())
    # data-only module
    w = OmfWriter("DAVEDATA")
    lo, hi = DATA_MODULE
    data = w.segment("_DATA", "DATA", align="word", combine="public",
                     data=image[DGROUP_FILE + lo:DGROUP_FILE + hi])
    w.group("DGROUP", [data])
    w.public(data, "_g_vga_palette", 0)
    w.public(data, "_g_levels", 0x300)
    p1 = work / "DAVEDATA.OBJ"
    p1.write_bytes(w.to_bytes())
    # far data: one segment per blob, the original bytes up to its data end
    w = OmfWriter("FARDATA")
    for seg in layout["segments"]:
        para = int(seg["paragraph"], 16)
        if para not in FAR_NAMES:
            continue
        # the blob = the segment's bytes up to its last non-zero byte (the
        # trailing zeros are the paragraph alignment TLINK adds)
        start, end = int(seg["file_start"], 16), int(seg["file_end"], 16)
        while end > start and image[end - 1] == 0:
            end -= 1
        s = w.segment(f"FARDATA{len(w.segments) + 1}_FAR", "FAR_DATA", align="para",
                      combine="public", data=image[start:end])
        w.public(s, FAR_NAMES[para], 0)
    p2 = work / "FARDATA.OBJ"
    p2.write_bytes(w.to_bytes())
    return [p1, p2]


def attribute(offsets, manifest) -> list:
    """Group differing load-module offsets into runs with their manifest region."""
    regions = sorted(manifest["regions"], key=lambda r: r["start"])
    runs = []
    for o in offsets:
        if runs and o == runs[-1][1]:
            runs[-1][1] = o + 1
        else:
            runs.append([o, o + 1])
    out = []
    for a, b in runs:
        f = a + mf.HDR
        reg = next((r["id"] for r in regions if r["start"] <= f < r["end"]), "?")
        out.append({"lm": [a, b], "file": [f, b + mf.HDR], "bytes": b - a, "region": reg})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(WORK / "report.json"))
    args = ap.parse_args()
    image = mf.unpacked_bytes()
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    units = compile_units(WORK)
    syms = unit_data_symbols(units)
    asm_srcs, renames = renamed_asm(WORK, syms)
    asm_objs = asm.assemble_many(asm_srcs, work=WORK / "tasm")
    if None in asm_objs:
        raise SystemExit("assembly failed: " + asm.log_for(WORK / "tasm", asm_objs.index(None)))
    objs = [o for _, o in units]
    for s, o in zip(asm_srcs, asm_objs):
        dst = WORK / f"{s.stem.upper()}.OBJ"
        shutil.copyfile(o, dst)
        objs.append(dst)
    objs += standins(WORK, image)
    exe, map_text, log = tlink.link(objs, work=WORK / "tlink", options="/m /c", startup="C0S",
                                    libs=["CS"], out="DAVE")
    report = {"objects": [p.name for p in objs], "asm_renames": renames, "tlink_log": log}
    if exe is None:
        print(log)
        raise SystemExit("TLINK produced no executable")
    (WORK / "DAVE.MAP").write_text(map_text)
    got, want = mz(exe.read_bytes()), mz(image)
    lm_g, lm_w = got.pop("load_module"), want.pop("load_module")
    n = min(len(lm_g), len(lm_w))
    diffs = [i for i in range(n) if lm_g[i] != lm_w[i]]
    manifest = json.loads((ROOT / "layout" / "manifest.json").read_text())
    report.update({
        "header": {k: {"linked": got[k], "original": want[k]} for k in got if k != "relocations"},
        "relocations": {"linked": len(got["relocations"]), "original": len(want["relocations"]),
                        "equal": got["relocations"] == want["relocations"],
                        "only_linked": [hex(x) for x in sorted(set(got["relocations"]) - set(want["relocations"]))],
                        "only_original": [hex(x) for x in sorted(set(want["relocations"]) - set(got["relocations"]))]},
        "load_module": {"linked_bytes": len(lm_g), "original_bytes": len(lm_w),
                        "differing_bytes": len(diffs), "identical": not diffs and len(lm_g) == len(lm_w),
                        "linked_md5": hashlib.md5(lm_g).hexdigest(), "original_md5": hashlib.md5(lm_w).hexdigest(),
                        "diff_runs": attribute(diffs, manifest)[:200]},
    })
    pathlib.Path(args.json).write_text(json.dumps(report, indent=1))
    print(f"linked {len(objs)} objects + C0S + CS.LIB with TLINK; log: {log.strip()[:300] or '(clean)'}")
    print("asm extern renames:", ", ".join(f"{k}->{v}" for k, v in renames.items()))
    for k, v in report["header"].items():
        mark = "==" if v["linked"] == v["original"] else "!="
        print(f"  header {k:17s} linked {v['linked']:#x} {mark} original {v['original']:#x}")
    r = report["relocations"]
    print(f"  relocations      linked {r['linked']} / original {r['original']}, equal: {r['equal']}")
    lmr = report["load_module"]
    print(f"  load module      {lmr['linked_bytes']} / {lmr['original_bytes']} bytes, "
          f"{lmr['differing_bytes']} differ -> {'IDENTICAL' if lmr['identical'] else 'differs'}")
    for run in lmr["diff_runs"][:20]:
        print(f"    file [{run['file'][0]:#x},{run['file'][1]:#x}) {run['bytes']} bytes in {run['region']}")


if __name__ == "__main__":
    main()
