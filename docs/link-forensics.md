# Link forensics (Level C: emergent layout)

How the original link produced the executable's layout, and how much of it
our sources now reproduce by themselves. Every claim is tagged **V**
(verified against bytes/experiment) or **H** (hypothesis).

## Result in one paragraph

**V** TLINK 3.0 linking C0S + the three C units (`src/DAVE.C`,
`src/CONFIG.C`, `src/HARDWARE.C`, compiled) + the two assembly modules
(`src/asm/lowlevel.asm`, `tiles.asm`, assembled) + two stand-in objects
built from the original bytes (the data-only module and the seven far data
blobs, `tools/omf_writer.py`) + CS.LIB produces a load module **identical
to the original, all 172,336 bytes**, with the same 27 relocations, load
size, minalloc/maxalloc, SS:SP and CS:IP (`python tools/link_probe.py`,
`tests/test_link_probe.py`). No address is given to the linker: every
function, variable, string, pad byte and segment lands where it is because of
the composition of the objects and TLINK's rules. (The MZ header's own
layout differs -- the unpacked specimen's header is the unpacker's
reconstruction -- which does not matter: LZEXE packs the load module.)

## Linker and segment order

- **V** Segment order (C0S's SEGDEFs + TLINK's class grouping): `_TEXT`,
  `FAR_DATA`-class segments, `_OVERLAY_`, `_INIT_`, `_INITEND_`, `_EXIT_`,
  `_EXITEND_`, `_1STUB_`, then DGROUP: `_DATA`, `_CVTSEG`, `_SCNSEG`, `_BSS`,
  `_BSSEND`, `_STACK`. Within a class, segments follow link order.
- **V** The far data blobs are `FAR_DATA` class, paragraph aligned: stand-ins
  with exactly those attributes land on the original paragraphs 0x0B31,
  0x0C42, 0x11EF, 0x1C2E, 0x1D58, 0x1E84, 0x20CC, and the zero bytes between
  them are TLINK's paragraph padding. TCC itself emits a far variable as
  segment `<FILE><n>_FAR`, class FAR_DATA, para, public (observed:
  `S00015_FAR`). Whether the blobs came from a C file or a bin-to-OBJ tool
  is not decidable from the bytes (**H**: a MAKEOBJ-style converter -- each
  blob is a raw file image: count/length header + payload).
- **V** Library modules follow in CS.LIB member order (docs/library-map.md).
- **V** `SS:SP = 0x2F3F:0x0080` and minalloc 0x534 come out of TLINK
  unchanged: `_STACK` (128 bytes) after `_BSSEND`.

## Translation units

**V** (bytes): three C units, each ONE object whose `_TEXT`, `_DATA` and
`_BSS` are contiguous in the image, in the same order in all three classes:

| unit | functions | cs | `_DATA` (DS) | `_BSS` (DS) |
|---|---|---|---|---|
| `DAVE.C` | 53: `main` .. `init_game_state` | 0x0239-0x51C3 | 0x00A8-0x0F02 | 0x4C60-0x654C |
| `CONFIG.C` | 9: `calibrate_joystick` .. `ega_upload_planes` | 0x51C3-0x6093 | 0x0F02-0x12EF (+pad 0x12EF) | 0x654C-0x8A24 |
| `HARDWARE.C` | 28: `install_keyboard_handler` .. `print_long` | 0x6093-0x6F25 | 0x12F0-0x132D (+pad 0x132D) | 0x8A24-0x9EC8 |
| `lowlevel.asm` | (asm worker) | 0x6F26-0x7E59 (pad 0x6F25) | 0x132E-0x13A9 (+pad) | - |
| `tiles.asm` | (asm worker) | 0x7E5A-0x9413 (pad 0x7E59) | 0x13AA-0x1439 (+pad 0x1439) | - |
| data-only module | - | - | 0x143A-0x493A (`g_vga_palette`, `g_levels`) | - |

`tools/verify_sources.py` proves each unit EXACT with addresses taken from
its own composition (directives `@at`, `@seg _DATA`, `@seg _BSS`; every
reference into the unit's own data resolved through those bases, every
reference to another unit or assembly module through that object's placed
PUBDEFs), checks that each unit's publics are exactly the census C functions
in its extent, and that units + assembly modules tile `_TEXT`
[0x239,0x9413), `_DATA` [0xA8,0x1439) and the game `_BSS` [0x4C60,0x9EC8)
with nothing between them but TLINK word-alignment pads.

### Evidence for the boundaries

- **V** `_DATA` = a unit's initialised variables (definition order,
  unpadded), the images of its initialised local aggregates where their
  functions are compiled, then its string literals in order of appearance
  (docs/compiler-behaviors.md). DAVE's pool ends exactly at DS 0x0F02 (the
  last literal `"           press space"` of `level_complete`), and the next
  bytes (0x0F02: `4,9,14,19`, the control panel's row table) are
  initialised data again -- a new unit. CONFIG's pool ends at 0x12EF (odd:
  one TLINK pad byte), followed by initialised data again (0x12F0: the
  input-device table) -- a third unit, whose single literal
  `"Out of memory!"` (0x131E) ends at 0x132D (pad), where lowlevel.asm's
  `_DATA` starts. Inside DAVE the order is: globals 0x00A8-0x07B6, local
  images 0x07B6-0x08B0 (check_high_score .. update_score, redraw_screen,
  level_complete, init_game_once), literals 0x08B0-0x0F02.
- **V** `_BSS`: DAVE's variables are referenced only by DAVE functions and
  fill 0x4C60-0x654A; the region 0x654C-0x9EC8 interleaves variables used
  only by CONFIG with variables used only by HARDWARE (e.g. 0x6556 CONFIG,
  0x65A8 `g_pic_planes`, 0x65B0 CONFIG), so some unit necessarily DEFINES
  variables only another unit uses.
- **H** Code boundary CONFIG|HARDWARE between `ega_upload_planes` (F_6213)
  and `install_keyboard_handler` (F_6293), BSS boundary at DS 0x8A24. The
  bytes allow the code boundary anywhere from F_6099 to F_6293 and the BSS
  split anywhere at a word boundary (calls inside a unit and across units
  produce the same bytes; the hash order is unobservable without the
  original names). The choice minimises "defined in a unit that never uses
  it": with `setup_graphics_pointers`/`ega_upload_planes` in CONFIG and the
  split at 0x8A24 only `g_pic_tileptr` (used by setup_graphics_pointers)
  and `g_adapter_type` (main, detect_hardware) live in a unit that does not
  use them. The picture-file set-up belongs with the control panel it draws
  (the picfiles are the control-panel icon banks), which fits.
- **H** `init_game_state` (F_535A) in DAVE: no `_DATA` evidence either way;
  it touches only DAVE's variables (plus g_video_mode).
- **H** The 2-byte unreferenced hole at DS 0x654A is attributed to DAVE
  (`g_unused_654a`); it could equally be the first variable of CONFIG.
- **V** The game `_BSS` ends at 0x9EC8 with HARDWARE's last variable; the
  assembly modules have no `_BSS`, and the data-only module none either
  (CS.LIB's `__atexittbl` starts at 0x9EC8).

### Data owned by the assembly and the data-only module

- **V** DS 0x132E-0x1439 is the assembly modules' `_DATA` (asm worker):
  `SoundData` 0x137A, `SoundEnabled` 0x137E, `XorMask` 0x1392, `LevelPtr`
  0x13AC, `RowTimes100` 0x13DD are C-visible publics; the C units declare
  them `extern` under those names (DAVE.H).
- **V** DS 0x143A-0x493A is one more `_DATA` contribution after tiles.asm
  (word aligned: pad 0x1439): the VGA palette (768 bytes) and `g_levels`
  (10 x 1280). It has no code and no `_BSS`. In the probe it is a stand-in
  object (`DAVEDATA.OBJ`, publics `_g_vga_palette`, `_g_levels`) and lands
  exactly. **H**: a data-only C file (`unsigned char palette[768] = ...;
  char levels[10][1280] = ...;`) or a converted binary; not decidable.
- The C units reference the palette as `g_vga_palette` and the far blobs
  as `g_demo_bank`, `g_tileset_cga`, `g_tileset_vga`, `g_sound_bank`,
  `g_picfile_cga/ega/vga` (`layout/symbols.json` holds their addresses for
  the matcher until those objects are built from the codecs).

### Names the assembly modules should adopt

The assembly sources still name C variables by placeholder. For the probe,
`tools/link_probe.py` binds them in a build copy to what the C objects
export (storage names where DAVE.H renames, `+2` for the segment word of a
far pointer):

| asm extern | C symbol |
|---|---|
| `_D_8604` | `_g_pic_table` |
| `_D_8A18` | `_g_pic_charptr+2` |
| `_D_8A20` | `_g_pic_picptr_th+2` |
| `_D_8B32` | `_g_video_mode` |
| `_D_4F86` | `_g_gfx_index__2h` |
| `_D_56F0` / `_D_56F2` | `_g_tileset_Qh` / `+2` |
| `_D_56F4` | `_g_current_level______yh` |
| `_D_57A0` | `_g_scroll_x_Wh` |
| `_D_173A` | `_g_levels` |

(Regenerated by every probe run into `build/link_probe/report.json`; the
storage names change only if `layout/bss-map.json` is re-solved.)

## _BSS order

**V** Every unit's `_BSS` is laid out by TC++ 1.00's name hash
(docs/compiler-behaviors.md). The original names are lost, so the sources
use readable names bound to storage names that hash into the original slot
(`#define g_score_... ` lines in `src/DAVE.H`, computed by
`tools/bss_names.py` from `layout/bss-map.json`). 60 of the 90 `_BSS`
variables need one. The full map is `docs/bss-map.md`. A broken storage name
moves variables and the strict match fails (tested by hand: dropping one
`#define` in HARDWARE's range turns HARDWARE and CONFIG into MISMATCH).

## Reproduce

```
python tools/verify_sources.py --json build/verify.json   # units + asm, composition
python tools/bss_names.py --check                          # storage names vs map
python tools/link_probe.py                                 # whole-program link, compare
```
