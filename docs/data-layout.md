# DATA architecture of DAVE.EXE

Machine-readable companion: [`data-layout.json`](data-layout.json), regenerated
by `python tools/data_layout.py` (and checked with `--check`). Level data has
its own decoder/encoder, `tools/levels.py`, proven by
`tests/test_levels_roundtrip.py`. Every far data segment has one too (section
5); all of them are STRUCTURED_DATA regions in `layout/manifest.json`. No derived game data (level contents, text,
graphics) is committed; the JSON holds only offsets, sizes, counts and hashes.

Coordinates: **file** = offset in `build/DAVE_unpacked.exe` (MZ header 0x200
bytes); **lm** = load-module offset = file - 0x200; **DS:x** = offset in
DGROUP, whose base is file 0x256D0. Every claim is tagged **[V]** (verified
against bytes or code) or **[H]** (hypothesis).

## 1. Segment map

The MZ relocation table has 27 entries. Every paragraph value they patch is a
segment the program addresses, so segment starts come straight from the
relocated immediates. Ends are the next segment's start. "Data end" is where
meaningful content stops; the rest is alignment padding or unread leftovers.

| Segment (paragraph) | File range | Size | Data end | Content | Status |
|---|---|---|---|---|---|
| `_TEXT` (0x0000) | 0x00200-0x0B510 | 45840 | 0x0B50B | C0S 0x200-0x439, game code 0x439-0x9613, CS.LIB runtime 0x9613-0xB50B; 5 zero bytes of padding | [V] |
| FAR 0x0B31 | 0x0B510-0x0C620 | 4368 | 0x0C616 | Attract-mode **demo recordings**: u32 count = 5, u32 offsets[5], then per demo: start-level byte + recorded input stream; 10 zero bytes of padding | [V] |
| FAR 0x0C42 | 0x0C620-0x120F0 | 23248 | 0x120E5 | **CGA tileset, RLE-compressed**: u32 unpacked length 27818 + RLE stream (23233 bytes, of which the decoder reads 23231). Unpacks to 239 resources, the first 53 being 64-byte 16x16 2bpp tiles | [V] |
| FAR 0x11EF | 0x120F0-0x1C4E0 | 41968 | 0x1C4DD | **VGA tileset, RLE-compressed**: u32 71238 + RLE stream (41961 bytes, of which the decoder reads 41938). Unpacks to 158 resources, the first 53 being 256-byte 16x16 8bpp tiles | [V] |
| FAR 0x1C2E | 0x1C4E0-0x1D780 | 4768 | 0x1D774 | **PC-speaker sounds**, id/Softdisk `SPK\0` format: u32 length 4756, 63 x 16-byte directory (12 named sounds + 51 `->UNUSED<-`), u16 PIT divisor data, 12 zero bytes of padding | [V] |
| FAR 0x1D58 | 0x1D780-0x1EA40 | 4800 | end | **Shell picfile, CGA**: 0x100-byte header, 128-char 8x8 font, 13 control-panel pictures (32x24) | [V] |
| FAR 0x1E84 | 0x1EA40-0x20EC0 | 9344 | end | **Shell picfile, EGA**: same, 4 planes; header pointers aim at EGA VRAM (A200:0...) | [V] |
| FAR 0x20CC | 0x20EC0-0x256C0 | 18432 | end | **Shell picfile, VGA**: same, 8bpp | [V] |
| `_INIT_`/`_EXIT_` (0x254C) | 0x256C0-0x256D0 | 16 | 0x256CC | 2 Borland init records (6 bytes each); `_EXIT_` is empty; 4 zero bytes of padding | [V] |
| DGROUP (0x254D) | 0x256D0-EOF 0x2A330 | 19552 in file | | `_DATA` DS:0-0x4C60 in the file, plus `_BSS`/`_STACK` in memory only | [V] |

How the segments were identified:

- **0x0B31 demos.** In F_519B at 0x51E5, `g_demo_data` (DS:0x57A4) is set
  to `MK_FP(0x0B31,0)`. In F_09DE at 0xB63..0xB9F the code picks
  `rand() % es:[0]`, sets `g_demo_pos = es:[4+4*i]` and
  `g_current_level = es:[g_demo_pos++]`, then sets `g_demo_mode` (DS:0xAA) = 1.
  F_4A27 (0x4A69..0x4AF0) decodes the input stream byte by byte:
  - `0x20 n`: the next n frames get no input (direction 8, no buttons).
  - `0x30` ends the demo.
  - Any other byte: the low nibble is a direction (0-7, 8 = none), and bits 7
    and 6 are the buttons.

  All 5 demos end in `0x30 xx`. **[V]**
- **0x0C42 / 0x11EF tilesets.** In F_1321, a switch on `g_video_mode`
  (DS:0x8B32) chooses what to load:
  - Case 1 (CGA) and case 3 (VGA): call the asm routine at 0x7E00 as
    `unrle(src = SEG:4, dst = g_tileset, len = u32 at SEG:0)`.
  - Case 2 (EGA): load `EGADAVE.DAV` (DS:0xD5E) instead.

  The decoder at 0x7ED4 works like this:
  - A byte `b >= 0x80` copies `b-0x7F` literal bytes.
  - A byte `b < 0x80` repeats the next byte `b+3` times.

  `tools/data_layout.py` reimplements it. Its output has the same
  count + offset-table shape as EGADAVE.DAV (`offsets[0] == 4+4*count`) and
  53 leading fixed tiles. Rendering them (with the VGA palette at DS:0x143A)
  gives the recognisable game tiles: door, jetpack, trophy, gun, gems.
  Some bytes after each stream are never read: CGA has 2 non-zero bytes then
  zeros, and VGA has 23 non-zero bytes. They are the last chunks the game's
  own encoder (0x7F41) emitted after reading past the end of its source
  buffer; see section 5.3. **[V]**
- **0x1C2E sounds.** In F_519B at 0x51D3, `g_sound_data` (DS:0x137A) is set
  to `MK_FP(0x1C2E,0)`. The `SPK\0` magic, the u32 length 4756, and 12 zero
  bytes of padding together add up exactly to the 4768-byte segment.
  play_sound (F_763E) takes 1-based ids that line up with the directory: id 7
  is played for the trophy, which is the 7th entry. **[V]**
- **0x1D58/0x1E84/0x20CC picfiles.** F_1321 passes `MK_FP(seg,0)` to F_6099,
  which reads the header as follows:
  - Four far pointers at +0/+4/+8/+0xC are stored to DS:0x8A16/0x8A2E/0x8A1E/0x8A1A.
  - Four plane segments at +0x1A+4i are stored to `g_pic_planes` (DS:0x65A8).
  - For EGA (mode 2) the pointers are used as-is: A200:0 etc., i.e. VRAM.
  - For CGA and VGA, segment + header word gives the address.

  The pictable at +0x28 holds 13 entries of 16 bytes (width, height, offset,
  8-character name). The names are the control-panel icons (video modes,
  sound, input devices); the rest of the header is padded with `*`. Sizes
  check exactly against the segment sizes:
  - CGA: 128 chars x 16 B + 13 x (8 B x 24) = 0x12C0 minus the header. ✓
  - EGA: per plane 0x8E paragraphs = 1024 + 1248. ✓
  - VGA: 8192 + 9984. ✓

  The `*` padding and the field order resemble the picfile header id
  Software used around 1990 **[H]**. The sizes and field roles are **[V]**.
- **0x254C `_INIT_`.** C0S at file 0x2DD/0x30F does `mov ax,0x254C; mov
  ds,ax; mov si,0; mov di,0xC; call walk`, and later walks again with
  `si=di=0xC`. That means 12 bytes of `_INIT_` and an empty `_EXIT_`. The two
  records are near calls:
  - Priority 2 → file 0x9C6F: stdio setup. It tests `__streams[0]` flags
    at DS:0x4A4A.
  - Priority 16 → file 0xB49B: `__setenvp__`. It stores `_environ` at
    DS:0x4C5E.

  C0S.OBJ's own SEGDEF order confirms the placement: `_TEXT, _FARDATA, ...,
  _INIT_, _INITEND_, _EXIT_, _EXITEND_, ..., _DATA, ..., _BSS, _BSSEND,
  _STACK`. That order is why the game's far data sits between `_TEXT` and
  `_INIT_`. **[V]** The class names of the game's far segments were not
  observed directly **[H]**.
- **Value-0 relocations** at lm 0x60DC/0x60F5 are `seg _TEXT` in F_6293, the
  keyboard-ISR install:
  1. It compares the old INT 9 vector with `_TEXT:0x610B`.
  2. It saves the old vector in DS:0x131A.
  3. It installs `_TEXT:0x610B` as the new handler. **[V]**
- The **15 relocations with value 0x254D** inside game code (lm 0x6115 ..
  0x940E; the 16th is C0S's entry at lm 0x0001) are `mov ax,DGROUP` in asm
  modules that later reload DS/ES. One example is the g_levels stub at file
  0x8516. **[V]**

### DGROUP internal layout

| DS range | Part | Evidence |
|---|---|---|
| 0x0000-0x00A8 | `_DATA` of C0S: null-check area, copyright, runtime messages, `__Int0..6Vector`, `__C0argc/argv/environ`, `__envLng/seg/Size`, `__psp`, `__version`, `errno`, `__StartTime`, `___heapbase` 0x98, **`___brklvl` 0x9A** (the `-N` stack-check limit), `__heapbase` 0x9C, `__brklvl` 0xA0, `__heaptop` 0xA4 | C0S.OBJ PUBDEFs and `_DATA` length 168; its bytes match DS:0 with fixups masked **[V]** |
| 0x00A8-0x173A | `_DATA` of the game modules: per-level tables, per-video-mode tables, string literals, asm-module variables, VGA palette | **[V]** |
| 0x173A-0x493A | **g_levels**: 10 records of 0x500 bytes (section 2) | **[V]** |
| 0x493A-0x4C60 | `_DATA` of CS.LIB modules in link order: `__atexitcnt` 0x493A, `_ctype` 0x493C (code indexes it as `[bx+0x493D]`), `__exitbuf/fopen/open` 0x4A3E (C0S calls `[0x4A3E/40/42]`), `__streams` 0x4A46, `__openfd` 0x4B86, `__fmode` 0x4BAE, `__heaplen` 0x4BB2, `rand` seed 0x4BB6, `__stklen` 0x4BBE (= 0x1000), TIMECVT 0x4BC0, `__doserrno` 0x4BCC, TZSET 0x4C28, near-heap `__first/__last/__rover` 0x4C58, `_environ` 0x4C5E | Unique byte matches of CS.LIB modules (CTYPE, FILES, FILES2, TIMECVT, IOERROR, TZSET) plus references from runtime code. The first is `cmp [0x493A],0x20` at 0x9616, right where g_levels ends **[V]** |
| 0x4C60-0x9EC8 | `_BSS` of the game modules; g_score is the first word | C0S zeroes `[0x4C60, 0x9F12)` (file 0x2C4); the file ends exactly at DS:0x4C60; the highest game-code reference is 0x9EC6 **[V]** |
| 0x9EC8-0x9F12 | `_BSS` of CS.LIB: `__atexittbl` (accessed as `[bx-0x6138]`), putc buffer 0x9F08 | **[V]** |
| 0x9F20-0x9FA0 | `_STACK` of C0S (128 bytes) | align16(0x9F12) + 0x80 = 0x9FA0 = 0x4C60 + e_minalloc (0x534) x 16 **[V]** |

The _DATA/_BSS boundary is therefore **DS:0x4C60 = EOF**. **[V]**

## 2. g_levels: resolved

**Answer: `g_levels` = DGROUP:0x173A = file 0x26E0A**: 10 records x 0x500
bytes = file 0x26E0A-0x2A00A. **[V]**

Evidence chain:

1. An asm stub at file 0x8516 contains no prologue and is missing from the
   census. F_519B calls it at 0x51D0. It reads `mov ax,0x173A; mov [0x13AC],ax;
   mov ax,0x254D; mov [0x13AE],ax; ret`. The 0x254D immediate is relocation lm
   0x831D, so it is DGROUP. **[V]**
2. The level loader F_4E69 at 0x4EE8 computes `g_level = [0x13AC] +
   g_current_level*0x500` and stores it in DS:0x57A8. **[V]**
3. Tiles are read as `[g_level + si + 0x100]` for `si < 0x3E8` (0x4F61,
   0x503C). Then `g_level_path = MK_FP(DS, g_level)` (DS:0x614C), `g_level
   += 0x100`, and `movmem(g_level, g_tiles /*DS:0x615C*/, 1000)`. **[V]**
4. F_3FD5 reads collision neighbours at `+1`, `+0x64` and `+0x65`, so the row
   stride is 100. **[V]**
5. F_2D87 restarts a monster path when `path[pos] == 0xEA` (0x2DF7). **[V]**

Record layout, checked against the bytes:

| Offset | Size | Content |
|---|---|---|
| +0x000 | 256 | monster path, signed (dx,dy) pairs, 0xEA terminator. Levels 3-10 all terminate. Levels 1-2 have no monsters: their entries in the per-level monster table DS:0x496 are all zero, so their path bytes are never read. |
| +0x100 | 1000 | 10x100 tile map. Every byte in all 10 levels is ≤ 52, which is exactly EGADAVE.DAV's fixed-tile range 0..52. |
| +0x4E8 | 24 | never read; non-zero leftovers |

The community "256 + 100x10 + 24 = 1280" description is confirmed. **[V]**

**Visual proof.** Run `python tools/levels.py render`, which writes
`build/levels/levelNN.png` using the EGADAVE.DAV tiles. Level 1 renders as
the familiar red-brick start room: trophy top-centre, gems on brick
pillars, start pipe bottom-left, door lower right. A large grey-rock area
lies to its right in columns 20-99, outside the 20-column room. **[V]** by
inspection.

**Why the earlier "contradiction" was itself wrong.** `0x26E0A` was correct.
The previous import concluded otherwise for two reasons:

- **The text bytes are real, but they are level 1's monster path.** The
  bytes at 0x26E0A are high-bit-set ASCII prompt text left over from the
  level editor. Level 1 has no monsters, so the game never reads those 256
  bytes. The tile map starts 0x100 later, at 0x26F0A.
- **The "own math" check used the wrong anchor.** It tested the claimed
  level-6 warp address 0x2932B against base 0x26E0A. Here is what the code
  actually does:
  1. On a warp, F_34CB sets `g_current_level = g_warp_target_level_plus1[5]
     - 1 = -1`.
  2. F_4E69 computes `0x173A + (-1*0x500 mod 0x10000)` = DS:0x123A = **file
     0x2690A**, with tiles at 0x26A0A.
  3. That record overlaps the control-panel strings, the VGA palette and
     other `_DATA`, and it contains tile ids up to 244, which produces the
     glitched level.

  0x2690A is exactly the "plain subtraction" value the earlier import ruled
  out. The 32 bytes at 0x2932B are level 8's tiles (row 2, columns 89-99 and
  beyond). Nothing in the code reads them as the level-6 warp. The external
  project's 0x2932B claim is not reproduced; its g_levels base is.
  **[V]** for our derivation. Why the external author picked 0x2932B is
  unknown **[H]**.

Per-level parameter tables are in `_DATA`, all indexed by `g_current_level`:

| DS | Name | Source |
|---|---|---|
| 0x122 | start x | F_4E69 |
| 0x136 | start y | F_4E69 |
| 0x16A | warp target + 1 | F_34CB |
| 0x192 | warp scroll x | F_34CB |
| 0x1A6 | warp x | F_34CB |
| 0x17E | warp-screen tile | F_34CB, **[H]** |
| 0x118 | per-level byte, meaning unknown | |
| 0x496 | 10 x 0x50-byte monster init block, struct-copied to `g_monsters` (DS:0x5742) | F_4E69 0x504A |

`tools/levels.py` round-trips all 10 records byte-for-byte through a JSON
representation (`decode` / `encode` / `render` / `check` / `info`).

## 3. DGROUP globals

`tools/data_layout.py` sweeps every game function in the census starts
0x439-0x9613. The sweep tracks DS, so asm routines that reload DS (sprite
blitters, the RLE codec, the 0x7C59 `push cs; pop ds` block) are not
mis-attributed; their CS-relative operands go to `text_resident_data_refs`,
which are mostly switch jump tables. The sweep records:

- 282 DGROUP addresses
- access widths and read/write
- referencing functions and sites
- initial values in `_DATA`
- address-taken sites (`mov ax,imm; push ax`)

Breakdown: 131 in game `_DATA`, 149 in game `_BSS`, 1 in C0S `_DATA`
(`___brklvl`, 83 references). Game code references no library `_DATA` or
`_BSS` directly.

Evidence-backed names (full list with evidence in the JSON):

| DS | Name | Conf. | Key evidence |
|---|---|---|---|
| 0x009A | `___brklvl` | V | C0S PUBDEF; every `-N` prologue `cmp [0x9a],sp` |
| 0x00AA | `g_demo_mode` | high | set 1 by F_09DE, incremented at end of demo (F_4A27) |
| 0x0122/0x0136 | `g_level_start_x/y[10]` | high | F_4E69 0x4E9C/0x4EA9 |
| 0x016A | `g_warp_target_level_plus1[10]` | V | F_34CB 0x36B4; values (0,0,0,0,2,0,0,6,7,1) |
| 0x0192/0x01A6 | `g_warp_start_scroll_x/x[10]` | high | F_34CB |
| 0x023A | `g_pickup_tile_ids[10]` | high | F_3FD5 switch: 2 door, 4 jetpack, 0x14 gun, 0xA trophy, 0x2F-0x34 gems |
| 0x024E | `g_pickup_points[10]` | high | added to g_score; trophy 1000, gems 50..500 |
| 0x034E | `g_animated_tile_ids[4]` | high | F_4E69 scans tiles for these |
| 0x0496 | `g_level_monster_init[10][0x50]` | high | N_SCOPY@ to 0x5742 |
| 0x131A | `g_old_int9` | high | F_6293 |
| 0x137A | `g_sound_data` far | V | = 1C2E:0000 |
| 0x1394-0x139F | `g_rle_src_seg/dst_seg/src_off/dst_off/remaining` | V | asm codec 0x7E00 |
| 0x13AC | `g_levels` far | V | stub 0x8516 |
| 0x143A | `g_vga_palette[768]` | V | F_6D64: int 10h/1012h, 256 regs, from DS:0x143A |
| 0x4C60 | `g_score` (long) | V | add/adc pair; first `_BSS` word |
| 0x4F84 | `g_has_gun` | high | tile 0x14 |
| 0x4F86 | `g_gfx_index` (= mode-1) | V | 139 refs as a table index |
| 0x4F88 | `g_got_trophy` | high | tile 0xA; door requires it |
| 0x4F8A | `g_has_jetpack` | high | tile 4 |
| 0x4F8C | `g_hiscores` | medium | 0x2D-byte buffer for the high-score file |
| 0x56EA/0x56EC | `g_player_x/y` | high | set from start tables; warp edge tests |
| 0x56EE | `g_lives` | V | init 3 |
| 0x56F0 | `g_tileset` far | high | F_6A62(0x16000); unrle destination |
| 0x56F4 | `g_current_level` | V | ×0x500 in loader |
| 0x573C | `g_in_warp_zone` | V | |
| 0x5742 | `g_monsters` (10 x int[4]) | high | |
| 0x5792 | `g_game_over` | V | |
| 0x57A0 | `g_scroll_x` | high | 0..0x50 |
| 0x57A2/0x57A4 | `g_demo_pos` / `g_demo_data` far | high/V | |
| 0x57A8 | `g_level` | V | |
| 0x57E8 | `g_anim_tiles[200]` (12 B) | high | |
| 0x6148 | `g_next_extra_life_score` | V | |
| 0x614C | `g_level_path` far | V | |
| 0x6152 | `g_warp_return_level` | V | |
| 0x6158 | `g_level_done` | high | |
| 0x615A | `g_anim_tick_divider` | high | dec/reload 10 in F_332C. The external project named it `g_maybe_levels_left`; usage contradicts that |
| 0x615C | `g_tiles[1000]` | V | movmem target |
| 0x8A16..0x8A30 | picfile pointers | high/medium | F_6099 |
| 0x8B32 | `g_video_mode` | V | 1 CGA / 2 EGA / 3 VGA |

**String-literal regions** contain code-referenced NUL-terminated strings
(`string_regions` in the JSON). They show the TC++ "module variables, then
that module's literals" pattern, which hints at module boundaries:

| DS range | Content |
|---|---|
| 0x0AE | high-score file name |
| 0x7CE-0xF02 | main game module: score digits, level messages, high-score/menu prompts, help pages, `EGADAVE.DAV`, title credits; 63 strings, 62 referenced |
| 0xF63-0x12EF | control-panel / input-configuration module; 57 strings |
| 0x131E | out-of-memory message |
| 0x13B0 | `$`-terminated DOS string of the EGA tileset loader |

The text itself is not committed.

## 4. Structured representations

- `tools/levels.py`: decodes and encodes the level array with an exact round
  trip, and renders PNGs. It derives the base from code: the C0S DGROUP
  immediate and the relocated g_levels init stub.
- `tools/data_layout.py` contains reference implementations of the RLE
  decompressor, the demo directory parser, the SPK directory parser and the
  picfile header parser (used for this document's evidence only).
- The far data segments have exact codecs, registered as generators in
  `tools/structured.py` and listed in section 5.

## 5. Far data segment formats (STRUCTURED_DATA)

All seven far segments are owned by codecs. Each region spans a whole
segment, from its paragraph to the next relocated paragraph, so alignment
padding is included. `tools/far_data.py` derives the extents from the MZ
relocation table: the far segments are the relocated values between 0 and
`_INIT_`, and `_INIT_` is the segment C0S walks. Each codec decodes to
`build/<name>/`, which is never committed, and encodes back to the exact
bytes. Run `python tools/structured.py check` to compare every generator
with the original image.

| Region | File range | Bytes | Codec | Representation | Test |
|---|---|---|---|---|---|
| `DATA_DEMOS` | 0x0B510-0x0C620 | 4368 | `tools/demos.py` | `build/demos/demos.json` | `tests/test_demos_roundtrip.py` |
| `DATA_TILESET_CGA` | 0x0C620-0x120F0 | 23248 | `tools/tilesets.py` + `tools/rle.py` | `build/tileset_cga/tileset.json` + 239 PNGs | `tests/test_tilesets_roundtrip.py` |
| `DATA_TILESET_VGA` | 0x120F0-0x1C4E0 | 41968 | same | `build/tileset_vga/tileset.json` + 158 PNGs | same |
| `DATA_SOUNDS` | 0x1C4E0-0x1D780 | 4768 | `tools/sounds.py` | `build/sounds/sounds.json` | `tests/test_sounds_roundtrip.py` |
| `DATA_PICFILE_CGA` | 0x1D780-0x1EA40 | 4800 | `tools/picfiles.py` | `build/picfile_cga/picfile.json` + font.png + 13 icon PNGs | `tests/test_picfiles_roundtrip.py` |
| `DATA_PICFILE_EGA` | 0x1EA40-0x20EC0 | 9344 | same | `build/picfile_ega/...` | same |
| `DATA_PICFILE_VGA` | 0x20EC0-0x256C0 | 18432 | same | `build/picfile_vga/...` | same |

Together these are 106,928 bytes, the whole former `RAW_B510_256C0`. In
every PNG the pixel values are the stored colour indices, so the attached
palette does not affect the bytes. The palettes are:

- CGA: palette 1, high intensity.
- EGA: the standard 16 colours; index = I<<3|R<<2|G<<1|B.
- VGA: the game's `g_vga_palette`, DS:0x143A.

### 5.1 Demos (0x0B31)

```
+0          u32  count (5)
+4          u32  offsets[count]   from the segment start; offsets[0] = 4+4*count; contiguous
offsets[i]  u8   start level index (0-based g_current_level): 2, 1, 3, 8, 4
            ...  input stream, terminated by 0x30
            ...  bytes after 0x30 up to the next demo: never read
                 (F_4A27 does not advance g_demo_pos on 0x30); one byte each
                 here (01 01 01 07 01), kept as `unread_after_end_hex`
then             zero padding (10 bytes)
```

Each stream byte is read by F_4A27 as one of three things:

- `0x20 n`: the idle counter DS:0x6544 = n. The following n frames get
  direction 8 and no buttons. The frame that reads the opcode keeps the
  live input.
- `0x30`: the end of the demo (`g_demo_mode++`).
- Any other byte: one frame of input. The low nibble is the direction, bit 7
  is button 1 and bit 6 is button 2. Bits 4-5 are never set; such a byte
  would be kept as `raw:0xHH`.

The direction codes come from the keyboard reader F_63AF. It computes
`3*dy + dx + 4` and looks the result up in its jump table at file 0x64F3:
0 N, 1 NE, 2 E, 3 SE, 4 S, 5 SW, 6 W, 7 NW, 8 none. **[V]** The buttons are
the keys whose scan codes are stored at DS:0x1318 (default 0x1D, Ctrl) and
DS:0x1319 (default 0x38, Alt). **[V]**

The JSON writes each demo as a list of events: `"E x15"`, `"NE+ctrl x19"`,
`"none+alt x9"`, `"idle 16"`. A run of identical input bytes becomes one
event, and the encoder writes one byte per frame, so the round trip is exact.
The demos never use 0x20 for held input. Repeated input is written out byte
by byte.

### 5.2 Sounds (0x1C2E), `SPK\0`

```
+0x000  char[4]  "SPK\0"
+0x004  u32      bank length 4756 (= end of the last sound's data)
+0x008  8 bytes  reserved, zero
+0x010  63 x { u16 offset; u8 priority; u8 rate; char name[12]; }   sound ids 1..63
+0x400  sound data in directory order, contiguous: u16 values, each sound ends with 0xFFFF
then    zero padding (12 bytes)
```

play_sound F_763E reads an entry as `id*16` with a 1-based id. The fields are
used as follows:

- `priority` (+2): the sound starts only if `priority >=` the priority of the
  sound already playing.
- `offset` (+0): becomes the play pointer, DS:0x1388.
- `rate` (+3): when it is above 1, PIT channel 0 is set to `0x10000/rate`,
  and the old INT 8 is chained every `rate` interrupts. So the sound advances
  `rate` x 18.2 times a second.

The ISR at 0x7719 reads one word per interrupt:

- `0xFFFF` stops the sound.
- `0` turns the speaker off for that tick.
- Any other value is a PIT channel 2 divisor (tone = 1193182/value Hz),
  played only if the sound-enable flag DS:0x137E is set. **[V]**

Twelve sounds are named:

1. HitWall
2. Falling
3. OUCH!
4. Walking
5. Jumping
6. Treasure
7. GotTrophy
8. explosion
9. Flying!
10. NextLevel
11. ToJetpack
12. GotSomethng

The other 51 entries are `->UNUSED<-`, each with one data word. The name
bytes after the NUL are leftovers. They are non-zero only in the unused
entries, and are kept as `name_tail_hex`. The JSON stores, per entry: name,
priority, rate and the divisor list. The encoder recomputes the offsets and
the bank length; the decoder checks both against the original.

### 5.3 RLE codec and the CGA/VGA tilesets (0x0C42, 0x11EF)

**Codec (asm 0x7E00-0x8058, `tools/rle.py`).** The decoder 0x7ED4 has two
control bytes:

- `b >= 0x80`: copy the next `b-0x7F` bytes (1..128).
- `b < 0x80`: repeat the next byte `b+3` times (3..130).

It stops once it has produced `count` bytes. The encoder 0x7F41 is never
called by the game; it was linked in with the decoder. It is ported
instruction for instruction:

- It keeps a run counter, the repeats after a byte's first occurrence. A run
  becomes a run chunk at 3 equal bytes, and the run chunk is flushed at 130.
- Literals are flushed at 126 (`0xFD`). Before a run starts, any pending
  literal is flushed.
- After a maximal run or literal, if the next two bytes equal the current one
  it advances the source pointer without decrementing the count. Call this a
  "skip".
- The loop reads `count + 1` source bytes, plus one more per skip.
- At source offset 0xFF00 it flushes and renormalises seg:off. It resets the
  literal start to offset 0, which emits the current byte a second time.

**Evidence that this encoder produced the data.** Running the port over the
decoded tilesets, with count = the u32 header, reproduces both streams byte
for byte. That includes every run/literal split, the chunks after the
decoder's stop point, and the one renormalisation in VGA. **[V]** Because
the encoder reads past its buffer, two artifacts appear:

- **Over-read bytes.** CGA reads 1 byte past the 27,818-byte tileset (`9A`).
  VGA reads 22 bytes past the 71,238-byte tileset (1 + 21 skips): `83 46 F6
  02 C4 5E F6 26 8B 07 02 10 C9 25 39 76 FC 77 C6 FF 46 F2`, which looks like
  x86 code from the compressing tool **[H]**. They are encoded after the
  point where the decoder stops, so the game never reads them. They are
  stored as `rle.overread_hex`, so these are the "2 / 23 unread bytes"
  mentioned in section 1.
- **VGA duplicate.** The VGA tileset is longer than 0xFF00 bytes. The
  renormalisation re-emits source byte 0xFF00, a zero inside a zero run of
  resource 147. The game's decoded tileset therefore has that byte twice and
  loses the final source byte, which is also 0. In memory, the tail of
  resource 147 and all of resources 148-157 sit one byte later than the
  offset table says. **[V]** The representation keeps the tileset as it was
  before compression, where every offset and size is self-consistent. The
  encoder reproduces the duplication. `rle.duplicated_source_bytes` records
  it; that field is informational, and the encoder ignores it. The source
  pointer's offset part is 0 (`rle.source_offset`). Of offsets 0-15, only 0
  reproduces the stream, so the tool's source buffer was
  paragraph-aligned. **[V]**

**Segment layout:**

```
+0  u32 L (tileset length = encoder count = decoder count)
+4  RLE stream    CGA 23233 bytes, VGA 41961
    zero padding  CGA 11 bytes, VGA 3
```

**Tileset layout.** It is the same container as EGADAVE.DAV:

```
+0          u32 count (CGA 239, VGA 158)
+4          u32 offsets[count]   offsets[0] = 4+4*count, contiguous, last resource ends at L
resource    0..52   fixed 16x16 tiles, no header: CGA 64 bytes (2bpp), VGA 256 bytes (8bpp)
            53..    u16 width, u16 height, pixels:
                    CGA 2bpp: ceil(w/4) bytes x h rows. The CGA blitter at
                        0x8900 reads exactly this ((w+3)>>2 bytes per row, h
                        rows, B800). Each CGA sprite is still allocated
                        ceil(w/8)*2*(h+1) bytes, EGADAVE.DAV's sprite size
                        rule. The remaining bytes (2,713 over 186 sprites) are
                        never read and are kept as `unread_tail_hex`.
                    VGA 8bpp: w bytes x h rows, no tail. The VGA blitter
                        0x8A9A reads the u32 offset and the w/h header.
```

Pixels are MSB-first (CGA: 4 pixels per byte). Each PNG holds the stored
raster, with the width rounded up to whole bytes. Rendering them gives the
expected art:

- tiles
- Dave's animation frames, with separate mask sprites
- monsters
- the status-bar words
- the "Dangerous Dave" title frames
- the digits 0-9

### 5.4 Config-screen picfiles (0x1D58 CGA, 0x1E84 EGA, 0x20CC VGA)

```
+0x00  far charptr, tileptr, picptr, spriteptr   -> DS:0x8A16/0x8A2E/0x8A1E/0x8A1A
                                                    EGA: A200:0000, A240, A240, A28E (VRAM, used as-is)
                                                    CGA/VGA: paragraph-relative, segment added by F_6099
+0x10  far pictable    0002:0008 = +0x28   (F_6099 copies 64 x 16 bytes to DS:0x8604)
+0x14  far spritetable 000F:0008 = +0xF8   (32 x 32 bytes to DS:0x65FC; no sprites)
+0x18  far planes[4]   paragraph-relative -> g_pic_planes DS:0x65A8
                       CGA 0010,012C,0248,0364  EGA 0010,009E,012C,01BA  VGA 0010,0480,08F0,0D60
+0x28  13 x { u16 width_bytes (per plane); u16 height; u32 offset (from picptr); char name[8]; }
       name = NUL-terminated, '-' filled, last byte NUL (e.g. "CGA\0---\0", "nomouse\0")
+0xF8  "********"
+0x100 per plane: 128 font chars (8x8), then the 13 pictures (32x24) in table order
```

The sizes check exactly:

- **Bytes per plane** = spriteptr - charptr: CGA 4544, EGA 2272, VGA 18176.
- **Planes in the file:** EGA has 4. CGA and VGA have 1; their
  `planes[1..3]` point past the segment end, written as if the bank had 4
  planes.
- **Pixel formats:**
  - CGA: 2bpp packed (font 16 bytes per char, icons 8 bytes x 24).
  - EGA: one bit per plane; plane p is bit p of the colour index (font 8
    bytes per char per plane, icons 4 x 24 per plane).
  - VGA: 8bpp (font 64 bytes per char, icons 32 x 24).
- **Icons:** CGA, EGA, VGA, noEGA, noVGA, nosound, SPKR, kbd, joy1, joy2,
  mouse, nojoy, nomouse.

All three render correctly. The JSON stores every header field by name,
including the far pointers as `SSSS:OOOO`. The encoder rebuilds the header
from those fields and checks them against the content sizes. The decoder
checks that the pictures are contiguous and fill each plane up to spriteptr.

## Open questions

- Whether the VGA game visibly suffers from the duplicated byte at decoded
  0xFF00 (section 5.3): resources 148-157 (the 8x11 digits) have their
  headers misread in memory. Which code draws them in VGA mode was not
  traced. **[H]**
- What the leftover bytes are: the CGA sprite tails, the RLE over-read bytes,
  the bytes after each demo's 0x30, the sound name tails. They are kept
  verbatim; their origin is not explained.
- What `DS:0x118` (per-level byte copied to DS:0x6156, 102 refs) and
  `DS:0x6150` mean.
- The individual fields of `g_monsters` beyond active (0x5742) and path
  position (0x575A).
- Linker class names of the 7 far segments (FAR_DATA is inferred from C0S
  segment order, not observed).
- The source of the external project's 0x2932B "level 6 warp" bytes.
- Several asm entry points used here are not in the function census: the
  g_levels stub at 0x8516 and the RLE entry at 0x7E00/0x7ED4. The supervisor
  may want to add them.
- `tools/setup_toolchain.py` fails with `KeyError: 'libraries'` against the
  current `layout/toolchain.json`. For this work, C0S.OBJ and CS.LIB were
  copied into `toolchain/LIB` by hand.
