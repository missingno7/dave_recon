"""Regenerate docs/data-layout.json: the DATA architecture of build/DAVE_unpacked.exe.

Everything numeric in the output is (re-)derived from the specimen bytes at run
time; the only hand-written inputs are the CURATED_* tables below, and every
entry there carries the code evidence that justifies it (and is re-checked
against the bytes where a mechanical check is possible). No derived game data
(level contents, string text, graphics) is written to the JSON -- only
offsets, sizes, counts and hashes.

Sources of evidence, in order of strength:
  1. The MZ relocation table: every far segment the program addresses by
     paragraph appears as a relocated `mov ax,SEG` / `mov word ptr [..],SEG`
     immediate. Segment start = paragraph*16 + header size.
  2. C0S startup code: DGROUP paragraph (`mov dx,DGROUP` at the entry point),
     the _BSS clear range (`mov di,bdata; mov cx,edata; sub cx,di; rep stosb`),
     and the _INIT_ table walk (`mov ax,seg _INIT_; mov ds,ax; mov si,..; mov di,..`).
  3. toolchain/LIB/C0S.OBJ and CS.LIB (optional, git-ignored; install with
     tools/setup_toolchain.py): C0S's own _DATA publics, and placement of each
     library module's _DATA by unique byte match (fixup bytes masked).
  4. A DS-tracking sweep of every game function (docs/function-census.json
     starts in [0x439, 0x9613)) collecting DGROUP-relative memory operands.

Usage:  python tools/data_layout.py [--exe build/DAVE_unpacked.exe] [--out docs/data-layout.json]
        python tools/data_layout.py --check     # regenerate and compare with the committed JSON
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import re
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import levels as levels_mod  # noqa: E402

DEFAULT_EXE = ROOT / "build" / "DAVE_unpacked.exe"
DEFAULT_OUT = ROOT / "docs" / "data-layout.json"
CENSUS = ROOT / "docs" / "function-census.json"
TOOLCHAIN_LIB = ROOT / "toolchain" / "LIB"

GAME_CODE = (0x439, 0x9613)      # file offsets: game code (docs/function-census.json)
LIB_CODE_START = 0x9613          # Borland CS.LIB runtime starts here (layout/manifest.json)


# ---------------------------------------------------------------- MZ basics
class Exe:
    def __init__(self, data: bytes):
        self.b = data
        if data[:2] != b"MZ":
            raise ValueError("not MZ")
        (self.e_cblp, self.e_cp, self.e_crlc, self.e_cparhdr, self.e_minalloc,
         self.e_maxalloc, self.e_ss, self.e_sp, _csum, self.e_ip, self.e_cs,
         self.e_lfarlc) = struct.unpack_from("<12H", data, 2)
        self.hdr = self.e_cparhdr * 16
        self.relocs = []
        for i in range(self.e_crlc):
            off, seg = struct.unpack_from("<HH", data, self.e_lfarlc + 4 * i)
            lm = seg * 16 + off
            self.relocs.append({"load_module": lm, "file": lm + self.hdr,
                                "value": struct.unpack_from("<H", data, lm + self.hdr)[0]})
        self.reloc_sites = {r["load_module"] for r in self.relocs}

    def w(self, fo):
        return struct.unpack_from("<H", self.b, fo)[0]

    def d(self, fo):
        return struct.unpack_from("<I", self.b, fo)[0]

    def seg_file(self, para):
        return para * 16 + self.hdr


def hx(v):
    return None if v is None else "0x%X" % v


# ------------------------------------------------------------- disassembly
def _capstone():
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
    md.detail = True
    return md


# --------------------------------------------------------------- RLE codec
def unrle(src: bytes, length: int):
    """The decompressor at file 0x7ED4 (called via 0x7E00): byte b>=0x80 copies
    b-0x7F literal bytes; b<0x80 repeats the next byte b+3 times; stops once
    `length` bytes have been produced. Returns (output, input bytes consumed)."""
    out = bytearray()
    i = 0
    while len(out) < length:
        b = src[i]
        i += 1
        if b >= 0x80:
            n = b - 0x7F
            out += src[i:i + n]
            i += n
        else:
            out += bytes([src[i]]) * (b + 3)
            i += 1
    return bytes(out), i


# ------------------------------------------------------- startup analysis
def analyse_startup(exe: Exe):
    b = exe.b
    entry = exe.hdr + exe.e_cs * 16 + exe.e_ip
    assert b[entry] == 0xBA and (entry + 1 - exe.hdr) in exe.reloc_sites
    dgroup = exe.w(entry + 1)
    # _BSS clear: bf LL HH  b9 LL HH  2b cf  fc  f3 aa
    m = re.search(rb"\xbf(..)\xb9(..)\x2b\xcf\xfc\xf3\xaa", b[entry:entry + 0x200], re.S)
    bdata = struct.unpack("<H", m.group(1))[0]
    edata = struct.unpack("<H", m.group(2))[0]
    bss_clear_site = entry + m.start()
    # _INIT_/_EXIT_ walks: b8 SS SS 8e d8 be LL HH bf LL HH e8
    walks = []
    for mm in re.finditer(rb"\xb8(..)\x8e\xd8\xbe(..)\xbf(..)\xe8", b[entry:entry + 0x200], re.S):
        seg = struct.unpack("<H", mm.group(1))[0]
        walks.append({"file": entry + mm.start(), "segment": seg,
                      "si": struct.unpack("<H", mm.group(2))[0],
                      "di": struct.unpack("<H", mm.group(3))[0]})
    # _stklen / _heaplen DS operands used by the stack-size check
    m2 = re.search(rb"\x8b\x3e(..)\x81\xff\x00\x02", b[entry:entry + 0x200], re.S)
    stklen_ds = struct.unpack("<H", m2.group(1))[0]
    m3 = re.search(rb"\x03\x3e(..)\x72", b[entry:entry + 0x200], re.S)
    heaplen_ds = struct.unpack("<H", m3.group(1))[0]
    return {"entry_file": entry, "dgroup": dgroup, "bdata": bdata, "edata": edata,
            "bss_clear_site": bss_clear_site, "init_walks": walks,
            "stklen_ds": stklen_ds, "heaplen_ds": heaplen_ds}


# ------------------------------------------------------- toolchain (OMF)
def load_toolchain():
    c0s = TOOLCHAIN_LIB / "C0S.OBJ"
    cslib = TOOLCHAIN_LIB / "CS.LIB"
    if not (c0s.exists() and cslib.exists()):
        return None
    from omf import OmfReader
    r = OmfReader()
    c0 = r.read_file(c0s)
    mods = [r.read(mb, name) for name, mb in r.split_library(cslib.read_bytes())]
    return c0, mods


def masked_pattern(mod, seg):
    length = mod.segment_lengths.get(seg, 0)
    data = mod.segments.get(seg, b"")
    data = data + b"\0" * (length - len(data))
    mask = [True] * length
    for f in mod.fixups_in(seg):
        for k in range(f["width"]):
            if f["offset"] + k < length:
                mask[f["offset"] + k] = False
    return re.compile(b"".join(re.escape(bytes([data[i]])) if mask[i] else b"." for i in range(length)), re.S), length, sum(mask)


# ------------------------------------------------------- DS-tracking scan
def scan_game_code(exe: Exe, dgroup: int, census_starts):
    """Collect DGROUP-relative memory operands, CS-relative operands, and
    immediate near-pointer candidates from every game function."""
    from capstone import x86_const as X
    md = _capstone()
    b = exe.b
    ds_refs = collections.defaultdict(list)   # disp -> [(func, site, width, kind, write)]
    cs_refs = collections.defaultdict(list)
    imm_refs = collections.defaultdict(list)
    starts = [s for s in census_starts if GAME_CODE[0] <= s < GAME_CODE[1]]
    seg_regs = {X.X86_REG_DS: "ds", X.X86_REG_ES: "es", X.X86_REG_SS: "ss", X.X86_REG_CS: "cs"}
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else GAME_CODE[1]
        fid = "F_%04X" % s
        ds_state = "dgroup"
        regval = {}
        stack = []
        insns = list(md.disasm(b[s:e], s - exe.hdr))
        for j, i in enumerate(insns):
            fo = i.address + exe.hdr
            mn = i.mnemonic
            ops = i.operands
            # --- track register values that are DGROUP / CS
            if mn == "mov" and len(ops) == 2 and ops[0].type == X.X86_OP_REG:
                dst = ops[0].reg
                if ops[1].type == X.X86_OP_IMM:
                    imm_site = i.address + i.size - 2
                    if (ops[1].imm & 0xFFFF) == dgroup and imm_site in exe.reloc_sites:
                        regval[dst] = "dgroup"
                    else:
                        regval[dst] = None
                elif ops[1].type == X.X86_OP_REG:
                    src = ops[1].reg
                    if src == X.X86_REG_SS:
                        regval[dst] = "dgroup"
                    elif src == X.X86_REG_DS:
                        regval[dst] = ds_state
                    elif src == X.X86_REG_CS:
                        regval[dst] = "cs"
                    else:
                        regval[dst] = regval.get(src)
                else:
                    regval[dst] = None
                if dst == X.X86_REG_DS:
                    if ops[1].type == X.X86_OP_REG:
                        ds_state = regval.get(dst) or "other"
                    else:
                        ds_state = "other"
            elif mn == "push":
                if ops and ops[0].type == X.X86_OP_REG:
                    r = ops[0].reg
                    stack.append("cs" if r == X.X86_REG_CS else
                                 ds_state if r == X.X86_REG_DS else
                                 "dgroup" if r == X.X86_REG_SS else regval.get(r))
                else:
                    stack.append(None)
            elif mn == "pop":
                v = stack.pop() if stack else "dgroup"
                if ops and ops[0].type == X.X86_OP_REG and ops[0].reg == X.X86_REG_DS:
                    ds_state = v or "other"
            elif mn in ("ret", "retf", "iret"):
                ds_state = "dgroup"
                stack = []
            # --- memory operands
            for op in ops:
                if op.type != X.X86_OP_MEM:
                    continue
                m = op.mem
                if m.base in (X.X86_REG_BP, X.X86_REG_SP) or mn == "lea":
                    continue
                seg = seg_regs.get(m.segment, "default")
                if seg == "ss":
                    state = "dgroup"
                elif seg in ("default", "ds"):
                    state = ds_state
                elif seg == "cs":
                    state = "cs"
                else:
                    continue
                disp = m.disp & 0xFFFF
                kind = "direct" if (m.base == 0 and m.index == 0) else "indexed"
                if kind == "indexed" and disp < 0xA8:
                    continue   # struct-field displacement off a pointer, not a global
                write = (op is ops[0]) and mn in ("mov", "add", "sub", "inc", "dec", "and", "or",
                                                  "xor", "adc", "sbb", "neg", "not", "shl", "shr",
                                                  "sar", "rcl", "rcr", "stosw", "stosb", "pop")
                rec = (fid, fo, op.size, kind, bool(write))
                if state == "dgroup":
                    ds_refs[disp].append(rec)
                elif state == "cs":
                    cs_refs[disp].append(rec)
            # --- immediate near pointers: `mov r16, imm` immediately pushed
            if (mn == "mov" and len(ops) == 2 and ops[0].type == X.X86_OP_REG and ops[1].type == X.X86_OP_IMM
                    and ops[0].size == 2 and ds_state == "dgroup" and j + 1 < len(insns)):
                nxt = insns[j + 1]
                if nxt.mnemonic == "push" and nxt.operands and nxt.operands[0].type == X.X86_OP_REG \
                        and nxt.operands[0].reg == ops[0].reg:
                    prev_push_ds = j > 0 and insns[j - 1].mnemonic == "push" and insns[j - 1].op_str == "ds"
                    imm_refs[ops[1].imm & 0xFFFF].append((fid, fo, "far" if prev_push_ds else "near"))
    return ds_refs, cs_refs, imm_refs


def lib_code_refs(exe: Exe, lo: int, hi: int):
    """DGROUP displacements in [lo,hi) used by memory operands in the runtime."""
    from capstone import x86_const as X
    md = _capstone()
    out = collections.defaultdict(list)
    end = 0
    for i in md.disasm(exe.b[LIB_CODE_START:0xB510], LIB_CODE_START - exe.hdr):
        end = i.address
        for op in i.operands:
            if op.type == X.X86_OP_MEM and op.mem.base not in (X.X86_REG_BP,) \
                    and op.mem.segment in (0, X.X86_REG_DS, X.X86_REG_SS):
                d = op.mem.disp & 0xFFFF
                if lo <= d < hi:
                    out[d].append(i.address + exe.hdr)
    return out


# ------------------------------------------------------------- strings
STR_RE = re.compile(rb"[\x20-\x7e\r\n\t]{2,}\x00")


def find_strings(data: bytes, lo: int, hi: int, skip):
    out = []
    for m in STR_RE.finditer(data, lo, hi):
        s = m.start()
        if any(a <= s < z for a, z in skip):
            continue
        out.append((s, len(m.group())))
    return out


# --------------------------------------------------- curated annotations
# Every entry is evidence-backed (file offsets are of the cited instruction).
CURATED_GLOBALS = {
    0x009A: ("___brklvl", "verified", "C0S.OBJ PUBDEF ___brklvl @ _DATA+0x9A; every game function's -N prologue does `cmp [0x9a],sp; jb ok; call F_B4FF (stack overflow)`"),
    0x00AA: ("g_demo_mode", "high", "F_09DE (0xB8D) sets 1 after picking a demo from far seg 0x0B31; F_4A27 (0x4A9D) increments it on the 0x30 end-of-demo byte; read by main loop F_0439"),
    0x0118: ("g_level_tile_0118[10] (per-level byte)", "medium", "byte table indexed by g_current_level in F_4E69 (0x4E8D: mov al,[bx+0x118] -> [0x6156]) and F_15A5; values 0x24/0x28; meaning not yet established"),
    0x0122: ("g_level_start_x[10]", "high", "F_4E69 0x4E9C: g_player_x = [0x122 + 2*level]"),
    0x0136: ("g_level_start_y[10]", "high", "F_4E69 0x4EA9: g_player_y = [0x136 + 2*level]"),
    0x016A: ("g_warp_target_level_plus1[10]", "verified", "F_34CB 0x36B4: g_current_level = [0x16a + 2*level] - 1; values (0,0,0,0,2,0,0,6,7,1); external fact EXT_WARP_TARGET_LEVEL_TABLE (file 0x2583A = DS:0x16A)"),
    0x0192: ("g_warp_start_scroll_x[10]", "high", "F_34CB 0x369D/0x36C2: g_scroll_x = [0x192 + 2*level] after warp"),
    0x01A6: ("g_warp_start_x[10]", "high", "F_34CB 0x36AA/0x36C5: g_player_x = [0x1a6 + 2*level] after warp"),
    0x023A: ("g_pickup_tile_ids[10]", "high", "F_3FD5 0x41FE: compared with the tile under Dave; values 2 (door), 4 (jetpack), 0x14 (gun), 0x0A (trophy), 0x2F..0x34 (treasures); each case handled in the switch at 0x40CA"),
    0x024E: ("g_pickup_points[10]", "high", "F_3FD5 0x416D: score += [0x24e + 2*i] (cwd; add [0x4c60]; adc [0x4c62]) parallel to g_pickup_tile_ids"),
    0x034E: ("g_animated_tile_ids[4]", "high", "F_4E69 0x4F76: every tile of the new level is compared against [0x34e + 2*k] for k<4; matches are registered in g_anim_tiles (0x57E8)"),
    0x0356: ("g_animated_tile_frames[4]", "medium", "F_4E69 0x4FB2/0x4FFB: per-kind frame count copied into each g_anim_tiles record"),
    0x0496: ("g_level_monster_init[10][0x50]", "high", "F_4E69 0x504A..0x505A: struct copy (N_SCOPY@ at 0xB1C2, cx=0x50) from DS:0x496 + level*0x50 to g_monsters (DS:0x5742)"),
    0x0F02: ("g_ctrl_panel_state (0x0F02..0x0F12)", "low", "small block used only by F_5B10/F_5DD5 (control panel / input configuration)"),
    0x131A: ("g_old_int9 (far)", "high", "F_6293 0x62ED/0x62F1: old INT 9 vector stored here unless it already equals _TEXT:0x610B (the keyboard ISR); then runtime 0xA44F (setvect-shaped) installs _TEXT:0x610B as INT 9; the `seg _TEXT` immediates are the two value-0 relocations"),
    0x137A: ("g_sound_data (far)", "verified", "F_519B 0x51D3/0x51D9: = MK_FP(0x1C2E,0) -- the relocated paragraph of the SPK sound segment"),
    0x1384: ("g_sound_state (0x1384..0x1392)", "medium", "bytes/words used only by the sound routines F_75D6..F_7719 and play_sound F_763E"),
    0x1394: ("g_rle_src_seg", "verified", "asm RLE codec entry 0x7E00: 0x7E0D ss:[0x1394] = arg2 (source segment); 0x7F1F: mov ds,ss:[0x1394]"),
    0x1396: ("g_rle_dst_seg", "verified", "0x7E1B: ss:[0x1396] = arg4 (destination segment); 0x7EDC: mov es,ss:[0x1396]"),
    0x1398: ("g_rle_src_off", "verified", "0x7E06: ss:[0x1398] = arg1"),
    0x139A: ("g_rle_dst_off", "verified", "0x7E14: ss:[0x139a] = arg3"),
    0x139C: ("g_rle_remaining (long)", "verified", "0x7E22/0x7E29: ss:[0x139c..0x139f] = arg5 (length); decremented per chunk at 0x7F0F"),
    0x13AC: ("g_levels (far)", "verified", "asm stub file 0x8516: mov ax,0x173A; mov [0x13ac],ax; mov ax,DGROUP(reloc lm 0x831D); mov [0x13ae],ax. Only the offset half is read (F_4E69 0x4EF0)"),
    0x143A: ("g_vga_palette[256][3]", "verified", "F_6D64 (set_video_mode) case 3: les dx,MK_FP(DS,0x143A); bx=0; cx=0x100; int 10h ax=1012h (set 256 DAC registers); 768 bytes end exactly at g_levels (DS:0x173A); renders the VGA tileset correctly"),
    0x4C60: ("g_score (long)", "verified", "first _BSS word; F_3FD5 0x4172: add [0x4c60],ax; adc [0x4c62],dx; F_0C34 caps at 99999 (EXT_SCORE_LIVES_LOGIC); F_535A zeroes it"),
    0x4F84: ("g_has_gun", "high", "F_3FD5 0x417F: set to 1 when the tile is 0x14 (gun); also draws the HUD gun icon at (0xF0,0xAA)"),
    0x4F86: ("g_gfx_index (video mode - 1)", "verified", "F_1321 0x13F8: [0x4f86] = [0x8b32] - 1; 139 uses as an index into per-video-mode tables (e.g. 0x336/0x33C)"),
    0x4F88: ("g_got_trophy", "high", "F_3FD5 0x40F9: set to 1 when the tile is 0x0A (trophy); door case 0x415C requires it to finish the level"),
    0x4F8A: ("g_has_jetpack", "high", "F_3FD5 0x41E9: set to 1 when the tile is 4 (jetpack); also sets jetpack fuel 0x5798=0x3C"),
    0x4F8C: ("g_hiscores (near ptr)", "medium", "F_519B 0x51FA: = runtime allocation (lm 0xB0BF) of 0x2D bytes; filled by load-file helper F_6ADE(DS:0xAE = the high-score file name); if that fails a default table is written via F_6B94 (0x5220)"),
    0x56EA: ("g_player_x", "high", "F_4E69 0x4EA0 = g_level_start_x[level]; F_34CB edge tests (<2, >0x132) trigger warps"),
    0x56EC: ("g_player_y", "high", "F_4E69 0x4EAD = g_level_start_y[level]; F_34CB sets 0x10 after a warp (EXT g_start_y)"),
    0x56EE: ("g_lives", "verified", "F_535A sets 3 (EXT_INIT_FUNCTION); F_0C34 increments on extra life"),
    0x56F0: ("g_tileset (far ptr)", "high", "F_519B 0x51C9: = F_6A62(0x16000) (far allocation helper, result in dx:ax); destination of the RLE-unpacked CGA/VGA tileset (F_1321 0x136E) or EGADAVE.DAV"),
    0x56F4: ("g_current_level", "verified", "F_535A sets 0; F_4E69 0x4EE8 level*0x500; F_3BA3 increments and compares with 0xA"),
    0x56F6: ("g_bullets (5 x 14 bytes)", "low", "array of 0x0E-byte records cleared in F_4E69 0x4F26 (5 iterations)"),
    0x573C: ("g_in_warp_zone", "verified", "F_535A clears; F_3BA3 0x3D95: if 1, restore g_current_level from 0x6152 (EXT g_is_warp_zone)"),
    0x5742: ("g_monsters (struct of 10 x int[4])", "high", "destination of the per-level 0x50-byte copy (F_4E69 0x5045); [0x5742+2i] is the active flag tested by F_2D87 0x2D9E"),
    0x575A: ("g_monster_path_pos[4]", "high", "F_2D87 0x2DE1: index into g_level_path; reset to 0 when the path byte is 0xEA (0x2DF7)"),
    0x5792: ("g_game_over", "verified", "F_535A clears; F_15A5 0x1647 / F_3BA3 0x3FC9 set 1 (EXT g_is_game_over)"),
    0x5798: ("g_jetpack_fuel", "medium", "set to 0x3C when the jetpack is collected (F_3FD5 0x41DA)"),
    0x57A0: ("g_scroll_x (tile column of the view)", "high", "range 0..0x50 (=100-20) checked in F_3FD5 0x46C9/0x4765; F_34CB warp trigger at 0 / 0x50"),
    0x57A2: ("g_demo_pos", "high", "F_09DE 0xB8A: = demo offset from seg 0x0B31 table; F_4A27 reads es:[g_demo_data + g_demo_pos] and increments"),
    0x57A4: ("g_demo_data (far ptr)", "verified", "F_519B 0x51E5/0x51EB: = MK_FP(0x0B31,0) (relocated paragraph)"),
    0x57A8: ("g_level (near ptr into g_levels)", "verified", "F_4E69 0x4EF6: = g_levels.off + level*0x500; += 0x100 at 0x511B so it then points at the tile map"),
    0x57AA: ("g_level_visited[10]", "medium", "F_34CB 0x368B: set [0x57aa+2*level]=1 when warping; tested at 0x3513 to suppress a second warp"),
    0x57E8: ("g_anim_tiles[200] (12-byte records)", "high", "cleared for 200 entries in F_4E69 0x4F36; filled for every animated tile found in the level"),
    0x6148: ("g_next_extra_life_score (long)", "verified", "F_535A zeroes; F_0C34 compares/advances (EXT g_next_goal)"),
    0x614C: ("g_level_path (far ptr)", "verified", "F_4E69 0x5114/0x5117: = MK_FP(DS, g_level) before g_level += 0x100; F_2D87 reads path bytes through it and restarts at 0xEA"),
    0x6150: ("g_6150 (per-level counter)", "low", "cleared at level load (F_4E69 0x4ED6); 28 refs"),
    0x6152: ("g_warp_return_level", "verified", "F_34CB 0x3694: = g_current_level before warping; F_3BA3 0x3DA2 restores it (EXT g_curr_warp_zone_mapping)"),
    0x6158: ("g_level_done", "high", "F_4E69 clears; F_3FD5 0x4163 sets 1 at the door when g_got_trophy"),
    0x615A: ("g_anim_tick_divider", "high", "F_535A sets 10; F_332C 0x3339 decrements it and, on reaching 0, reloads 10 (0x3344) and advances every g_anim_tiles record (0x3356..). EXT called it g_maybe_levels_left; usage contradicts that"),
    0x615C: ("g_tiles[1000]", "verified", "working copy of the level's tile map: movmem(g_level, 0x615C, 1000) in F_4E69 0x5121..0x512D (and re-copied in F_34CB/F_3BA3/F_4A27)"),
    0x6544: ("g_demo_repeat", "high", "F_4A27 0x4A86: = count byte after a 0x20 run marker in the demo stream; decremented per frame (0x4AF6)"),
    0x65A8: ("g_pic_planes[4] (segments)", "high", "F_6099 0x611D: [0x65a8+2i] = picfile.seg + plane[i].seg for the shell picfile segments 0x1D58/0x1E84/0x20CC"),
    0x8A16: ("g_pic_charptr (far)", "high", "F_6099 0x60C6: picfile header +0 (font glyphs)"),
    0x8A1A: ("g_pic_spriteptr (far)", "medium", "F_6099 0x60FC: picfile header +0xC"),
    0x8A1E: ("g_pic_picptr (far)", "high", "F_6099 0x60EA: picfile header +8 (the 13 32x24 control-panel pictures)"),
    0x8A2E: ("g_pic_tileptr (far)", "medium", "F_6099 0x60D8: picfile header +4"),
    0x8B32: ("g_video_mode (1=CGA 2=EGA 3=VGA)", "verified", "F_1321 switch: 1 -> unpack seg 0x0C42 + picfile 0x1D58, 2 -> load EGADAVE.DAV + picfile 0x1E84, 3 -> unpack seg 0x11EF + picfile 0x20CC"),
}

PER_LEVEL_TABLE_NOTE = (
    "DS:0x118..0x1CC and DS:0x496..0x7B6 are per-level parameter tables in "
    "initialised _DATA (indexed by g_current_level); see CURATED_GLOBALS.")


# --------------------------------------------------------------- analysis
def build(exe_path: pathlib.Path):
    data = exe_path.read_bytes()
    exe = Exe(data)
    st = analyse_startup(exe)
    dg = st["dgroup"]
    ds_file = exe.seg_file(dg)
    file_end = len(data)
    data_end_ds = file_end - ds_file
    assert data_end_ds == st["bdata"], "initialised _DATA must end exactly where C0S starts clearing _BSS"

    census = json.loads(CENSUS.read_text())
    starts = sorted(f["start"] for f in census["functions"])

    def func_of(fo):
        best = None
        for s in starts:
            if s <= fo:
                best = s
            else:
                break
        return None if best is None else "F_%04X" % best

    # ---------------- relocations -> segment values
    seg_values = collections.defaultdict(list)
    for r in exe.relocs:
        seg_values[r["value"]].append(r)
    reloc_out = [{"load_module": hx(r["load_module"]), "file": hx(r["file"]),
                  "value": hx(r["value"]), "in_function": func_of(r["file"])}
                 for r in exe.relocs]

    far_paras = sorted(v for v in seg_values if 0 < v < dg and v != dg - 1)
    init_para = dg - 1
    assert init_para in seg_values and any(w["segment"] == init_para for w in st["init_walks"])
    bounds = far_paras + [init_para, dg]

    # ---------------- end of _TEXT
    first_far = exe.seg_file(far_paras[0])
    text_end = first_far
    while data[text_end - 1] == 0:
        text_end -= 1
    segments = [{
        "name": "_TEXT", "class": "CODE", "paragraph": "0x0000",
        "file_start": hx(exe.hdr), "file_end": hx(first_far), "size": first_far - exe.hdr,
        "data_end": hx(text_end), "padding": {"file_start": hx(text_end), "file_end": hx(first_far),
                                               "bytes": first_far - text_end, "all_zero": True},
        "content": "game code 0x439..0x9613 (after C0S 0x200..0x439), Borland CS.LIB runtime 0x9613..data_end",
        "status": "verified",
        "evidence": [
            "segment value 0x0000 is the relocated target of the two `seg _TEXT` immediates at load-module 0x60DC/0x60F5 (keyboard-ISR far pointer _TEXT:0x610B in F_6293)",
            "last non-zero byte belongs to the runtime's stack-overflow stub (`Stack overflow!` message + int 21h/ah=9 + jmp) at file 0xB4ED..0x%X; followed by %d zero bytes of paragraph alignment before the first FAR_DATA segment" % (text_end, first_far - text_end),
        ],
    }]

    # ---------------- far data segments
    def ref_sites(para):
        return [{"file": hx(r["file"]), "load_module": hx(r["load_module"]),
                 "in_function": func_of(r["file"])} for r in seg_values[para]]

    for idx, para in enumerate(far_paras):
        fs = exe.seg_file(para)
        fe = exe.seg_file(bounds[idx + 1])
        seg = {"name": "FAR_%04X" % para, "class": "FAR_DATA (hypothesis: class name from C0S segment order)",
               "paragraph": hx(para), "file_start": hx(fs), "file_end": hx(fe), "size": fe - fs,
               "referenced_from": ref_sites(para)}
        blob = data[fs:fe]
        if para == far_paras[0]:
            cnt = exe.d(fs)
            offs = list(struct.unpack_from("<%dI" % cnt, data, fs + 4))
            assert offs[0] == 4 + 4 * cnt
            demos = []
            for k, o in enumerate(offs):
                e = offs[k + 1] if k + 1 < cnt else None
                demos.append({"offset": hx(o), "start_level_index": blob[o]})
            last = len(blob.rstrip(b"\0"))
            seg.update({"content": "attract-mode demo recordings (recorded input streams)",
                        "status": "verified",
                        "data_end": hx(fs + last),
                        "format": {"count_u32": cnt, "offsets_u32": [hx(o) for o in offs],
                                   "record": "byte 0 = level index to load; then input bytes: low nibble = direction 0..7 (8 = none), bit 7 / bit 6 = buttons; 0x20 n = repeat previous input n frames; 0x30 = end of demo"},
                        "demos": demos,
                        "evidence": [
                            "F_519B 0x51E5: g_demo_data (DS:0x57A4) = MK_FP(0x%04X,0) via relocated immediate at lm 0x4FEF" % para,
                            "F_09DE 0xB63..0xB9F: idx = rand() %% es:[0]; g_demo_pos = es:[4+4*idx]; g_current_level = es:[g_demo_pos++]; g_demo_mode = 1",
                            "F_4A27 0x4A69..0x4AF0: 0x20 -> g_demo_repeat = next byte; 0x30 -> end of demo; else dir = b&0xF, button bits from b>>7 and b>>6",
                        ],
                        "padding": {"file_start": hx(fs + last), "file_end": hx(fe), "bytes": len(blob) - last, "all_zero": True}})
        elif blob[:4] == b"SPK\0":
            total = exe.d(fs + 4)
            names = 0
            unused = 0
            for k in range(63):
                ent = blob[16 + 16 * k: 32 + 16 * k]
                nm = ent[4:].split(b"\0")[0]
                if nm == b"->UNUSED<-":
                    unused += 1
                elif nm:
                    names += 1
            seg.update({"content": "PC-speaker sound effects, id/Softdisk 'SPK' format",
                        "status": "verified",
                        "data_end": hx(fs + total),
                        "format": {"magic": "SPK\\0", "total_length_u32": total,
                                   "directory": "63 x 16-byte entries at +0x10: u16 data offset, u8 priority, u8 rate/divider, char name[12]",
                                   "named_sounds": names, "unused_slots": unused,
                                   "sound_data": "u16 PIT divisors from +0x400, each sound terminated by 0xFFFF"},
                        "evidence": [
                            "F_519B 0x51D3/0x51D9: g_sound_data (DS:0x137A) = MK_FP(0x%04X,0) via relocated immediate at lm 0x4FDD" % para,
                            "u32 at +4 (%d) + %d zero bytes == segment size %d (paragraph alignment)" % (total, len(blob) - total, len(blob)),
                            "play_sound F_763E is called with 1-based ids that line up with the directory (e.g. 7 on the trophy, 12 on gun/jetpack in F_3FD5)",
                        ],
                        "padding": {"file_start": hx(fs + total), "file_end": hx(fe), "bytes": len(blob) - total,
                                    "all_zero": not any(blob[total:])}})
        elif exe.w(fs + 0x10) == 0x0008 and exe.w(fs + 0x12) == 0x0002:
            # picfile header: far ptrs charptr/tileptr/picptr/spriteptr, pictable, spritetable, plane[4]
            ptrs = [(exe.w(fs + 4 * k), exe.w(fs + 4 * k + 2)) for k in range(4)]
            planes = [exe.w(fs + 0x1A + 4 * k) for k in range(4)]
            pics = []
            a = 0x28
            while a + 16 <= 0x100 and blob[a + 8:a + 16] != b"*" * 8:
                w_, h_ = struct.unpack_from("<HH", blob, a)
                pics.append({"width_bytes": w_, "height": h_, "offset": hx(exe.d(fs + a + 4))})
                a += 16
            is_ega = ptrs[0][1] >= 0xA000
            mode = {0x1D58: "CGA", 0x1E84: "EGA", 0x20CC: "VGA"}.get(para, "?")
            seg.update({"content": "shell picfile (%s): 8x8 font (128 chars) + %d control-panel pictures 32x24; header 0x100 bytes" % (mode, len(pics)),
                        "status": "verified",
                        "data_end": hx(fe),
                        "format": {"header_far_ptrs": {"charptr": "%04X:%04X" % ptrs[0][::-1],
                                                       "tileptr": "%04X:%04X" % ptrs[1][::-1],
                                                       "picptr": "%04X:%04X" % ptrs[2][::-1],
                                                       "spriteptr": "%04X:%04X" % ptrs[3][::-1]},
                                   "pointer_base": "EGA video memory (latched planes)" if is_ega else "segment-relative paragraphs (added to the segment in F_6099)",
                                   "pictable": "+0x28, %d x 16 bytes {u16 width_bytes, u16 height, u32 offset, char name[8]}; rest of header filled with '*'" % len(pics),
                                   "plane_paragraphs": [hx(p) for p in planes],
                                   "pictures": pics},
                        "evidence": [
                            "F_1321 (switch on g_video_mode at 0x1330) passes MK_FP(0x%04X,0) to F_6099 via relocated immediate" % para,
                            "F_6099 0x60B5: for g_video_mode==2 the header far pointers are used as-is (A200:0, A240:0, A28E:0 = EGA VRAM); otherwise segment+header word (0x5F29..)",
                            "last plane paragraph + plane size == segment size exactly (no padding)",
                        ],
                        "padding": None})
        else:
            # RLE-compressed tileset
            length = exe.d(fs)
            out, used = unrle(blob[4:], length)
            cnt = struct.unpack_from("<I", out, 0)[0]
            offs = struct.unpack_from("<%dI" % cnt, out, 4)
            sizes = [(offs[k + 1] if k + 1 < cnt else length) - offs[k] for k in range(cnt)]
            fixed = 0
            while fixed < cnt and sizes[fixed] == sizes[0]:
                fixed += 1
            mode = {0x0C42: "CGA", 0x11EF: "VGA"}.get(para, "?")
            stream_end = fs + 4 + used
            tail = blob[4 + used:]
            nz = len(tail.rstrip(b"\0"))
            seg.update({"content": "RLE-compressed %s tileset (the in-EXE counterpart of EGADAVE.DAV)" % mode,
                        "status": "verified",
                        "data_end": hx(stream_end),
                        "format": {"unpacked_length_u32": length,
                                   "rle": "b>=0x80: copy b-0x7F literal bytes; b<0x80: repeat next byte b+3 times",
                                   "compressed_bytes_consumed": used,
                                   "unpacked_overshoot": len(out) - length,
                                   "unpacked": {"count_u32": cnt, "offset_table_end": hx(4 + 4 * cnt),
                                                "fixed_tiles": fixed, "fixed_tile_bytes": sizes[0],
                                                "unpacked_md5": hashlib.md5(out[:length]).hexdigest()}},
                        "evidence": [
                            "F_1321 0x1356..0x1382 (%s case): far ptr MK_FP(0x%04X,0) (relocated immediate); unrle(dst=g_tileset, src=+4, len=u32 at +0) via 0x7E00 -> 0x7ED4" % (mode, para),
                            "decoding with the 0x7ED4 algorithm yields a count + strictly increasing offset table whose first offset == 4 + 4*count, and %d leading %d-byte tiles (16x16 at %s depth), matching EGADAVE.DAV's 53 fixed tiles" % (fixed, sizes[0], "2bpp" if sizes[0] == 64 else "8bpp"),
                        ],
                        "padding": {"file_start": hx(stream_end), "file_end": hx(fe), "bytes": fe - stream_end,
                                    "unread_nonzero_bytes": nz,
                                    "note": "bytes after the RLE stream are never read by the decoder; %d non-zero leftover byte(s) then zero alignment" % nz}})
        segments.append(seg)

    # ---------------- _INIT_ segment
    fs = exe.seg_file(init_para)
    walk = [w_ for w_ in st["init_walks"] if w_["segment"] == init_para]
    init_end = max(w_["di"] for w_ in walk)
    entries = []
    for a in range(0, init_end, 6):
        ct, pr, off, segw = struct.unpack_from("<BBHH", data, fs + a)
        entries.append({"calltype": "near" if ct == 0 else "far", "priority": pr,
                        "target_file": hx(off + exe.hdr) if ct == 0 else None})
    segments.append({"name": "_INIT_/_EXIT_", "class": "INITDATA/EXITDATA", "paragraph": hx(init_para),
                     "file_start": hx(fs), "file_end": hx(ds_file), "size": ds_file - fs,
                     "data_end": hx(fs + init_end),
                     "content": "Borland startup/exit routine tables: _INIT_ = %d x 6-byte records, _EXIT_ empty" % len(entries),
                     "init_records": entries,
                     "status": "verified",
                     "evidence": ["C0S at file %s: mov ax,0x%04X; mov ds,ax; mov si,0x%X; mov di,0x%X; call (startup walk) and again with si=di=0x%X (exit walk); relocations at lm 0xDE/0x110" % (hx(walk[0]["file"]), init_para, walk[0]["si"], walk[0]["di"], walk[-1]["si"]),
                                  "records point at runtime init code: priority 2 -> setupio-style stdio init at file 0x9C6F (tests __streams flags at DS:0x4A4A), priority 16 -> __setenvp__ at file 0xB49B (stores _environ DS:0x4C5E)"],
                     "padding": {"file_start": hx(fs + init_end), "file_end": hx(ds_file), "bytes": ds_file - fs - init_end,
                                 "all_zero": not any(data[fs + init_end:ds_file])}})

    # ---------------- DGROUP
    stack_start = (st["edata"] + 15) & ~15
    mem_top = data_end_ds + exe.e_minalloc * 16
    stack_size = mem_top - stack_start
    dgroup = {"paragraph": hx(dg), "file_base": hx(ds_file),
              "evidence": ["entry point (file %s) `mov dx,0x%04X` is relocated (lm 0x0001); C0S stores it in DGROUP@ (cs:[0x235]) and loads DS from it" % (hx(st["entry_file"]), dg)],
              "subsegments": []}

    tc = load_toolchain()
    c0s_publics = []
    lib_modules = []
    c0s_len = None
    if tc:
        c0, mods = tc
        c0s_len = c0.segment_lengths["_DATA"]
        pat, ln, _ = masked_pattern(c0, "_DATA")
        assert pat.fullmatch(data[ds_file:ds_file + ln]), "C0S _DATA must sit at DS:0"
        c0s_publics = [{"ds_offset": hx(p["offset"]), "name": p["name"]} for p in c0.publics_in("_DATA")]
        assert c0.segment_lengths["_STACK"] == stack_size, "C0S _STACK length == minalloc remainder"
        for m in mods:
            dl = m.segment_lengths.get("_DATA", 0)
            if dl < 4:
                continue
            pat, ln, known = masked_pattern(m, "_DATA")
            if known < 8:
                continue
            hits = [mm.start() for mm in pat.finditer(data, ds_file, ds_file + data_end_ds)]
            if len(hits) == 1:
                lib_modules.append({"module": m.name, "ds_offset": hx(hits[0] - ds_file), "size": dl,
                                    "publics": [{"name": p["name"], "ds_offset": hx(hits[0] - ds_file + p["offset"])}
                                                for p in m.publics_in("_DATA")]})
        lib_modules.sort(key=lambda x: int(x["ds_offset"], 16))
    else:
        c0s_len = 0xA8

    lib_refs_data = lib_code_refs(exe, 0, data_end_ds)
    lib_refs_bss = lib_code_refs(exe, st["bdata"], st["edata"])

    ds_refs, cs_refs, imm_refs = scan_game_code(exe, dg, starts)
    game_refd = sorted(d for d in ds_refs if c0s_len <= d < st["edata"])
    levels_ds, levels_fo, stub = levels_mod.find_levels_base(data)
    levels_end = levels_ds + levels_mod.NUM_LEVELS * levels_mod.RECORD_SIZE
    lib_data_start = min(d for d in lib_refs_data if d >= c0s_len and d >= levels_end)
    assert lib_data_start == levels_end, "library _DATA begins right after g_levels"
    lib_bss_start = min(d for d in lib_refs_bss)
    assert max(d for d in game_refd) < lib_bss_start

    sub = dgroup["subsegments"]
    sub.append({"name": "_DATA (C0S)", "ds_start": "0x0", "ds_end": hx(c0s_len),
                "file_start": hx(ds_file), "file_end": hx(ds_file + c0s_len),
                "status": "verified" if tc else "hypothesis",
                "evidence": "C0S.OBJ _DATA length %d matches the file bytes at DS:0 (null-check area + copyright + runtime messages + startup variables)" % c0s_len})
    sub.append({"name": "_DATA (game modules)", "ds_start": hx(c0s_len), "ds_end": hx(levels_end),
                "file_start": hx(ds_file + c0s_len), "file_end": hx(ds_file + levels_end),
                "status": "verified",
                "evidence": "between C0S's _DATA and the first CS.LIB module's _DATA; ends with g_levels (DS:%s..%s)" % (hx(levels_ds), hx(levels_end))})
    sub.append({"name": "_DATA (CS.LIB modules)", "ds_start": hx(levels_end), "ds_end": hx(data_end_ds),
                "file_start": hx(ds_file + levels_end), "file_end": hx(file_end),
                "status": "verified",
                "evidence": "first library-code DS reference in _DATA is __atexitcnt at %s (LIB_ATEXIT 0x9616: cmp [0x493a],0x20); unique byte matches of CS.LIB modules listed in library_data_modules" % hx(lib_data_start)})
    sub.append({"name": "_BSS (game modules)", "ds_start": hx(st["bdata"]), "ds_end": hx(lib_bss_start),
                "file_start": None, "file_end": None, "status": "verified",
                "evidence": "C0S clears [bdata=%s, edata=%s) at file %s; highest game-code reference %s" % (hx(st["bdata"]), hx(st["edata"]), hx(st["bss_clear_site"]), hx(max(game_refd)))})
    sub.append({"name": "_BSS (CS.LIB modules)", "ds_start": hx(lib_bss_start), "ds_end": hx(st["edata"]),
                "file_start": None, "file_end": None, "status": "verified",
                "evidence": "__atexittbl referenced as [bx-0x6138] (= DS:0x9EC8) by LIB_ATEXIT; putc's 1-byte buffer at DS:0x9F08"})
    sub.append({"name": "_STACK (C0S)", "ds_start": hx(stack_start), "ds_end": hx(mem_top),
                "file_start": None, "file_end": None, "status": "verified" if tc else "hypothesis",
                "evidence": "align16(edata) + C0S.OBJ _STACK length 0x%X == DS:%s == initialised size + e_minalloc*16 (0x%X paragraphs). At run time C0S moves SP to edata + _stklen (DS:%s, = 0x%X)" % (stack_size, hx(mem_top), exe.e_minalloc, hx(st["stklen_ds"]), exe.w(ds_file + st["stklen_ds"]))})
    dgroup["c0s_publics"] = c0s_publics
    dgroup["library_data_modules"] = lib_modules
    dgroup["library_data_refs"] = [{"ds_offset": hx(d), "lib_sites": [hx(x) for x in v[:4]]} for d, v in sorted(lib_refs_data.items()) if d >= levels_end]
    dgroup["library_bss_refs"] = [{"ds_offset": hx(d), "lib_sites": [hx(x) for x in v[:4]]} for d, v in sorted(lib_refs_bss.items())]

    # ---------------- strings (offsets only; no text committed)
    strings = find_strings(data[ds_file:ds_file + data_end_ds], c0s_len, levels_ds, [])
    str_starts = {s: n for s, n in strings}
    for s in list(str_starts):
        str_starts[s] = {"len": str_starts[s], "refs": [r for r in imm_refs.get(s, [])]}
    regions = []
    cur = None
    for s, n in strings:
        if cur and s <= cur["end"] + 2:
            cur["end"] = s + n
            cur["strings"] += 1
            cur["referenced"] += bool(imm_refs.get(s))
        else:
            cur = {"start": s, "end": s + n, "strings": 1, "referenced": int(bool(imm_refs.get(s)))}
            regions.append(cur)
    string_regions = [{"ds_start": hx(r["start"]), "ds_end": hx(r["end"]), "file_start": hx(ds_file + r["start"]),
                       "strings": r["strings"], "code_referenced": r["referenced"]}
                      for r in regions if r["referenced"] and r["end"] - r["start"] >= 4]

    # ---------------- globals table
    def region_of(d):
        if d < c0s_len:
            return "_DATA:C0S"
        if d < levels_ds:
            return "_DATA:game"
        if d < levels_end:
            return "_DATA:g_levels"
        if d < data_end_ds:
            return "_DATA:lib"
        if d < lib_bss_start:
            return "_BSS:game"
        if d < st["edata"]:
            return "_BSS:lib"
        return "beyond_edata"

    c0s_names = {int(p["ds_offset"], 16): p["name"] for p in c0s_publics}
    globals_out = []
    all_ds = sorted(set(ds_refs) | {d for d in CURATED_GLOBALS})
    for d in all_ds:
        if d >= st["edata"]:
            continue
        refs = ds_refs.get(d, [])
        widths = sorted({r[2] for r in refs})
        kinds = sorted({r[3] for r in refs})
        funcs = sorted({r[0] for r in refs})
        g = {"ds_offset": hx(d), "file_offset": hx(ds_file + d) if d < data_end_ds else None,
             "region": region_of(d), "access_widths": widths, "access_kinds": kinds,
             "written": any(r[4] for r in refs), "ref_count": len(refs), "functions": funcs,
             "sites": [hx(r[1]) for r in refs[:6]]}
        if d < data_end_ds and refs:
            wdt = max(widths) if widths else 2
            g["initial_value_hex"] = data[ds_file + d: ds_file + d + wdt].hex()
        if d in imm_refs:
            g["address_taken_at"] = [hx(x[1]) for x in imm_refs[d][:4]]
        if d in CURATED_GLOBALS:
            name, conf, ev = CURATED_GLOBALS[d]
            g.update({"proposed_name": name, "confidence": conf, "evidence": ev})
        elif d in c0s_names:
            g.update({"proposed_name": c0s_names[d], "confidence": "verified", "evidence": "C0S.OBJ PUBDEF"})
        if d in str_starts:
            g["is_string_literal"] = True
        globals_out.append(g)

    # ---------------- g_levels
    lv = levels_mod.decode_levels(data)
    g_levels = {
        "ds_offset": hx(levels_ds), "file_offset": hx(levels_fo), "far_pointer": "%04X:%04X" % (dg, levels_ds),
        "count": levels_mod.NUM_LEVELS, "record_size": levels_mod.RECORD_SIZE,
        "record_layout": [{"offset": "0x000", "size": 256, "what": "monster path: signed (dx,dy) byte pairs, 0xEA in the dx slot ends/restarts the path"},
                          {"offset": "0x100", "size": 1000, "what": "tile map, 10 rows x 100 columns, row-major, EGADAVE.DAV fixed-tile index per byte"},
                          {"offset": "0x4E8", "size": 24, "what": "never read (padding to 0x500); non-zero editor leftovers, preserved"}],
        "init_stub_file": hx(stub),
        "range_file": [hx(levels_fo), hx(levels_fo + levels_mod.NUM_LEVELS * levels_mod.RECORD_SIZE)],
        "per_level": [{"level": d_["level"], "path_moves": len(d_["path"]["moves"]),
                       "path_terminated": d_["path"]["terminator_hex"] is not None,
                       "max_tile": max(max(r) for r in d_["tiles"]),
                       "record_md5": hashlib.md5(levels_mod.encode_record(d_)).hexdigest()} for d_ in lv],
        "warp_bug_level_minus_1": {"ds_offset": hx((levels_ds - levels_mod.RECORD_SIZE) & 0xFFFF),
                                   "file_offset": hx(ds_file + ((levels_ds - levels_mod.RECORD_SIZE) & 0xFFFF)),
                                   "tiles_file_offset": hx(ds_file + ((levels_ds - levels_mod.RECORD_SIZE) & 0xFFFF) + 0x100)},
        "roundtrip_exact": levels_mod.encode_levels(json.loads(json.dumps(lv))) ==
        data[levels_fo:levels_fo + levels_mod.NUM_LEVELS * levels_mod.RECORD_SIZE],
    }

    cs_out = [{"cs_offset": hx(d), "file_offset": hx(d + exe.hdr), "functions": sorted({r[0] for r in v}),
               "ref_count": len(v)} for d, v in sorted(cs_refs.items())]

    return {
        "schema": "dave_recon/data-layout/v1",
        "generator": "tools/data_layout.py",
        "specimen": {"path": "build/DAVE_unpacked.exe", "size": len(data), "md5": hashlib.md5(data).hexdigest()},
        "mz": {"header_size": hx(exe.hdr), "e_minalloc_paragraphs": hx(exe.e_minalloc),
               "e_maxalloc_paragraphs": hx(exe.e_maxalloc), "e_ss": hx(exe.e_ss), "e_sp": hx(exe.e_sp),
               "relocations": reloc_out},
        "startup": {"entry_file": hx(st["entry_file"]), "dgroup": hx(dg), "bdata": hx(st["bdata"]),
                    "edata": hx(st["edata"]), "bss_clear_site": hx(st["bss_clear_site"]),
                    "stklen_ds": hx(st["stklen_ds"]), "stklen_value": hx(exe.w(ds_file + st["stklen_ds"])),
                    "heaplen_ds": hx(st["heaplen_ds"]), "toolchain_objects_used": bool(tc)},
        "segments": segments,
        "dgroup": dgroup,
        "g_levels": g_levels,
        "per_level_tables_note": PER_LEVEL_TABLE_NOTE,
        "string_regions": string_regions,
        "string_count_game_data": len(strings),
        "globals": globals_out,
        "text_resident_data_refs": cs_out,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    result = build(pathlib.Path(a.exe))
    text = json.dumps(result, indent=1) + "\n"
    if a.check:
        old = pathlib.Path(a.out).read_text()
        same = old == text
        print("data-layout.json is", "up to date" if same else "STALE")
        return 0 if same else 1
    pathlib.Path(a.out).write_text(text)
    print("wrote", a.out, "(%d globals, %d segments)" % (len(result["globals"]), len(result["segments"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
