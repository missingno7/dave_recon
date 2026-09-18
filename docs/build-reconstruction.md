# Build/link reconstruction contract

Modeled on `empires_reconstruction`'s four-level proof ladder.

| Level | Established when | Not yet implied |
|---|---|---|
| Placement | A component's bytes match at its declared original file offset | The position follows from any recovered linking rule |
| Component | Source independently compiles/assembles/encodes to the complete matching component | Original whole-build topology is recovered |
| Structural build | Module ordering, sizes, segments, and (eventually) LZEXE packing generate layout mechanically | All unknown/fixed fallbacks are gone |
| Emergent whole build | Components + recovered rules produce `DAVE.EXE`/`EGADAVE.DAV` with no fallback or forced placement | Historical source filenames are required to match |

## Two layers, tracked separately

Dangerous Dave adds a layer `empires_reconstruction` did not have to deal with
for its EXE: **LZEXE 0.91 packing**. We therefore report two independent
build targets:

```text
Level 1: reconstructed unpacked image  ==  reference unpacked image
Level 2: reconstructed packed image    ==  original DAVE.EXE (as distributed)
```

Level 1 is the primary near-term goal and gates all matching-C/ASM work.
Level 2 requires separately reconstructing the historical LZEXE packing
policy (compression parameters, stub bytes, any packer version quirks) and
is tracked as its own frontier in `docs/blockers.json`. Failing to solve
Level 2 does not block progress on Level 1.

## Directory split: layout/ (fixed) vs recipes/ (derived)

Same convention as `empires_reconstruction`, applied from day one:

- `layout/manifest.json` — the fixed-placement scaffold for the unpacked EXE:
  explicit `start`/`end` file offsets taken from the original unpacked image.
  This is the bootstrap builder and comparison oracle.
- `layout/archives/*.json` — analogous fixed-placement manifests for
  `EGADAVE.DAV` resource chunks, once its format is understood.
- `recipes/` — the emergent/derived path. Recipes must never contain original
  offsets, sizes, or digests — only component order and source/encoding
  rules. A recipe-driven packer must compute offsets purely from emitted
  component sizes, then a separate verification step checks
  `derived pack == fixed rebuild == original`.

EXE-side work will likely stay at fixed placement (`layout/manifest.json`)
for a long time before migrating region-by-region into a recipe-driven,
linker-emergent scheme — this is expected and matches
`empires_reconstruction`'s own documented gap.

## Toolchain pinning

Once a candidate compiler/assembler/version/memory-model/flags combination is
established (see `docs/blockers.json`), it will be pinned by SHA-256 in
`layout/toolchain.json`, installed locally via `tools/setup_toolchain.py`
(never committed to git), and invoked through an isolated, disposable
DOSBox build session per compile — no cached object file may ever satisfy a
fresh build claim.
