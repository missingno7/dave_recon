"""Historical build: sources + codecs -> TCC/TASM -> TLINK -> LZEXE -> DAVE.EXE.

The Level D build. Every input is source or a structured representation;
the original files are used only to COMPARE the result:

  src/DAVE.C, src/CONFIG.C, src/HARDWARE.C   Turbo C++ 1.00 (tools/tcc.py)
  src/asm/lowlevel.asm, src/asm/tiles.asm    TASM 2.0 (tools/asm.py)
  DAVEDATA.OBJ   data-only module after tiles.asm's _DATA: g_vga_palette
                 (tools/palette.py) + g_levels (tools/levels.py), emitted as
                 OMF by tools/omf_writer.py
  FARDATA.OBJ    the seven FAR_DATA blobs from their codecs (tools/demos.py,
                 tilesets.py, sounds.py, picfiles.py), paragraph aligned
  C0S.OBJ + CS.LIB, linked by TLINK 3.0; packed by LZEXE 0.91.

TLINK decides every address; nothing is placed by hand. Structured
representations are materialised under build/ from the user-supplied
original files on first use (game data is not committed).

Checks: the linked EXE's load module, relocation set and header fields
against build/DAVE_unpacked.exe; the LZEXE-packed EXE against
assets/DAVE.EXE.

    python tools/build.py            # build/final/DAVE.EXE + report
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import asm  # noqa: E402
import link_probe as lp  # noqa: E402
import repack  # noqa: E402
import structured  # noqa: E402
import tlink  # noqa: E402
from omf_writer import OmfWriter  # noqa: E402

WORK = ROOT / "build" / "final"
FAR_BLOBS = [  # link order = paragraph order in the original
    ("demos", "_g_demo_bank"), ("tileset_cga", "_g_tileset_cga"),
    ("tileset_vga", "_g_tileset_vga"), ("sounds", "_g_sound_bank"),
    ("picfile_cga", "_g_picfile_cga"), ("picfile_ega", "_g_picfile_ega"),
    ("picfile_vga", "_g_picfile_vga"),
]


def data_objects(work: pathlib.Path) -> list:
    palette = structured.generate("palette")
    levels = structured.generate("levels")
    w = OmfWriter("DAVEDATA")
    seg = w.segment("_DATA", "DATA", align="word", combine="public", data=palette + levels)
    w.group("DGROUP", [seg])
    w.public(seg, "_g_vga_palette", 0)
    w.public(seg, "_g_levels", len(palette))
    p1 = work / "DAVEDATA.OBJ"
    p1.write_bytes(w.to_bytes())
    w = OmfWriter("FARDATA")
    for n, (gen, name) in enumerate(FAR_BLOBS, 1):
        blob = structured.generate(gen)
        # each codec covers its whole segment incl. TLINK's paragraph padding;
        # the object carries the data, TLINK re-creates the padding
        blob = blob.rstrip(b"\0")
        s = w.segment(f"FARDATA{n}_FAR", "FAR_DATA", align="para", combine="public", data=blob)
        w.public(s, name, 0)
    p2 = work / "FARDATA.OBJ"
    p2.write_bytes(w.to_bytes())
    return [p1, p2]


def main() -> int:
    image = lp.mf.unpacked_bytes()
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    units = lp.compile_units(WORK)
    asm_srcs, renames = lp.renamed_asm(WORK, lp.unit_data_symbols(units))
    asm_objs = asm.assemble_many(asm_srcs, work=WORK / "tasm")
    if None in asm_objs:
        raise SystemExit("assembly failed")
    objs = [o for _, o in units]
    for s, o in zip(asm_srcs, asm_objs):
        dst = WORK / f"{s.stem.upper()}.OBJ"
        shutil.copyfile(o, dst)
        objs.append(dst)
    objs += data_objects(WORK)
    exe, map_text, log = tlink.link(objs, work=WORK / "tlink", options="/m /c", startup="C0S",
                                    libs=["CS"], out="DAVE")
    if exe is None:
        raise SystemExit("TLINK produced no executable:\n" + log)
    linked = exe.read_bytes()
    got, want = lp.mz(linked), lp.mz(image)
    lm_ok = got.pop("load_module") == want.pop("load_module")
    hdr_ok = got == want
    packed = repack.pack(linked)
    (WORK / "DAVE.EXE").write_bytes(packed)
    orig = (ROOT / "assets" / "DAVE.EXE").read_bytes()
    report = {
        "objects": [p.name for p in objs],
        "unpacked_load_module_identical": lm_ok,
        "header_fields_and_relocations_identical": hdr_ok,
        "packed_sha256": hashlib.sha256(packed).hexdigest(),
        "packed_identical_to_original_DAVE_EXE": packed == orig,
        "asm_extern_renames": renames,
    }
    (WORK / "report.json").write_text(json.dumps(report, indent=1))
    print(f"load module identical: {lm_ok}; header fields + relocations identical: {hdr_ok}")
    print(f"packed DAVE.EXE {len(packed)} bytes sha256 {report['packed_sha256'][:16]}... "
          f"{'== original DAVE.EXE' if packed == orig else 'DIFFERS from original'}")
    return 0 if (lm_ok and hdr_ok and packed == orig) else 1


if __name__ == "__main__":
    sys.exit(main())
