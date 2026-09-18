"""Identify Dangerous Dave's memory model and startup library module.

Compares the very start of the unpacked load module (file offset 512, the
entry point CS:IP=0000:0000) against each Turbo C++ 1.00 memory model's
startup object (C0S/C0C/C0M/C0L/C0H.OBJ). The correct model is the one where
every differing byte is explained by a fixup (relocation) location recorded
in the object's own OMF FIXUPP records — i.e. the code matches exactly
except where the linker necessarily had to patch in real addresses.

Usage: python tools/recover_startup_binding.py
Writes docs/startup-binding-evidence.json.
"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import omf  # noqa: E402

MODELS = [
    ("small", "C0S.OBJ"),
    ("compact", "C0C.OBJ"),
    ("medium", "C0M.OBJ"),
    ("large", "C0L.OBJ"),
    ("huge", "C0H.OBJ"),
]


def compare(load_module: bytes, obj_path: pathlib.Path):
    data = obj_path.read_bytes()
    mod = omf.OmfReader().read(data, obj_path.stem)
    seg = mod.segments["_TEXT"]
    n = len(seg)
    candidate = load_module[:n]

    diffs = {i for i in range(n) if candidate[i] != seg[i]}
    fixup_bytes = set()
    for fx in mod.fixups_in("_TEXT"):
        fixup_bytes.update(range(fx["offset"], fx["offset"] + fx["width"]))

    unexplained = sorted(diffs - fixup_bytes)
    return {
        "object": obj_path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "text_segment_length": n,
        "total_diffs": len(diffs),
        "fixup_covered_bytes": len(fixup_bytes),
        "unexplained_diffs": unexplained,
        "exact_match_modulo_fixups": len(unexplained) == 0,
    }


def main():
    load_module = (ROOT / "raw" / "RAW_LOAD_MODULE.bin").read_bytes()
    results = {}
    for model, fname in MODELS:
        results[model] = compare(load_module, ROOT / "toolchain" / "LIB" / fname)

    winners = [m for m, r in results.items() if r["exact_match_modulo_fixups"]]

    report = {
        "hypothesis": "Dangerous Dave's C0 startup module is unmodified Turbo C++ 1.00 runtime "
                      "library code; the correct memory model is the one whose startup object "
                      "matches the load module's first bytes exactly except at fixup locations.",
        "results": results,
        "conclusion": winners[0] if len(winners) == 1 else winners,
    }
    print(json.dumps(report, indent=2))
    (ROOT / "docs" / "startup-binding-evidence.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
