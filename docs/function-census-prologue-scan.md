# Function census: `_main` boundary resolution and initial census

## The `_main` disassembly-alignment mystery: resolved

The blocker recorded in `docs/blockers.json` ("Initial function census over
RAW_LOAD_MODULE (starting with `_main`)") claimed the linker-resolved call
target for `_main` was **file offset 0x639 (1593)**, and that linear
disassembly there did not show the expected Turbo C++ 1.00 prologue
(`55 8B EC` = `push bp; mov bp,sp`).

That target was wrong by exactly 512 bytes (0x200) — the same 512-byte value
as `STARTUP_C0S`'s file offset base. The bug was an **address-space
double-conversion**: the self-relative `CALL rel16` fixup value was correctly
resolved into "load-module offset 0x439", but that quantity was *already* a
file offset (relative to the actual `CS:IP = 0000:0000` base, which the DOS
loader places at file offset 512 — see `docs/startup-binding-evidence.json`
and `tools/recover_startup_binding.py`'s own docstring, which states this
explicitly: "the very start of the unpacked load module (file offset 512,
the entry point CS:IP=0000:0000)"). Adding 512 to it a second time to "convert
load-module offset to file offset" produced the erroneous 0x639.

### Re-derivation from raw bytes

The `CALL` instruction in `STARTUP_C0S` that targets `_main` is at **file
offset 764–766**, not 765–767 as originally logged (off by one, opcode vs.
operand):

```
file offset:  764   765   766
bytes:        E8    3A    01
              ^     ^^^^^^^^^
              opcode  disp16 (little-endian) = 0x013A = 314
```

C0S.OBJ's OMF `FIXUPP` record location for this fixup is `_TEXT`-segment
offset 253, which is the **displacement field**, not the opcode — i.e. file
offset `253 + 512 (STARTUP_C0S's file base) = 765`. That is one byte into the
instruction (the `3A`), which matches the raw bytes above and confirms this
is indeed the fixed-up call.

For a self-relative `CALL rel16`, the CPU computes
`target = IP_after_instruction + disp16`, where `IP` is measured from the
segment's own base (file offset 512, per above):

```
IP_after_instruction (seg-relative) = (764 + 3) - 512 = 255       (0x0FF)
target (seg-relative)               = 255 + 314        = 569       (0x239)
target (file offset)                = 569 + 512         = 1081      (0x439)
```

**`_main` is at file offset `0x439` (1081), not `0x639`.** This is also
exactly the manifest boundary between `STARTUP_C0S` (`[512, 1081)`) and
`RAW_LOAD_MODULE` (`[1081, 172848)`) in `layout/manifest.json` — i.e.
`_main` is the very first byte of `RAW_LOAD_MODULE`, which makes complete
sense: it is the first user-code byte the linker placed right after the
startup library object.

Disassembling from file offset 1081 shows exactly the expected prologue:

```
file offset 1081: 55 8B EC 39 26 9A 00 72 03 ...
                   push bp
                   mov  bp, sp
                   cmp  [0x009A], sp      ; Turbo C stack-overflow check idiom
                   jb   ...
```

So (c) from the task's hypothesis list was closest to the truth in spirit —
there wasn't a separate thunk function, but there *was* a systematic
off-by-512 in the anchor address computation that made "0x639" look like
valid-but-frameless code purely by coincidence (mid-function bytes of some
other, unrelated function happened to disassemble plausibly).

## Methodology for the wider census

`tools/function_census.py`:

1. Scans `RAW_LOAD_MODULE` (file offset 1081–172848) for the literal byte
   sequence `55 8B EC` (`push bp; mov bp, sp`) as candidate function starts.
   This is the prologue Turbo C++ 1.00 (small model, `-1- -f- -N-`) always
   emits for any function that is not a trivial single-basic-block leaf.
2. For each candidate start, linearly disassembles forward with Capstone
   (`CS_MODE_16`), **using addresses relative to file offset 512** (the
   program's `CS:IP = 0000:0000` base — see above; this was the exact bug
   that produced the original mystery) so that self-relative `CALL`/`JMP`
   targets resolve to correct file offsets instead of wrapping/aliasing.
3. Stops at the first `RET`/`RETF`, capped at the next candidate start as a
   safety net against runaway disassembly into unrelated bytes.
4. Records: id (`F_<hex file offset>`), start/end/size, whether a `SUB
   SP,imm` frame-locals instruction immediately follows the prologue,
   resolved `CALL` targets, and any `IMUL` idioms spotted (struct-array
   indexing candidates).

### Result: the code segment's extent falls out naturally

193 candidate functions were found, spanning file offsets **1081–46179**
(~45 KB). No further `55 8B EC` matches occur anywhere in the remaining
~126 KB of `RAW_LOAD_MODULE` (up to file offset 172848). This is strong
circumstantial evidence that Turbo C++'s `_TEXT` code segment for this
program ends around file offset ~46179, and everything after that is the
`_DATA`/`_BSS` segment (globals, strings, tables, level data) — consistent
with a single-segment small-model layout (`_TEXT` then `DGROUP`). This
segment-boundary hypothesis is **not yet proven** (no OMF segment
directory survives repacking/relinking) and is recorded as a new frontier
in `docs/blockers.json` rather than asserted as fact.

Sanity checks on the 193-function census:
- Zero overlapping function ranges.
- Zero truncated functions (every candidate reached a `RET`/`RETF` before
  hitting the next candidate's start).
- 44 of 193 functions have a `SUB SP,imm` immediately after the prologue
  (true bp-relative locals); the rest use `bp` only for parameter access.
- 29 functions contain `IMUL` idioms, including repeated `imul dx` by small
  constants (struct-size array indexing) in `F_04FC` and `F_088E`, matching
  the `imul` by 9 / by 7 idiom noted in the original task description.
- 43 resolved `CALL` targets do not land exactly on a recorded `F_XXXX`
  start. Spot-checking several of these (e.g. file offsets `0xA460`,
  `0xA469`, `0x850A`, `0xA34C`) shows small, frame-using leaf functions that
  the `55 8B EC` scan *did* actually find (they use the same prologue) —
  these are legitimate additional functions already present in the census;
  the "unmatched" list mostly reflects calls into the tail of the code
  region (~file offset 43000-46300) that are worth re-examining, plus one
  call target at file offset 783 that lands inside `STARTUP_C0S` itself
  (plausibly a call to `_exit` or similar library routine, out of scope for
  this pass).

### Notable candidates spotted while spot-checking

- `F_A460` (9 bytes) and `F_A469` (11 bytes): trivial one-basic-block
  wrappers around `IN AX,DX` / `IN AL,DX` — these look exactly like Turbo
  C++ 1.00's runtime library `inport()`/`inportb()`. Excellent matching-C
  candidates for a future pass (not attempted here — would need to compile
  against the pinned toolchain and OMF-bind to prove it, per
  `docs/matching-phase.md`'s standard of proof).
- `F_850A` (12 bytes): wraps `INT 21h` with `AH=9` (DOS "print string"),
  consistent with a runtime helper (e.g. part of `puts`/`cputs`/`_dos_write`
  family), not user game code.
- `F_04FC` and `F_088E` (both containing many `imul dx` idioms): promising
  candidates for the game's own struct-array-indexed data access code
  (actors/sprites/tiles), given the recurring `imul` by small constants
  noted in the task brief — good next targets for semantic naming and
  matching-C promotion, but not attempted in this pass.

## Files

- `tools/function_census.py` — the census tool (uses Capstone via the
  pinned `Python312` interpreter that has it installed).
- `docs/function-census.json` — machine-readable output: 193 functions,
  each with id/start/end/size/has_frame/has_sub_sp/calls/notes.
