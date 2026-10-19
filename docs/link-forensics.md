# Link forensics (toward Level C: emergent layout)

Working notes on how the original link produced the executable's layout.
Every claim is tagged **V** (verified against bytes/experiment) or **H**
(hypothesis to test).

## Linker and segment order

- **V** TLINK 3.0 (shipped with Turbo C++ 1.00) links `C0S + game + CS.LIB`
  with this segment order (from a probe link, `tools/tlink.py`):
  `_TEXT`, `FAR_DATA`-class segments (`_FARDATA`), `_OVERLAY_`, `_INIT_`,
  `_INITEND_`, `_EXIT_`, `_EXITEND_`, `_1STUB_`, then DGROUP: `_DATA`,
  `_CVTSEG`, `_SCNSEG`, `_BSS`, `_BSSEND`, `_STACK`.
- **V** In the original, the far data segments (paragraphs 0x0B31-0x20CC)
  sit exactly where `FAR_DATA` class goes: between `_TEXT` and `_INIT_`
  (paragraph 0x254C), DGROUP at 0x254D. The `FAR_DATA` class name itself is
  inferred from placement (**H** until a far array compiled by TCC links to
  the same place).
- **V** Library modules are emitted in CS.LIB member order in three
  alphabetical runs (docs/library-map.md), i.e. TLINK's library pass order.
- **V** `SS:SP = 0x2F3F:0x0080` puts `_STACK` (128 bytes, C0S default) at
  DS:0x9F20; DGROUP initialised data ends at DS:0x4C60 = end of file (TLINK
  does not write trailing BSS).
- **V** The MZ header in `build/DAVE_unpacked.exe` (relocation table at 0x1C)
  is the unpacker's reconstruction; TLINK 3.0 writes its table at 0x3E. This
  does not matter for the packed target: LZEXE 0.91 applied to the unpacked
  image reproduces `DAVE.EXE` exactly (`tools/repack.py --oracle`).

## Translation units of the game C code (H, from `_DATA` references)

Turbo C emits each unit's initialised globals and then its string literals
into `_DATA`, and units appear in the same order in `_TEXT` and `_DATA`.
Clustering the DS addresses each C function references (script in the
2026-10-19 session; to be rerun as functions are matched, using their exact
`@seg _DATA` bases):

| unit | functions (file ids) | `_DATA` it owns |
|---|---|---|
| 1 main game | F_0439 .. F_519B (F_535A ?) | globals from DS 0xA8, literals DS 0x7CE-0xF02 |
| 2 configuration screens | (F_535A ?) F_53C3 .. F_5DD5 | globals from DS 0xF02, literals DS 0xF63-0x12EF |
| 3 hardware: keyboard ISR, timer, video | F_6099 .. F_70F8 | globals DS 0x130E-0x143A (incl. VGA palette 0x143A) |
| ASM modules | cs 0x6F25 .. 0x9413 | DS 0x1310.. ? and g_levels 0x173A-0x493A ? |

Next steps: pin each unit's exact `_DATA` extent from matched functions'
literal bases; test the order/hash rule for uninitialised globals in TC++ 1.00
(codegen lane); then compile a complete unit and link it with raw stand-ins
for the rest to show its addresses emerge.
