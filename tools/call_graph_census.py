"""Call-graph-rooted function census for the unpacked DAVE.EXE image.

This supersedes the naive prologue scan (`tools/function_census.py`, whose
output is preserved unmodified as a cross-reference baseline at
`docs/function-census-prologue-scan.json`) as the *authoritative*
`docs/function-census.json` producer, per the `docs/blockers.json` frontier
"Function census rooted at _main @ 0x439".

Methodology (see docs/function-census.md for the full writeup):

1. Start a worklist at the trusted root `_main @ file offset 0x439`
   (`docs/matching-phase.md` / `docs/blockers.json` CLOSED item).
2. For each worklist entry, linearly disassemble forward (Capstone,
   CS_MODE_16, addresses given relative to the load-module base per
   `tools/coordinates.py`, exactly as `tools/function_census.py` already
   does -- this is the fix for the historical file-offset/load-module-offset
   double-counting bug) until a RET/RETF or an *indirect* JMP (a likely
   switch-dispatch jump table, where linear sweep would otherwise start
   disassembling table data as if it were code) is reached, or a generous
   hard byte cap is hit with neither (flagged as truncated).
3. Every resolved near CALL rel16 target found along the way is:
     - independently re-derived from the raw opcode bytes via
       `tools/coordinates.py`'s `resolve_self_relative_call`, asserted equal
       to Capstone's own resolved target as a standing regression guard
       against the historical coordinate bug, then
     - enqueued as a new worklist entry if it falls inside
       `[MAIN_START, RAW_LOAD_MODULE_END)` and hasn't been visited, or
     - recorded (not walked further) as a call into the already-identified
       `STARTUP_C0S` library region if it falls below `MAIN_START`.
4. Indirect calls/jumps (register or memory operand, e.g. jump tables or
   function-pointer calls) and far calls (absolute segment:offset immediates,
   which our flat file/load-module coordinate system cannot resolve without
   real segment bases) are recorded honestly as unresolved indirect control
   flow -- never silently ignored or guessed.
5. Once the worklist is exhausted, a second "finalize" pass recomputes every
   function's extent capped at the *next* known function start (mirroring
   `tools/function_census.py`'s own capping strategy) instead of the
   generous per-node exploration cap, to produce clean, non-overlapping
   extents comparable to the prologue-scan baseline. Any case where the
   finalize pass's tighter cap cuts a function off before its own RET/
   indirect-jmp (which would mean the free-running walk actually overlapped
   into the next function) is flagged as an anomaly rather than silently
   resolved either way.
6. The result is cross-referenced against the prologue-scan baseline
   (`docs/function-census-prologue-scan.json`): call-graph starts lacking
   the `55 8B EC` prologue are flagged for manual attention (frameless leaf
   vs. misalignment), and baseline starts never reached by the call graph
   are reported as "not reached" (likely only reachable via an unresolved
   indirect call/jump, i.e. a function-pointer table).

Usage:
    "/c/Users/Jiri/AppData/Local/Programs/Python/Python312/python.exe" \
        tools/call_graph_census.py

Writes docs/function-census.json (authoritative) and prints a summary.
Does not touch docs/function-census-prologue-scan.json (regenerate that with
tools/function_census.py if it's ever missing/stale).
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import deque

from capstone import Cs, CS_ARCH_X86, CS_MODE_16

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import coordinates as coord  # noqa: E402

EXE = ROOT / "build" / "DAVE_unpacked.exe"
PROLOGUE_BASELINE_PATH = ROOT / "docs" / "function-census-prologue-scan.json"
OUT_JSON = ROOT / "docs" / "function-census.json"

SEGMENT_BASE = coord.MZ_HEADER_SIZE            # file offset of CS:IP 0000:0000
MAIN_START = 0x439                             # trusted call-graph root (file offset)
RAW_LOAD_MODULE_END = 172848                   # file offset, EOF of build/DAVE_unpacked.exe
PROLOGUE = b"\x55\x8b\xec"                     # push bp; mov bp, sp

assert MAIN_START == 0x439, "MAIN_START must match the _main anchor recorded in docs/blockers.json"

# Safety valve only, for the exploratory (pre-finalize) disassembly pass, to
# stop runaway disassembly if a function body never reaches a RET/indirect
# JMP. The largest function in the prologue-scan baseline is 3771 bytes; this
# is more than double that with margin. Any function that actually needs this
# cap is flagged as truncated/suspicious, never silently trusted.
HARD_BODY_CAP = 8192

# A handful of call-graph-reached, non-prologue ("frameless") addresses that
# docs/blockers.json / docs/function-census-prologue-scan.md already
# spot-checked by hand against Turbo C++ 1.00 runtime library idioms. Kept as
# a small, explicit, provenance-noted hint table -- not a substitute for the
# real "scan Turbo C++ libraries" frontier, which remains a separate,
# not-yet-done productive frontier.
KNOWN_FRAMELESS_HINTS = {
    0xA460: "9 bytes, IN AX,DX -- matches Turbo C++ 1.00 inport() pattern (spot-checked, not OMF-bound)",
    0xA469: "11 bytes, IN AL,DX + XOR AH,AH -- matches Turbo C++ 1.00 inportb() pattern (spot-checked, not OMF-bound)",
    0x850A: "12 bytes, wraps INT 21h AH=9 -- consistent with a DOS 'print string' runtime helper (spot-checked, not OMF-bound)",
}


def make_disassembler() -> Cs:
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    md.detail = False
    return md


def disassemble_body(data: bytes, md: Cs, start: int, cap: int) -> dict:
    """Linearly disassemble one function body starting at file offset
    `start`, stopping at the first RET/RETF or indirect JMP (likely a switch
    dispatch table, where continuing would misread table data as code),
    capped at file offset `cap`.

    Returns a dict with: end, stop_reason ("ret" / "indirect_jmp" /
    "cap_reached_no_terminator"), has_sub_sp, near_calls (list of
    {target_file_offset, site_file_offset}), indirect (list of
    {kind, site_file_offset, op_str, bytes}), insn_count.
    """
    seg_start = start - SEGMENT_BASE
    # Iterate the disassembly generator directly (not list(...)) and stop as
    # soon as a terminator is found: `cap` can be very far away (the next
    # *known* function start, which may be a large gap of intervening data),
    # and materializing the whole range up front would both waste time and
    # -- if used naively for an instruction count -- silently misreport how
    # many instructions actually belong to this function's own body.
    has_sub_sp = False
    near_calls = []
    indirect = []
    end = None
    stop_reason = None
    last_insn = None
    insn_count = 0
    for i, insn in enumerate(md.disasm(data[start:cap], seg_start)):
        last_insn = insn
        insn_count = i + 1
        addr_file = insn.address + SEGMENT_BASE
        mnem = insn.mnemonic
        if i <= 3 and mnem == "sub" and insn.op_str.startswith("sp,"):
            has_sub_sp = True
        if mnem == "call":
            raw = insn.bytes
            if len(raw) == 3 and raw[0] == 0xE8:
                # Near CALL rel16. Resolve two independent ways and assert
                # agreement (regression guard for the file/load-module
                # coordinate bug documented in tools/coordinates.py).
                disp16 = raw[1] | (raw[2] << 8)
                target_capstone_load = int(insn.op_str, 16) & 0xFFFF
                target_via_capstone = coord.load_module_to_file_offset(target_capstone_load)
                target_via_coord = coord.resolve_self_relative_call(addr_file, disp16).value
                assert target_via_coord == target_via_capstone, (
                    f"coordinate mismatch at call site {addr_file:#x}: "
                    f"capstone-derived={target_via_capstone:#x} "
                    f"coordinates.py-derived={target_via_coord:#x}"
                )
                near_calls.append({
                    "target_file_offset": target_via_capstone,
                    "site_file_offset": addr_file,
                })
            elif ":" in insn.op_str:
                # Far direct call (immediate seg:off). Not resolvable in our
                # flat file/load-module coordinate system without a real
                # linked segment base -- record honestly, do not guess.
                indirect.append({
                    "kind": "far_call",
                    "site_file_offset": addr_file,
                    "op_str": insn.op_str,
                    "bytes": raw.hex(),
                })
            else:
                indirect.append({
                    "kind": "indirect_call",
                    "site_file_offset": addr_file,
                    "op_str": insn.op_str,
                    "bytes": raw.hex(),
                })
        if mnem == "jmp" and insn.op_str.startswith("0x") and ":" not in insn.op_str:
            # Direct unconditional near JMP. Turbo C emits plenty of these
            # as *internal* forward control flow (e.g. _main's own
            # early-return-style "jmp" chains to a shared local epilogue,
            # still comfortably inside the function's own body) -- those
            # must NOT end the sweep. But a JMP whose target lands *before*
            # this function's own start is a tail-jump clean out of it (the
            # Turbo C++ "stack overflow" handler at file offset 0xB4FF is a
            # confirmed real example: it prints a message via INT 21h then
            # `jmp`s ~45KB backward into the C startup exit sequence).
            # Continuing linear disassembly past such a jump reads whatever
            # follows -- here, the handler's own error message string -- as
            # if it were more code, producing garbage. So: only a *backward*
            # jump that leaves the function is treated as a terminator.
            target_load = int(insn.op_str, 16) & 0xFFFF
            target_file = coord.load_module_to_file_offset(target_load)
            if target_file < start:
                end = addr_file + insn.size
                stop_reason = "jmp_out_of_function"
                indirect.append({
                    "kind": "tail_jmp_out_of_function",
                    "site_file_offset": addr_file,
                    "op_str": insn.op_str,
                    "bytes": insn.bytes.hex(),
                    "target_file_offset": target_file,
                })
                break
        if mnem == "jmp" and not insn.op_str.startswith("0x"):
            # Indirect JMP via register/memory operand: the classic
            # Turbo C switch-dispatch idiom (jmp word ptr cs:[bx+table]).
            # What follows in the byte stream is very likely the jump
            # table's raw word data, not more code, so we stop here rather
            # than let linear disassembly misread the table as instructions.
            indirect.append({
                "kind": "indirect_jmp",
                "site_file_offset": addr_file,
                "op_str": insn.op_str,
                "bytes": insn.bytes.hex(),
            })
            end = addr_file + insn.size
            stop_reason = "indirect_jmp"
            break
        if mnem in ("ret", "retf"):
            end = addr_file + insn.size
            stop_reason = "ret"
            break
    else:
        if last_insn is not None:
            end = last_insn.address + last_insn.size + SEGMENT_BASE
        else:
            end = start
        stop_reason = "cap_reached_no_terminator"

    return {
        "end": end,
        "stop_reason": stop_reason,
        "has_sub_sp": has_sub_sp,
        "near_calls": near_calls,
        "indirect": indirect,
        "insn_count": insn_count,
    }


def rough_bfs(data: bytes, md: Cs):
    """Phase A: discover the full set of call-graph-reachable function
    starts (and calls into the known STARTUP_C0S library region below
    MAIN_START), using a generous per-node cap so extents don't matter yet
    -- only reachability does.
    """
    functions = {}                 # start -> disassemble_body() result
    calls_into_library = []        # calls landing below MAIN_START
    out_of_range_targets = []      # calls landing >= RAW_LOAD_MODULE_END (should never happen)
    queued = {MAIN_START}
    worklist = deque([MAIN_START])
    discovery_order = []

    while worklist:
        start = worklist.popleft()
        discovery_order.append(start)
        cap = min(start + HARD_BODY_CAP, RAW_LOAD_MODULE_END)
        info = disassemble_body(data, md, start, cap)
        functions[start] = info
        for c in info["near_calls"]:
            tgt = c["target_file_offset"]
            if tgt < MAIN_START:
                calls_into_library.append({
                    "caller_start": start,
                    "target_file_offset": tgt,
                    "site_file_offset": c["site_file_offset"],
                })
            elif tgt >= RAW_LOAD_MODULE_END:
                out_of_range_targets.append({
                    "caller_start": start,
                    "target_file_offset": tgt,
                    "site_file_offset": c["site_file_offset"],
                })
            elif tgt not in queued:
                queued.add(tgt)
                worklist.append(tgt)

    return functions, calls_into_library, out_of_range_targets, discovery_order


def finalize(data: bytes, md: Cs, rough_functions: dict):
    """Phase B: recompute each discovered function's extent capped at the
    next known function start (or EOF for the last one), for clean,
    non-overlapping extents comparable to the prologue-scan baseline's own
    convention. Detects (rather than silently resolving) any case where this
    tighter cap cuts a function off before its own RET/indirect-jmp, which
    would mean phase A's free-running walk actually ran into the next
    function's bytes.
    """
    starts_sorted = sorted(rough_functions.keys())
    finalized = {}
    overlap_anomalies = []
    for idx, start in enumerate(starts_sorted):
        next_start = starts_sorted[idx + 1] if idx + 1 < len(starts_sorted) else RAW_LOAD_MODULE_END
        cap = min(next_start, RAW_LOAD_MODULE_END)
        info = disassemble_body(data, md, start, cap)
        rough_end = rough_functions[start]["end"]
        if info["stop_reason"] == "cap_reached_no_terminator" and rough_end > cap:
            # The free-running (phase A) walk found its RET/indirect-jmp
            # only past the next function's start -- a genuine overlap
            # anomaly. Keep phase A's calls (more complete) but flag loudly
            # and downgrade confidence; do not guess which is "right".
            overlap_anomalies.append({
                "start": start,
                "capped_end": cap,
                "rough_end": rough_end,
                "note": (
                    f"finalize-pass cap at next function start {cap:#x} was reached "
                    f"before a RET/indirect-jmp; the uncapped phase-A walk continued "
                    f"to {rough_end:#x}. Possible overlap with the next function or a "
                    f"missed early RET -- needs manual review."
                ),
            })
            info = dict(info)
            info["near_calls"] = rough_functions[start]["near_calls"]
            info["indirect"] = rough_functions[start]["indirect"]
            info["overlap_anomaly"] = True
        else:
            info["overlap_anomaly"] = False
        finalized[start] = info
    return finalized, overlap_anomalies


def load_prologue_baseline():
    if not PROLOGUE_BASELINE_PATH.exists():
        return None
    return json.loads(PROLOGUE_BASELINE_PATH.read_text())


def classify(start: int, info: dict, data: bytes, prologue_starts: set) -> tuple[str, str, str]:
    """Return (likely_type, confidence, confidence_reason)."""
    has_prologue = data[start:start + 3] == PROLOGUE
    anomaly = info.get("overlap_anomaly", False)
    stop_reason = info["stop_reason"]

    if start in KNOWN_FRAMELESS_HINTS:
        return ("library_routine", "medium", KNOWN_FRAMELESS_HINTS[start])

    clean_terminators = ("ret", "jmp_out_of_function")

    if has_prologue:
        if anomaly:
            return ("c_function", "low",
                    "standard 55 8B EC prologue, but finalize-pass detected an "
                    "extent overlap with the next function -- boundary not trustworthy yet")
        if stop_reason == "ret":
            return ("c_function", "high",
                    "standard Turbo C++ small-model 55 8B EC prologue, clean RET-terminated body, "
                    "reached via a resolved near CALL from the call-graph walk")
        if stop_reason == "jmp_out_of_function":
            return ("c_function", "medium",
                    "standard prologue, but body ends with a tail JMP out of the function "
                    "(e.g. into a shared exit/cleanup sequence) rather than its own RET -- "
                    "extent is the point of the jump, semantics of the jump target not analyzed")
        if stop_reason == "indirect_jmp":
            return ("c_function", "medium",
                    "standard prologue, but body ends at an indirect JMP (likely switch dispatch); "
                    "true function extent beyond the jump table is not yet resolved")
        return ("c_function", "low",
                "standard prologue, but disassembly hit the hard cap without a RET/indirect-jmp/"
                "tail-jmp (likely ran into data or a misaligned instruction stream)")

    # No 55 8B EC prologue.
    if stop_reason in clean_terminators and not anomaly:
        return ("unknown", "medium",
                f"frameless (no 55 8B EC) but disassembles cleanly to a {stop_reason}; first bytes "
                f"{data[start:start+4].hex()} -- plausible leaf function or unrecognized "
                f"library routine, not yet spot-checked")
    return ("unknown", "low",
            f"frameless (no 55 8B EC) and disassembly did not cleanly reach a RET/tail-jmp "
            f"(stop_reason={stop_reason}); first bytes {data[start:start+4].hex()} -- "
            f"possible disassembly misalignment, needs manual review")


def main():
    data = EXE.read_bytes()
    md = make_disassembler()

    rough_functions, calls_into_library, out_of_range_targets, discovery_order = rough_bfs(data, md)
    finalized, overlap_anomalies = finalize(data, md, rough_functions)

    starts_sorted = sorted(finalized.keys())

    # Build call edges (only between two functions inside our census; calls
    # into the known library region and unresolved indirect control flow are
    # tracked separately) and invert them into per-function caller lists.
    call_edges = []
    callers = {s: [] for s in starts_sorted}
    unresolved_indirect_targets = []
    for start in starts_sorted:
        info = finalized[start]
        caller_id = f"F_{start:04X}"
        for c in info["near_calls"]:
            tgt = c["target_file_offset"]
            if tgt in finalized:
                callee_id = f"F_{tgt:04X}"
                call_edges.append({
                    "caller_id": caller_id,
                    "callee_id": callee_id,
                    "site_file_offset": c["site_file_offset"],
                })
                callers[tgt].append(caller_id)
            elif tgt < MAIN_START:
                call_edges.append({
                    "caller_id": caller_id,
                    "callee_id": f"LIBRARY@{tgt:#06x}",
                    "site_file_offset": c["site_file_offset"],
                    "note": "target falls inside the already-identified STARTUP_C0S region "
                            "(layout/manifest.json KNOWN_LIBRARY, file offset [0x200,0x439)); "
                            "not walked further or given its own F_XXXX entry, since that "
                            "region is already owned/classified outside this census's scope.",
                })
            else:
                # Should be unreachable: finalized always contains every
                # target rough_bfs enqueued, and rough_bfs only enqueues
                # targets in [MAIN_START, RAW_LOAD_MODULE_END).
                call_edges.append({
                    "caller_id": caller_id,
                    "callee_id": f"UNRESOLVED@{tgt:#06x}",
                    "site_file_offset": c["site_file_offset"],
                    "note": "target address was not resolved to a census function; investigate.",
                })
        for ind in info["indirect"]:
            rec = dict(ind)
            rec["caller_id"] = caller_id
            unresolved_indirect_targets.append(rec)

    for oor in out_of_range_targets:
        unresolved_indirect_targets.append({
            "kind": "out_of_range_near_call_target",
            "caller_id": f"F_{oor['caller_start']:04X}",
            "site_file_offset": oor["site_file_offset"],
            "target_file_offset": oor["target_file_offset"],
            "note": "resolved near-CALL target falls at/after RAW_LOAD_MODULE_END "
                    "(file offset 172848); this should be impossible for a valid small-model "
                    "near call and needs investigation.",
        })

    # Cross-reference against the prologue-scan baseline (step 3 of the task).
    baseline = load_prologue_baseline()
    baseline_starts = set()
    if baseline is not None:
        baseline_starts = {f["start"] for f in baseline["functions"]}
    call_graph_starts = set(starts_sorted)
    reached_not_in_baseline = sorted(
        s for s in call_graph_starts - baseline_starts
        if data[s:s + 3] != PROLOGUE
    )
    reached_and_has_prologue_not_in_baseline = sorted(
        s for s in call_graph_starts - baseline_starts
        if data[s:s + 3] == PROLOGUE
    )
    baseline_not_reached = sorted(baseline_starts - call_graph_starts) if baseline is not None else []

    # Assemble per-function records.
    functions_out = []
    for start in starts_sorted:
        info = finalized[start]
        fid = f"F_{start:04X}"
        load_off = coord.file_offset_to_load_module(start)
        likely_type, confidence, confidence_reason = classify(start, info, data, baseline_starts)

        blockers = []
        if info["stop_reason"] == "indirect_jmp":
            blockers.append(
                f"body ends at an indirect JMP ({info['indirect'][-1]['op_str']}) -- likely a "
                f"switch dispatch table; true function extent past the table is unresolved"
            )
        if info["stop_reason"] == "cap_reached_no_terminator":
            blockers.append("disassembly hit the hard cap without reaching a RET/RETF/indirect JMP")
        if info.get("overlap_anomaly"):
            blockers.append("extent overlaps the next census function per the finalize-pass check")
        far_calls = [i for i in info["indirect"] if i["kind"] == "far_call"]
        if far_calls:
            blockers.append(f"{len(far_calls)} far call(s) not resolvable in the flat file/load-module coordinate system")
        indirect_calls = [i for i in info["indirect"] if i["kind"] == "indirect_call"]
        if indirect_calls:
            blockers.append(f"{len(indirect_calls)} indirect call(s) via register/memory operand not resolved")

        functions_out.append({
            "id": fid,
            # "start" is kept (in addition to "file_offset") for backward
            # compatibility with tools/library_scanner.py, which anchors on
            # docs/function-census.json's functions[].start / .size / .id
            # and is out of scope for this task (do not touch).
            "start": start,
            "file_offset": start,
            "load_module_offset": load_off,
            "end": info["end"],
            "size": info["end"] - start,
            "callers": sorted(set(callers[start])),
            "direct_callees": sorted({
                f"F_{c['target_file_offset']:04X}" if c["target_file_offset"] in finalized
                else f"LIBRARY@{c['target_file_offset']:#06x}"
                for c in info["near_calls"]
            }),
            "likely_type": likely_type,
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "matching_status": "unmatched",
            "blockers": blockers,
            "has_prologue": data[start:start + 3] == PROLOGUE,
            "has_sub_sp": info["has_sub_sp"],
            "stop_reason": info["stop_reason"],
            "insn_count": info["insn_count"],
            "in_prologue_scan_baseline": start in baseline_starts,
        })

    report = {
        "schema": "dave-function-census-v2",
        "method": "call-graph walk rooted at _main (file offset 0x439): recursive linear "
                  "disassembly of every reachable near-CALL target, stopping each function "
                  "body at its first RET/RETF or indirect JMP, with a finalize pass "
                  "capping extents at the next known function start. Supersedes the "
                  "prologue-scan baseline (docs/function-census-prologue-scan.json) as the "
                  "authoritative census. See docs/function-census.md.",
        "source": str(EXE.relative_to(ROOT)).replace("\\", "/"),
        "root": {"id": "F_0439", "file_offset": MAIN_START, "note": "_main, trusted call-graph root"},
        "region": {"start": MAIN_START, "end": RAW_LOAD_MODULE_END},
        "function_count": len(functions_out),
        "functions": functions_out,
        "call_edges": call_edges,
        "unresolved_indirect_targets": unresolved_indirect_targets,
        "calls_into_known_library": calls_into_library,
        "overlap_anomalies": overlap_anomalies,
        "cross_reference": {
            "baseline_source": "docs/function-census-prologue-scan.json" if baseline is not None else None,
            "baseline_function_count": len(baseline_starts) if baseline is not None else None,
            "call_graph_function_count": len(call_graph_starts),
            "reached_and_in_baseline_count": len(call_graph_starts & baseline_starts),
            "reached_with_prologue_but_not_in_baseline": reached_and_has_prologue_not_in_baseline,
            "reached_without_prologue_not_in_baseline": reached_not_in_baseline,
            "baseline_functions_not_reached_by_call_graph": baseline_not_reached,
        },
        "discovery_order": [f"F_{s:04X}" for s in discovery_order],
    }

    OUT_JSON.write_text(json.dumps(report, indent=2))
    print(f"Wrote {OUT_JSON}")
    print(f"  call-graph functions: {len(functions_out)}")
    if baseline is not None:
        print(f"  prologue-scan baseline functions: {len(baseline_starts)}")
        print(f"  baseline functions not reached by call graph: {len(baseline_not_reached)}")
        print(f"  call-graph starts with prologue not in baseline (should be 0): "
              f"{len(reached_and_has_prologue_not_in_baseline)}")
        print(f"  call-graph starts without prologue not in baseline (frameless/misalignment candidates): "
              f"{len(reached_not_in_baseline)}")
    print(f"  unresolved indirect/far control-flow sites: {len(unresolved_indirect_targets)}")
    print(f"  calls into known STARTUP_C0S library region: {len(calls_into_library)}")
    print(f"  overlap anomalies: {len(overlap_anomalies)}")


if __name__ == "__main__":
    main()
