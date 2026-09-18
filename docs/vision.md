# Dangerous Dave Reconstruction

## Vision

`dave_recon` reconstructs the original DOS version of **Dangerous Dave** into a
complete, human-readable, lossless source representation.

The goal is not a source port. It is not a behaviorally-equivalent rewrite. It
is not a modernization.

The goal is to take the original game files apart, understand what every part
of them is, give those parts names and meaning, and still be able to put them
back together into byte-identical originals.

This applies to code, embedded data, graphics, sprites, fonts, palettes,
levels, lookup tables, resource formats, compiler/runtime support code, and
executable metadata (headers, relocations, and the LZEXE packing layer).

Conceptually:

```text
original game
    DAVE.EXE   (LZEXE-packed)
    EGADAVE.DAV
        ↓
lossless decomposition
        ↓
code / data / assets / runtime / executable metadata
        ↓
functions / globals / structures / formats / modules
        ↓
matching C + matching ASM + reconstructed data/assets
        ↓
historically compatible compile / assemble / link / pack
        ↓
original game files
```

The original files are the ground truth. Every claim of understanding must be
demonstrated by re-deriving the original bytes, not merely described.

## Packing layer is separate from program reconstruction

`DAVE.EXE` is packed with **LZEXE 0.91** (see
[lzexe-unpacking.md](lzexe-unpacking.md) and the specimen manifest). We treat
unpacking as its own reconstruction layer:

```text
original packed DAVE.EXE
        ↓
packing layer (LZEXE 0.91)
        ↓
historical unpacked executable image
        ↓
program reconstruction (this repository's main effort)
```

Matching-C/ASM promotion, function census, and ownership bookkeeping all
operate on the **unpacked** executable image. Exact re-derivation of the
LZEXE-packed bytes from a reconstructed unpacked image is a later, separately
tracked goal. Until it is solved, the packed file remains the final oracle,
and `unpacked reconstruction == unpacked reference` is reported as an
independent metric from `packed reconstruction == original packed DAVE.EXE`.

## Progression ladders

Code: `RAW → DISASSEMBLED → FUNCTION_BOUNDARY_KNOWN → STRUCTURED_ASM →
MATCHING_ASM → MATCHING_C`. Not every region must reach C — hand-written
graphics/interrupt/port-I/O routines may correctly remain matching ASM
permanently.

Data/assets: `RAW → IDENTIFIED → FORMAT_UNDERSTOOD → STRUCTURED →
REBUILDABLE → EXACT_MATCH`.

Matching is the authority. Disassembly, naming, and typing can be wrong; only
re-compiling/re-encoding to identical bytes plus fixups/relocations is proof.

## Losslessness is the fundamental invariant

Every byte of the unpacked executable has exactly one owner at all times, even
when that owner is a temporary `RAW_UNKNOWN` fallback. Semantic improvement
must never require throwing away machine truth. See
[layout/manifest.json](../layout/manifest.json) for the ownership ledger.

Historical quirks (dead code, odd padding, suboptimal codegen) are preserved
as evidence, not "fixed."

## Architectural end-state: layout must emerge

A fixed-placement builder — reconstructing the exact original bytes by
placing known-good components at their original file offsets — is a bootstrap
scaffold and comparison oracle, not the final build system.

The final build must compile/assemble/encode independent source modules, link
them with a historically faithful linker, and (eventually) re-pack with
LZEXE, such that addresses and offsets **emerge** from translation-unit
composition, segment ordering, symbol resolution, and linker/packer behavior
— not from copying original addresses.

Track four levels separately, as in the sibling `empires_reconstruction`
project:

1. **Placement reconstruction** — component matches at its declared original
   location.
2. **Independent component reconstruction** — source independently
   compiles/encodes to the complete matching component.
3. **Structural build reconstruction** — ordering/sizes/segments/packing
   generate layout mechanically.
4. **Emergent whole-build reconstruction** — components + recovered rules
   produce the original files with no fallback or forced placement.

Never confuse "I can put these exact bytes at the right address" with "I have
reconstructed why those bytes end up at that address."

## Toolchain is discovered, not assumed

Reports describe Dangerous Dave as mostly C with hand-written assembly, but we
do not hard-code a compiler version. The toolchain (compiler, version, memory
model, flags, assembler, linker) is determined empirically by compiling
probes and comparing emitted OMF/machine code against the original, following
the same method as `empires_reconstruction`'s `layout/toolchain.json` +
`tools/setup_toolchain.py` + DOSBox-driven compile loop.

## Instruments, not dependencies

Emulators/debuggers may be used as observation instruments to understand
semantics (execution frequency, call graphs, register arguments, buffer
layouts). They never replace binary matching and are never a runtime
dependency of the reconstructed artifact.
