"""Compile and strictly verify every recovered game source; feed the rebuild.

For each src/game/*.c: batch-compile (tools/tcc.py), place and link it with
every fixup resolved (tools/match_function.py match_object), and require
EXACT. The linked bytes are written to build/matched/<stem>.bin, which is
what tools/reconstruct.py uses for MATCHING_C regions -- the rebuilt image's
matched code therefore really comes from the compiler, not from raw extracts.

--sync rewrites layout/manifest.json's code-area ownership from the verdicts:
every MATCHING_C region is re-derived (id = source stem, extent = linked
extent), the bytes between them stay RAW_UNKNOWN, adjacent RAW_UNKNOWN
regions are coalesced. Extents must coincide with census function
boundaries. Then extract_raw.py + reconstruct.py run; any failure restores
the previous manifest.

src/asm/*.asm (hand-written assembly) take a separate, verification-only
path: see verify_asm() below; their report goes to <json stem>_asm.json.

Usage: python tools/verify_sources.py [--sync] [--json build/verify.json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import match_function as mf  # noqa: E402
import reconstruct  # noqa: E402
import tcc  # noqa: E402

SRC = ROOT / "src" / "game"
OUT = ROOT / "build" / "matched"


def verify_all():
    sources = sorted(SRC.glob("*.c"))
    objs = tcc.compile_many(sources, work=ROOT / "build" / "verify_batch")
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for i, (src, obj) in enumerate(zip(sources, objs)):
        if obj is None:
            log = (ROOT / "build" / "verify_batch" / f"S{i + 1:04d}.LOG")
            results.append({"source": str(src.relative_to(ROOT)).replace("\\", "/"),
                            "verdict": "COMPILE_FAILED",
                            "log": log.read_text(errors="replace") if log.exists() else ""})
            continue
        r = mf.match_object(obj.read_bytes(), src)
        r["source"] = str(src.relative_to(ROOT)).replace("\\", "/")
        if r["verdict"] == "EXACT":
            image = mf._IMAGE
            (OUT / f"{src.stem}.bin").write_bytes(image[r["file_start"]:r["file_end"]])
        results.append(r)
    return results


def sync_manifest(results):
    bounds = mf.census_boundaries()
    manifest = mf.load_manifest()
    backup = mf.MANIFEST_PATH.read_text()
    # 1. dissolve existing MATCHING_C regions back into RAW_UNKNOWN
    regions = []
    for r in sorted(manifest["regions"], key=lambda r: r["start"]):
        if r["kind"] == "MATCHING_C":
            r = {"id": "tmp", "start": r["start"], "end": r["end"], "kind": "RAW_UNKNOWN",
                 "classification": "unknown"}
        if regions and regions[-1]["kind"] == "RAW_UNKNOWN" and r["kind"] == "RAW_UNKNOWN" \
                and regions[-1]["end"] == r["start"]:
            regions[-1]["end"] = r["end"]
        else:
            regions.append(dict(r))
    # 2. carve each EXACT source out of RAW_UNKNOWN
    for res in sorted((r for r in results if r["verdict"] == "EXACT"), key=lambda r: r["file_start"]):
        if res["cs_start"] not in bounds or res["cs_end"] not in bounds:
            raise SystemExit(f"{res['source']}: extent [{res['cs_start']:#x},{res['cs_end']:#x}) "
                             "is not on census function boundaries")
        a, b = res["file_start"], res["file_end"]
        idx = next((i for i, r in enumerate(regions)
                    if r["kind"] == "RAW_UNKNOWN" and r["start"] <= a and b <= r["end"]), None)
        if idx is None:
            raise SystemExit(f"{res['source']}: [{a:#x},{b:#x}) is not inside one RAW_UNKNOWN region")
        old = regions[idx]
        stem = pathlib.Path(res["source"]).stem
        new = []
        if old["start"] < a:
            new.append({**old, "end": a})
        new.append({
            "id": stem, "start": a, "end": b, "kind": "MATCHING_C", "classification": "code",
            "source": res["source"], "compile_flags": {"model": res["model"], "flags": res["flags"]},
            "object_sha256": res["object_sha256"], "matching_status": "EXACT",
            "matching_status_note": "tools/verify_sources.py: strict link, every fixup resolved, "
                                    f"{res['fixup_count']} fixups, 0 differing bytes",
            "artifact": f"build/matched/{stem}.bin",
        })
        if b < old["end"]:
            new.append({**old, "start": b})
        regions[idx:idx + 1] = new
    for r in regions:
        if r["kind"] == "RAW_UNKNOWN":
            r["id"] = f"RAW_{r['start']:X}_{r['end']:X}"
            r["artifact"] = f"raw/{r['id']}.bin"
    manifest["regions"] = regions
    reconstruct.validate_ownership(manifest)
    mf.MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        for tool in ("extract_raw.py", "reconstruct.py"):
            p = subprocess.run([sys.executable, str(ROOT / "tools" / tool)], cwd=ROOT,
                               capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError(f"{tool} failed:\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
    except Exception:
        mf.MANIFEST_PATH.write_text(backup)
        raise


# ---------------------------------------------------------------------------
# Hand-written assembly: src/asm/*.asm (separate path, verification only).
#
# Each module is assembled with the pinned assembler (layout/assembler.json,
# tools/asm.py) and strictly matched by tools/match_asm.py (match_function's
# link(), full SEGDEF extent, frame checks, _DATA compared with DGROUP). The
# assembler's linked bytes go to build/matched/<stem>.bin, ready for
# MATCHING_ASM regions. These results never feed --sync (the C carving
# below); MATCHING_ASM manifest regions are applied separately.

ASM_SRC = ROOT / "src" / "asm"


def verify_asm():
    import match_asm  # noqa: E402  (pulls in tools/asm.py only when needed)
    sources = sorted(ASM_SRC.glob("*.asm"))
    if not sources:
        return []
    results = match_asm.assemble_and_match(sources, work=ROOT / "build" / "verify_asm_batch")
    OUT.mkdir(parents=True, exist_ok=True)
    for src, r in zip(sources, results):
        r["source"] = str(src.relative_to(ROOT)).replace("\\", "/")
        linked = r.pop("linked", None)
        if r["verdict"] == "EXACT":
            (OUT / f"{src.stem}.bin").write_bytes(linked)
    return results


def report_asm(results) -> int:
    bad = 0
    for r in results:
        if r["verdict"] == "EXACT":
            data = ", ".join(f"{c['segment']} ds [{c['ds']:#06x},{c['ds'] + c['length']:#06x})"
                             for c in r["data_checks"])
            print(f"EXACT     {r['source']}  cs [{r['cs_start']:#06x},{r['cs_end']:#06x}) "
                  f"{r['length']} bytes, {r['fixup_count']} fixups"
                  + (f"; {data}" if data else "") + f" ({r['assembler']} {r['options']})")
        else:
            bad += 1
            print(f"{r['verdict']:9s} {r['source']}  {r.get('diff_count', '')}")
    if results:
        print(f"{len(results) - bad}/{len(results)} assembly modules EXACT, "
              f"{sum(r['length'] for r in results if r['verdict'] == 'EXACT')} bytes")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--json", default=None)
    ap.add_argument("--json-asm", default=None,
                    help="report for src/asm/*.asm (default: <--json stem>_asm.json)")
    args = ap.parse_args()
    asm_results = verify_asm()
    asm_bad = report_asm(asm_results)
    asm_json = args.json_asm or (str(pathlib.Path(args.json).with_name(
        pathlib.Path(args.json).stem + "_asm.json")) if args.json else None)
    if asm_json:
        pathlib.Path(asm_json).write_text(json.dumps(
            [{k: v for k, v in r.items() if k != "fixups"} for r in asm_results], indent=1))
    results = verify_all()
    bad = 0
    for r in results:
        if r["verdict"] == "EXACT":
            print(f"EXACT     {r['source']}  cs [{r['cs_start']:#06x},{r['cs_end']:#06x}) "
                  f"{r['length']} bytes, {r['fixup_count']} fixups")
        else:
            bad += 1
            extra = r.get("diff_count", "")
            print(f"{r['verdict']:9s} {r['source']}  {extra}")
    print(f"{len(results) - bad}/{len(results)} sources EXACT, "
          f"{sum(r['length'] for r in results if r['verdict'] == 'EXACT')} bytes")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            [{k: v for k, v in r.items() if k != "fixups"} for r in results], indent=1))
    if args.sync:
        if bad:
            raise SystemExit("refusing to sync: not every source is EXACT")
        sync_manifest(results)
        print("manifest synced; reconstruction exact")
    sys.exit(1 if bad or asm_bad else 0)


if __name__ == "__main__":
    main()
