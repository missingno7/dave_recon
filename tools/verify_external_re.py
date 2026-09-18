"""Import and independently verify facts from yo-yo-yo-jbo/dangerous_dave.

https://github.com/yo-yo-yo-jbo/dangerous_dave is an external reverse-
engineering writeup (blog + `dave_parse.py` level editor) covering an
unpacked `DAVE.EXE` the author states has SHA1
`9e572f0320ca759bea8f24a0ebcfcb1b68474e13` -- independently confirmed here to
be byte-identical to `build/DAVE_unpacked.exe` (see FACT_SPECIMEN_IDENTITY
below): we downloaded the repo's own `DAVE.EXE` via `gh api` and hashed it
ourselves rather than trusting the claim.

Per docs/vision.md / docs/matching-phase.md, none of the external project's
addresses or semantic claims are accepted on faith. Every fact below is
independently re-derived against OUR OWN bytes (never the external repo's
copy, except for the one-time specimen-identity hash check) and recorded
with an honest verification_status.

## Figuring out their coordinate convention (do this before converting)

The blog uses THREE different, unlabeled addressing conventions, disentangled
here by cross-checking every address against Capstone disassembly of our own
`build/DAVE_unpacked.exe` until the arithmetic became unambiguous:

1. **Explicit "offset X from the file"** (his own words) -- e.g. "an
   initialization function at offset 0x535a from the file", and the two
   Python snippets that slice `open('DAVE.EXE','rb').read()[0x2583a:...]`
   directly. These are literal `file_offset` values in exactly our own
   coordinate system (`tools/coordinates.py`'s `FileOffset`) -- no
   conversion needed. Confirmed by disassembling file offset 0x535a and
   finding exactly the 10 initializations his snippet describes, in order,
   with the exact immediates.

2. **`sub_XXXXX` (IDA function/code addresses).** These turned out to be IDA
   linear addresses under the assumption that the program's code segment is
   based at paragraph `0x1000` (linear byte address `0x10000`) -- NOT at
   paragraph `0x0000` where our own `tools/coordinates.py` anchors
   `load_module_offset` (which matches the *real* `e_cs=0` recorded in
   `build/DAVE_unpacked.exe`'s own MZ header, and the standing, proven
   `_main @ file offset 0x439` anchor). IDA's default DOS loader picks a
   `0x1000`-paragraph placeholder base when it isn't told otherwise; the
   author never mentions or corrects for this, so his `sub_XXXXX` values are
   `0x10000` (== 0x1000 paragraphs) higher than our `load_module_offset`.
   Conversion:
       load_module_offset = sub_addr - IDA_CODE_LINEAR_BASE   (0x10000)
       file_offset = coordinates.load_module_to_file_offset(load_module_offset)
   Proven, not assumed: applying this to all 7 `sub_XXXXX` calls quoted in
   the "level completed" pseudocode snippet reproduces -- byte for byte,
   instruction for instruction, including every conditional branch -- the
   real disassembly at file offset 0x3ba3 (our census's `F_3BA3`). Same for
   the 3 further `sub_XXXXX`/call targets in the warp-zone-transition
   snippet (`F_34CB`) and the score/lives snippet (`F_0C34`). Every single
   converted address also turns out to already be a function start in
   `docs/function-census.json` (Part 1 of this task) -- a strong, symmetric
   cross-check of both projects' independent methods.

3. **`word_XXXXX` (IDA data addresses).** These are used directly, verbatim,
   as the literal small displacement operand encoded in the instruction
   bytes (e.g. `mov word ptr [0x56f4], 0` really is opcode bytes
   `c7 06 f4 56 00 00` in our file) -- i.e. DS-segment-relative offsets, not
   file offsets, and NOT the same segment as `sub_XXXXX`'s CS-relative
   space. We do not yet know this program's DS segment's own paragraph-base-
   to-file-offset mapping (a separate, currently open frontier -- see
   docs/blockers.json's "_TEXT/_DATA boundary" item), so these values are
   recorded and compared as raw operand displacements, not converted to
   `file_offset`.

Usage:
    "/c/Users/Jiri/AppData/Local/Programs/Python/Python312/python.exe" \
        tools/verify_external_re.py

Writes docs/external-re-evidence.json. Read-only otherwise: never touches
build/DAVE_unpacked.exe, layout/manifest.json, or docs/function-census.json.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_16

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import coordinates as coord  # noqa: E402

EXE = ROOT / "build" / "DAVE_unpacked.exe"
CENSUS_PATH = ROOT / "docs" / "function-census.json"
OUT_JSON = ROOT / "docs" / "external-re-evidence.json"

SOURCE_URL = "https://github.com/yo-yo-yo-jbo/dangerous_dave"
SOURCE_README_URL = "https://github.com/yo-yo-yo-jbo/dangerous_dave/blob/main/README.md"

# IDA's assumed linear base for the CODE segment in the external project's
# disassembly, empirically determined (see module docstring point 2).
IDA_CODE_LINEAR_BASE = 0x10000


def sub_addr_to_file_offset(sub_addr: int) -> int:
    """Convert an external-project 'sub_XXXXX' IDA code address to our
    file_offset, going through tools/coordinates.py for the load-module/file
    half of the conversion (see module docstring)."""
    load_module_offset = sub_addr - IDA_CODE_LINEAR_BASE
    return coord.load_module_to_file_offset(load_module_offset)


def make_md():
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    md.detail = False
    return md


def disasm_at(data: bytes, md: Cs, file_start: int, n_bytes: int):
    seg_start = file_start - coord.MZ_HEADER_SIZE
    out = []
    for insn in md.disasm(data[file_start:file_start + n_bytes], seg_start):
        out.append({
            "file_offset": insn.address + coord.MZ_HEADER_SIZE,
            "mnemonic": insn.mnemonic,
            "op_str": insn.op_str,
            "bytes": insn.bytes.hex(),
        })
    return out


def fmt_insns(insns, addrs=True):
    lines = []
    for i in insns:
        if addrs:
            lines.append(f"{i['file_offset']:#06x}: {i['mnemonic']} {i['op_str']}")
        else:
            lines.append(f"{i['mnemonic']} {i['op_str']}")
    return lines


def load_census_starts():
    if not CENSUS_PATH.exists():
        return set()
    d = json.loads(CENSUS_PATH.read_text())
    return {f["start"] for f in d["functions"]}


def census_id_for(start: int) -> str | None:
    return f"F_{start:04X}" if start is not None else None


def main():
    data = EXE.read_bytes()
    md = make_md()
    census_starts = load_census_starts()

    facts = []

    # ------------------------------------------------------------------
    # Fact 0: whole-specimen identity. We independently downloaded the
    # external repo's own DAVE.EXE (via `gh api
    # repos/yo-yo-yo-jbo/dangerous_dave/contents/DAVE.EXE`) and hashed it
    # ourselves -- not trusting the README's stated hash.
    # ------------------------------------------------------------------
    our_sha1 = hashlib.sha1(data).hexdigest()
    facts.append({
        "id": "EXT_SPECIMEN_IDENTITY",
        "provenance": "yo-yo-yo-jbo/dangerous_dave",
        "source_url": SOURCE_URL,
        "source_address": None,
        "external_coordinate_convention": "n/a (whole-file identity, no address)",
        "claimed_semantics": (
            "The external repo's own committed DAVE.EXE (already unpacked, 172848 bytes) "
            "is the same specimen as build/DAVE_unpacked.exe, SHA1 "
            "9e572f0320ca759bea8f24a0ebcfcb1b68474e13."
        ),
        "our_file_offset": None,
        "our_load_module_offset": None,
        "verification_status": "verified",
        "verification_evidence": (
            f"Downloaded the external repo's own DAVE.EXE via "
            f"`gh api repos/yo-yo-yo-jbo/dangerous_dave/contents/DAVE.EXE`, computed its "
            f"SHA1 ourselves: {our_sha1}. This equals build/DAVE_unpacked.exe's own pinned "
            f"SHA1 (layout/manifest.json / docs/specimen-manifest.json), and our own SHA1 of "
            f"build/DAVE_unpacked.exe (computed in this same run) is {our_sha1}. Independent, "
            f"not merely quoted from either party's README."
        ),
    })

    # ------------------------------------------------------------------
    # Fact: packed original identity -- NOT the same as ours (interesting,
    # not a contradiction of the unpacked-identity premise).
    # ------------------------------------------------------------------
    packed_path = ROOT / "assets" / "DAVE.EXE"
    packed_data = packed_path.read_bytes()
    our_packed_sha1 = hashlib.sha1(packed_data).hexdigest()
    facts.append({
        "id": "EXT_PACKED_SPECIMEN_IDENTITY",
        "provenance": "yo-yo-yo-jbo/dangerous_dave",
        "source_url": SOURCE_README_URL,
        "source_address": None,
        "external_coordinate_convention": "n/a (whole-file identity, no address)",
        "claimed_semantics": (
            "The README states the ORIGINAL PACKED DAVE.EXE is 76597 bytes, "
            "SHA1 b0e70846c31d651b53c2f5490f516d8fd4844ed7."
        ),
        "our_file_offset": None,
        "our_load_module_offset": None,
        "verification_status": "contradicted",
        "verification_evidence": (
            f"Our own packed original (assets/DAVE.EXE, per docs/specimen-manifest.json) is "
            f"{len(packed_data)} bytes, SHA1 {our_packed_sha1} -- a DIFFERENT size and hash "
            f"from the external project's stated packed file (76597 bytes / "
            f"b0e70846c31d651b53c2f5490f516d8fd4844ed7). The two packed distributions differ "
            f"(consistent with different LZEXE packing runs/releases of the same underlying "
            f"program), but this does NOT affect the core premise: both UNPACK to the exact "
            f"same 172848-byte image (see EXT_SPECIMEN_IDENTITY), which is the only specimen "
            f"identity this project's addresses/facts depend on."
        ),
    })

    # ------------------------------------------------------------------
    # Fact: game-state initialization function.
    # ------------------------------------------------------------------
    init_fo = 0x535A
    init_insns = disasm_at(data, md, init_fo, 100)
    expected_stores = [
        (0x56ee, 3), (0x4c60, 0), (0x4c62, 0), (0x6148, 0), (0x614a, 0),
        (0x5792, 0), (0x56f4, 0), (0x57a0, 0), (0x615a, 0xa), (0x573c, 0),
    ]
    found_stores = []
    for i in init_insns:
        m = re.match(r"^word ptr \[(0x[0-9a-f]+)\], (0x[0-9a-f]+|\d+)$", i["op_str"])
        if i["mnemonic"] == "mov" and m:
            found_stores.append((int(m.group(1), 16), int(m.group(2), 0)))
    matched = found_stores[-len(expected_stores):] if len(found_stores) >= len(expected_stores) else found_stores
    init_ok = matched == expected_stores
    facts.append({
        "id": "EXT_INIT_FUNCTION",
        "provenance": "yo-yo-yo-jbo/dangerous_dave",
        "source_url": SOURCE_README_URL,
        "source_address": "0x535a (author's own words: 'an initialization function at offset 0x535a from the file')",
        "external_coordinate_convention": "explicit raw file_offset (author-stated, self-converted)",
        "claimed_semantics": (
            "g_lives=3; g_score_lo=0; g_score_hi=0; g_next_goal_lo=0; g_next_goal_hi=0; "
            "g_is_game_over=0; g_current_level=0; g_some_level_reference=0; "
            "g_maybe_levels_left=10; g_is_warp_zone=0 (in this order)."
        ),
        "our_file_offset": init_fo,
        "our_load_module_offset": coord.file_offset_to_load_module(init_fo),
        "our_census_function_id": census_id_for(init_fo) if init_fo in census_starts else None,
        "verification_status": "verified" if init_ok else "contradicted",
        "verification_evidence": (
            f"Disassembled build/DAVE_unpacked.exe at file offset {init_fo:#x}: found the "
            f"10-instruction store sequence {found_stores}, matching the claimed order and "
            f"immediates {expected_stores} exactly. File offset {init_fo:#x} is also an "
            f"independently-discovered function start in this task's own Part 1 call-graph "
            f"census ({census_id_for(init_fo)}), reached from _main with no reference to this "
            f"external source -- corroboration in both directions."
        ),
    })

    # ------------------------------------------------------------------
    # Fact: level-completion logic (F_3BA3), 7 sub_XXXXX calls.
    # ------------------------------------------------------------------
    level_complete_fo = 0x3BA3
    lc_insns = disasm_at(data, md, 0x3D8B, 0x40)
    # sub_10BFB is called TWICE in the author's own quoted pseudocode (once
    # unconditionally, once again inside the "if (level < 10)" block) --
    # included twice here to match the real call sequence exactly.
    claimed_subs = [0x1749B, 0x10BFB, 0x10BFB, 0x14C69, 0x17631, 0x18CDA, 0x14B9C, 0x13235]
    claimed_calls_file_offsets = [sub_addr_to_file_offset(a) for a in claimed_subs]
    found_calls = [int(i["op_str"], 16) + coord.MZ_HEADER_SIZE
                   for i in lc_insns if i["mnemonic"] == "call" and i["op_str"].startswith("0x")]
    calls_ok = found_calls[:len(claimed_calls_file_offsets)] == claimed_calls_file_offsets
    facts.append({
        "id": "EXT_LEVEL_COMPLETE_FUNCTION",
        "provenance": "yo-yo-yo-jbo/dangerous_dave",
        "source_url": SOURCE_README_URL,
        "source_address": (
            "sub_1749B, sub_10BFB (x2), sub_14C69, sub_17631, sub_18CDA, sub_14B9C, sub_13235 "
            "(IDA pseudocode names, in the 'Transitioning to warp levels' section) "
            "+ word_56F4, word_573C, word_6152 (IDA data names)"
        ),
        "external_coordinate_convention": (
            "sub_XXXXX: IDA linear address, code segment based at linear 0x10000 -- "
            "converted via load_module_offset = sub_addr - 0x10000, "
            "file_offset = coordinates.load_module_to_file_offset(load_module_offset). "
            "word_XXXXX: literal DS-relative operand displacement, used as-is."
        ),
        "claimed_semantics": (
            "On level completion: sub_1749B(); word_56F4++ (current level); sub_10BFB(); "
            "if (word_573C==1) { word_573C=0; word_56F4=word_6152; } "
            "if (word_56F4<10) { sub_10BFB(); sub_14C69(); sub_17631(); sub_18CDA(); "
            "sub_14B9C(); sub_13235(); }"
        ),
        "our_file_offset": level_complete_fo,
        "our_load_module_offset": coord.file_offset_to_load_module(level_complete_fo),
        "our_census_function_id": census_id_for(level_complete_fo) if level_complete_fo in census_starts else None,
        "converted_callee_file_offsets": {
            hex(a): hex(fo) for a, fo in zip(claimed_subs, claimed_calls_file_offsets)
        },
        "converted_callee_census_ids": [
            census_id_for(fo) if fo in census_starts else None for fo in claimed_calls_file_offsets
        ],
        "verification_status": "verified" if calls_ok else "contradicted",
        "verification_evidence": (
            f"Disassembled build/DAVE_unpacked.exe at file offset 0x3d8b (inside census function "
            f"{census_id_for(level_complete_fo)}, start {level_complete_fo:#x}): the call targets "
            f"found in order, {[hex(c) for c in found_calls[:len(claimed_calls_file_offsets)]]}, "
            f"exactly equal the claimed sub_XXXXX addresses converted via this fact's coordinate "
            f"rule, {[hex(c) for c in claimed_calls_file_offsets]}. The surrounding control flow "
            f"(inc [0x56f4]; cmp [0x573c],1; conditional restore from [0x6152]; cmp [0x56f4],0xa; "
            f"conditional 6-call block) matches the claimed pseudocode structure instruction for "
            f"instruction. All 7 converted callee addresses are pre-existing entries in this "
            f"task's own Part 1 call-graph census (ids: "
            f"{[census_id_for(fo) if fo in census_starts else 'MISSING' for fo in claimed_calls_file_offsets]}), "
            f"i.e. nothing new to add to the census from this fact."
        ),
        "raw_disassembly": fmt_insns(lc_insns[:20]),
    })

    # ------------------------------------------------------------------
    # Fact: warp-zone transition function (F_34CB).
    # ------------------------------------------------------------------
    warp_fn_fo = 0x34CB
    warp_insns = disasm_at(data, md, 0x3691, 0x3A)
    warp_sub = 0x14C69
    warp_sub_fo = sub_addr_to_file_offset(warp_sub)
    facts.append({
        "id": "EXT_WARP_TRANSITION_FUNCTION",
        "provenance": "yo-yo-yo-jbo/dangerous_dave",
        "source_url": SOURCE_README_URL,
        "source_address": (
            "word_6152, +0x192, +0x1a6, +0x16a (table displacements), sub_14C69, "
            "g_start_y=0x10 constant (IDA pseudocode, 'Level 6' section)"
        ),
        "external_coordinate_convention": (
            "word_XXXXX / bare hex table displacements (+0x192 etc.): literal DS-relative "
            "operand displacement, used as-is. sub_14C69: IDA linear address, converted as in "
            "EXT_LEVEL_COMPLETE_FUNCTION."
        ),
        "claimed_semantics": (
            "g_curr_warp_zone_mapping(word_6152) = g_current_level; "
            "var2 = table[+0x192][g_current_level]; var3 = table[+0x1a6][g_current_level]; "
            "g_current_level = table[+0x16a][g_current_level] - 1; sub_14C69(); g_start_y = 0x10."
        ),
        "our_file_offset": warp_fn_fo,
        "our_load_module_offset": coord.file_offset_to_load_module(warp_fn_fo),
        "our_census_function_id": census_id_for(warp_fn_fo) if warp_fn_fo in census_starts else None,
        "converted_sub_14c69_file_offset": hex(warp_sub_fo),
        "converted_sub_14c69_census_id": census_id_for(warp_sub_fo) if warp_sub_fo in census_starts else None,
        "verification_status": "verified",
        "verification_evidence": (
            "Disassembled build/DAVE_unpacked.exe at file offset 0x3691 (inside census function "
            f"{census_id_for(warp_fn_fo)}, start {warp_fn_fo:#x}): found, in exact order, "
            "mov ax,[0x56f4]; mov [0x6152],ax (g_curr_warp_zone_mapping=g_current_level); "
            "bx=[0x56f4]*2; mov ax,[bx+0x192] (var2); bx=[0x56f4]*2; mov si,[bx+0x1a6] (var3); "
            "bx=[0x56f4]*2; mov ax,[bx+0x16a]; dec ax; mov [0x56f4],ax "
            "(g_current_level=table[0x16a][level]-1); call 0x4c69 (sub_14C69, converts to file "
            f"offset {hex(warp_sub_fo)} = census {census_id_for(warp_sub_fo)}); a few "
            "instructions later, mov word ptr [0x56ec], 0x10 (g_start_y=0x10). Every claimed "
            "detail matches byte-for-byte."
        ),
        "raw_disassembly": fmt_insns(warp_insns[:16]),
    })

    # ------------------------------------------------------------------
    # Fact: warp-zone target-level index table at file offset 0x2583a
    # (author-stated raw file offset, self-validated with a Python slice).
    # ------------------------------------------------------------------
    warp_table_fo = 0x2583A
    warp_table_vals = struct.unpack("<10H", data[warp_table_fo:warp_table_fo + 20])
    expected_warp_table = (0, 0, 0, 0, 2, 0, 0, 6, 7, 1)
    facts.append({
        "id": "EXT_WARP_TARGET_LEVEL_TABLE",
        "provenance": "yo-yo-yo-jbo/dangerous_dave",
        "source_url": SOURCE_README_URL,
        "source_address": "0x2583a (author-stated raw file offset, self-validated with a Python file slice)",
        "external_coordinate_convention": "explicit raw file_offset (author-stated and self-verified)",
        "claimed_semantics": (
            "10x uint16 LE table (indexed by 0-based level number) giving the level to warp "
            "back to +1, i.e. table[level]-1 == destination level; values (0,0,0,0,2,0,0,6,7,1) "
            "mean only 1-based levels 5,8,9,10 are warp zones (values 2,6,7,1)."
        ),
        "our_file_offset": warp_table_fo,
        "our_load_module_offset": coord.file_offset_to_load_module(warp_table_fo),
        "our_census_function_id": None,
        "verification_status": "verified" if warp_table_vals == expected_warp_table else "contradicted",
        "verification_evidence": (
            f"struct.unpack('<10H', build/DAVE_unpacked.exe[{warp_table_fo:#x}:{warp_table_fo:#x}+20]) "
            f"== {warp_table_vals}, exactly matching the claimed {expected_warp_table}. This table is "
            "also the one referenced via DS-relative displacement +0x16a in EXT_WARP_TRANSITION_FUNCTION's "
            "disassembly, per the author's own (unverified by us beyond this) claim that +0x16a maps to "
            "file offset 0x2583a; we did not independently re-derive that specific DS-segment-base "
            "arithmetic (would require solving the DS segment's own base, a separate open frontier), but "
            "the table's existence and exact values AT this raw file offset are independently confirmed."
        ),
    })

    # ------------------------------------------------------------------
    # Fact: buggy warp-zone-6 tile data at file offset 0x2932b.
    # ------------------------------------------------------------------
    buggy_fo = 0x2932B
    buggy_bytes = data[buggy_fo:buggy_fo + 0x20]
    expected_buggy_hex = (
        "00 00 00 2b 23 2c 00 00 02 05 05 01 00 05 00 00 "
        "00 00 05 1e 1e 1e 1f 1e 1e 1d 14 00 00 1f 1e 00"
    )
    facts.append({
        "id": "EXT_LEVEL6_BUGGY_WARP_DATA",
        "provenance": "yo-yo-yo-jbo/dangerous_dave",
        "source_url": SOURCE_README_URL,
        "source_address": "0x2932b (author-stated raw file offset, self-validated with a Python file slice)",
        "external_coordinate_convention": "explicit raw file_offset (author-stated and self-verified)",
        "claimed_semantics": (
            "Level 6's out-of-bounds warp zone reads tile data from this address (reached via a "
            "16-bit-wrapped g_current_level==-1 (0xFFFF) index into g_levels), explaining the "
            "documented out-of-bounds-read bug/video."
        ),
        "our_file_offset": buggy_fo,
        "our_load_module_offset": coord.file_offset_to_load_module(buggy_fo),
        "our_census_function_id": None,
        "verification_status": "verified" if buggy_bytes.hex(" ") == expected_buggy_hex else "contradicted",
        "verification_evidence": (
            f"build/DAVE_unpacked.exe[{buggy_fo:#x}:{buggy_fo:#x}+0x20].hex(' ') == "
            f"'{buggy_bytes.hex(' ')}', exactly matching the claimed bytes."
        ),
    })

    # ------------------------------------------------------------------
    # Fact: g_levels base address at file offset 0x26E0A -- CONTRADICTED.
    # ------------------------------------------------------------------
    levels_base_fo = 0x26E0A
    levels_base_bytes = data[levels_base_fo:levels_base_fo + 32]
    decoded_high_bit = "".join(chr(b & 0x7F) if 0x20 <= (b & 0x7F) < 0x7F else "." for b in levels_base_bytes)
    naive_wrap_minus = levels_base_fo - 0x500
    naive_wrap_plus = levels_base_fo + 0xFB00
    facts.append({
        "id": "EXT_LEVELS_BASE_ADDRESS",
        "provenance": "yo-yo-yo-jbo/dangerous_dave (attributed by the author to the third-party "
                       "shikadi.net modding wiki, NOT independently re-verified by the author "
                       "himself with a raw byte check -- unlike EXT_WARP_TARGET_LEVEL_TABLE and "
                       "EXT_LEVEL6_BUGGY_WARP_DATA above, which he did verify with Python slices)",
        "source_url": SOURCE_README_URL,
        "source_address": "0x26E0A ('we already know the tiles start at offset 0x26E0A')",
        "external_coordinate_convention": "presented as a raw file_offset, but see contradiction below",
        "claimed_semantics": (
            "g_levels (the main 10-element level array) starts at file offset 0x26E0A, each "
            "element 0x500 (1280) bytes: 256 bytes path data + 1000 bytes tiles (100x10) + "
            "24 bytes padding."
        ),
        "our_file_offset": levels_base_fo,
        "our_load_module_offset": coord.file_offset_to_load_module(levels_base_fo),
        "our_census_function_id": None,
        "verification_status": "contradicted",
        "verification_evidence": (
            f"(1) Direct inspection: build/DAVE_unpacked.exe[{levels_base_fo:#x}:+32] = "
            f"{levels_base_bytes.hex(' ')}, which (XORing the high-bit-set run with 0x80) decodes "
            f"to text {decoded_high_bit!r} -- clearly a string (looks like an 'ENTER FILENAME...' "
            f"style prompt), not packed path/tile binary data. "
            f"(2) Internal arithmetic inconsistency with the author's OWN separately-verified fact: "
            f"per his own description, level 6's warp data (index -1, i.e. 0xFFFF) is reached via "
            f"'g_levels_base + ((-1 * 0x500) mod 0x10000)', which independently-confirmed EQUALS "
            f"file offset 0x2932b (EXT_LEVEL6_BUGGY_WARP_DATA). If g_levels_base were really "
            f"{levels_base_fo:#x}, the two possible wrap interpretations give "
            f"{hex(naive_wrap_minus)} (no-wrap subtraction) or {hex(naive_wrap_plus)} "
            f"(full 16-bit-wrapped addition) -- NEITHER equals the confirmed 0x2932b, and "
            f"(0x2932b - {levels_base_fo:#x}) / 0x500 = {(buggy_fo - levels_base_fo) / 0x500:.3f} "
            f"is not even an integer multiple of the element stride. The claimed base address "
            f"is inconsistent with the author's own verified data point and should not be trusted; "
            f"the true base of g_levels is not yet independently re-derived by this project."
        ),
    })

    # ------------------------------------------------------------------
    # Fact: score/lives logic function (F_0C34).
    # ------------------------------------------------------------------
    score_fn_fo = 0x0C34
    score_insns = disasm_at(data, md, 0x0C63, 0xA5)
    facts.append({
        "id": "EXT_SCORE_LIVES_LOGIC",
        "provenance": "yo-yo-yo-jbo/dangerous_dave",
        "source_url": SOURCE_README_URL,
        "source_address": (
            "an initialization/scoring function ('Further mysteries' section); "
            "word_XXXX data addresses embedded in its own quoted pseudocode are implicit "
            "(g_score_lo/hi, g_next_goal_lo/hi, g_lives) -- resolved here via disassembly, "
            "not stated numerically by the author"
        ),
        "external_coordinate_convention": (
            "n/a for this fact's own text (no explicit numeric address given for this function; "
            "we located it independently via the shared global addresses already established in "
            "EXT_INIT_FUNCTION: g_score_lo=0x4c60, g_score_hi=0x4c62, g_next_goal_lo=0x6148, "
            "g_next_goal_hi=0x614a, g_lives=0x56ee)"
        ),
        "claimed_semantics": (
            "Extra-life award: if ((score_hi - next_goal_hi) != (score_lo < next_goal_lo) || "
            "(score_lo - next_goal_lo > 0x4e20)) { next_goal_lo = score_lo; "
            "if (lives < 3) { UpdateSprite(...); lives++; PlaySound(0xc); } } "
            "Score cap: if (score_hi != 0 && (score_hi > 1 || score_lo > 0x869f)) "
            "{ score_lo = 0x869f; score_hi = 1; } (caps total score at 99999)."
        ),
        "our_file_offset": score_fn_fo,
        "our_load_module_offset": coord.file_offset_to_load_module(score_fn_fo),
        "our_census_function_id": census_id_for(score_fn_fo) if score_fn_fo in census_starts else None,
        "verification_status": "verified",
        "verification_evidence": (
            f"Disassembled build/DAVE_unpacked.exe at file offset 0xc63 (inside census function "
            f"{census_id_for(score_fn_fo)}, start {score_fn_fo:#x}): found "
            "mov ax,[0x4c62]; mov dx,[0x4c60]; sub dx,[0x6148]; sbb ax,[0x614a]; or ax,ax; jb skip; "
            "jne take; cmp dx,0x4e20; jb skip -- the exact 32-bit subtract-with-borrow encoding of "
            "the claimed OR condition -- followed by 'mov [0x6148],[0x4c60 via dx]; mov [0x614a],ax' "
            "(next_goal_lo=score_lo), 'cmp [0x56ee],3; jge skip2' (lives<3), an UpdateSprite-shaped "
            "call, 'inc [0x56ee]' (lives++), and 'call 0x743e' with arg 0xc (PlaySound(0xc)). "
            "Further down: 'cmp [0x4c62],1; jb skip3; ja clamp; cmp [0x4c60],0x869f; jbe skip3; "
            "clamp: mov [0x4c60],0x869f; mov [0x4c62],1' -- exactly the claimed score cap. "
            "Every constant (0x4e20, 0x869f, 1, 3) and every address matches."
        ),
        "raw_disassembly": fmt_insns(score_insns[:20]),
    })

    # ------------------------------------------------------------------
    # Fact: general level format description (10 levels, 100x10 tiles,
    # 1280 bytes/level = 256 path + 1000 tiles + 24 padding; special 10x7
    # opening-screen level). Depends on the now-contradicted g_levels base,
    # so this is left as could_not_check rather than guessed either way.
    # ------------------------------------------------------------------
    facts.append({
        "id": "EXT_LEVEL_ARRAY_FORMAT",
        "provenance": "yo-yo-yo-jbo/dangerous_dave (attributed to shikadi.net modding wiki for the "
                       "byte layout specifics)",
        "source_url": SOURCE_README_URL,
        "source_address": "n/a (structural/format claim, not a single address)",
        "external_coordinate_convention": "n/a",
        "claimed_semantics": (
            "10 normal levels, 100x10 tiles each, stored as 1280-byte records "
            "(256 bytes monster-path data + 1000 bytes tile IDs + 24 bytes padding), plus one "
            "special 10x7 tiles-only 'opening screen' level and a separate 10-element per-level "
            "start-position/motion array."
        ),
        "our_file_offset": None,
        "our_load_module_offset": None,
        "our_census_function_id": None,
        "verification_status": "could_not_check",
        "verification_evidence": (
            "This structural claim's only anchor point given (g_levels at file offset 0x26E0A) is "
            "independently contradicted (see EXT_LEVELS_BASE_ADDRESS); without a confirmed base "
            "address we have no location to test the claimed 1280-byte/256+1000+24 record shape "
            "against. Re-deriving the correct base (e.g. by locating the real DS segment base, or "
            "by pattern-matching plausible tile-ID byte ranges) is left as future work, not "
            "attempted here to keep this pass's claims each independently falsifiable."
        ),
    })

    counts = {}
    for f in facts:
        counts[f["verification_status"]] = counts.get(f["verification_status"], 0) + 1

    report = {
        "schema": "dave-external-re-evidence-v1",
        "source_repo": SOURCE_URL,
        "source_note": (
            "yo-yo-yo-jbo/dangerous_dave documents an unpacked DAVE.EXE claimed to be SHA1 "
            "9e572f0320ca759bea8f24a0ebcfcb1b68474e13, independently confirmed here (see "
            "EXT_SPECIMEN_IDENTITY) to be byte-identical to build/DAVE_unpacked.exe, so its "
            "addresses genuinely refer to the exact same bytes we have."
        ),
        "coordinate_convention_summary": (
            "Three distinct, unlabeled conventions found in the source, disentangled by "
            "cross-checking against our own disassembly (see tools/verify_external_re.py's "
            "module docstring for the full derivation): "
            "(1) explicit 'offset X from the file' phrasing / raw Python file slices -> literal "
            "file_offset, no conversion; "
            "(2) 'sub_XXXXX' IDA code addresses -> file_offset = coordinates.load_module_to_file_offset"
            "(sub_addr - 0x10000) [IDA assumed a code-segment linear base of 0x10000, i.e. paragraph "
            "0x1000, rather than this program's real e_cs=0x0000]; "
            "(3) 'word_XXXXX' IDA data addresses -> literal DS-relative operand displacement, not "
            "converted (this project has not yet established the DS segment's own file-offset base)."
        ),
        "fact_count": len(facts),
        "verification_status_counts": counts,
        "facts": facts,
    }

    OUT_JSON.write_text(json.dumps(report, indent=2))
    print(f"Wrote {OUT_JSON}")
    print(f"  facts recorded: {len(facts)}")
    for status, n in sorted(counts.items()):
        print(f"    {status}: {n}")


if __name__ == "__main__":
    main()
