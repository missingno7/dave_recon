# External RE import: yo-yo-yo-jbo/dangerous_dave

Per `docs/blockers.json`'s "Import and verify yo-yo-yo-jbo/dangerous_dave RE
facts" frontier: [`yo-yo-yo-jbo/dangerous_dave`](https://github.com/yo-yo-yo-jbo/dangerous_dave)
is a blog-post-plus-tooling reverse-engineering writeup of an unpacked
`DAVE.EXE` the author claims is SHA1 `9e572f0320ca759bea8f24a0ebcfcb1b68474e13`
— the same specimen as `build/DAVE_unpacked.exe`. Nothing from it is accepted
on faith; every fact below is independently re-derived against our own bytes
(never the external repo's copy, except the one-time specimen-identity hash
check) with `tools/verify_external_re.py`, and recorded with full provenance
in `docs/external-re-evidence.json`.

## Specimen identity (re-checked, not re-quoted)

We did not trust the README's stated SHA1. We fetched the external repo's
own committed `DAVE.EXE` via `gh api
repos/yo-yo-yo-jbo/dangerous_dave/contents/DAVE.EXE`, and hashed it
ourselves: SHA1 `9e572f0320ca759bea8f24a0ebcfcb1b68474e13`, 172848 bytes —
**verified independently** as identical to `build/DAVE_unpacked.exe`.

Their *packed* original, however, is a different file from ours: 76597 bytes
in their README vs. our `assets/DAVE.EXE`'s 76586 bytes (SHA1
`a8e14979d4259bc086b7d6b8ced575c66c4f9fef`, computed here, vs. their stated
`b0e70846c31d651b53c2f5490f516d8fd4844ed7`) — **contradicted**, but harmless:
two different LZEXE-packed distributions of the same underlying program
decompress to the identical image, which is the only identity this
project's addresses/facts actually depend on.

## Figuring out their coordinate convention first

The blog mixes three different, unlabeled addressing conventions. We
disentangled them empirically (never assumed) by disassembling our own file
until the arithmetic became unambiguous — see `tools/verify_external_re.py`'s
module docstring for the full derivation:

1. **Explicit "offset X from the file"** (his own phrase) and the two Python
   snippets that slice `open('DAVE.EXE','rb').read()[0x2583a:...]` directly
   — these are literal `file_offset`s in exactly our own coordinate system.
   No conversion.
2. **`sub_XXXXX`** (IDA function names) — these are IDA linear addresses
   under the assumption that the CODE segment is based at linear `0x10000`
   (paragraph `0x1000`). Our own `build/DAVE_unpacked.exe` actually has
   `e_cs = 0x0000` in its MZ header (the real load-time base, matching the
   proven `_main @ file offset 0x439` anchor and `tools/coordinates.py`'s
   `load_module_offset`), so IDA's `0x1000`-paragraph default placeholder is
   `0x10000` higher than our own coordinate origin. Conversion:
   `file_offset = coordinates.load_module_to_file_offset(sub_addr - 0x10000)`.
   This was not assumed — it was *proven* by converting all 10 `sub_XXXXX`
   addresses quoted across three different code snippets in the blog and
   finding that every single one reproduces our own disassembly **byte for
   byte, instruction for instruction, including every conditional branch**,
   at three different, independently-existing functions in this task's own
   Part 1 call-graph census.
3. **`word_XXXXX`** (IDA data names) — used directly as the literal
   DS-segment-relative displacement encoded in the instruction bytes (e.g.
   `mov word ptr [0x56f4], 0` really is `c7 06 f4 56 00 00` in our file). Not
   converted to `file_offset`, since this project has not yet independently
   established the DS segment's own paragraph-base-to-file-offset mapping
   (a separate open frontier, see `docs/blockers.json`'s "_TEXT/_DATA
   boundary" item) — comparisons use the raw operand value as-is.

## Results: 10 facts imported, 7 verified, 2 contradicted, 1 could-not-check

| id | verdict | one-line summary |
|---|---|---|
| `EXT_SPECIMEN_IDENTITY` | verified | Their committed `DAVE.EXE` hashes identically to ours (SHA1 checked ourselves). |
| `EXT_PACKED_SPECIMEN_IDENTITY` | contradicted | Their *packed* original differs (76597B vs. our 76586B) — different distributions, doesn't matter for this project. |
| `EXT_INIT_FUNCTION` | verified | File offset `0x535a`: 10 game-state initializations (`g_lives=3`, scores/goals=0, `g_maybe_levels_left=10`, etc.), byte-for-byte, in order. Also an independently-discovered function start in our own Part 1 census (`F_535A`) — corroboration in both directions. |
| `EXT_LEVEL_COMPLETE_FUNCTION` | verified | `F_3BA3`: the 8-call level-completion sequence (`sub_10BFB` called twice) matches exactly once the `sub_XXXXX → file_offset` conversion is applied; all 7 distinct callees are pre-existing Part 1 census entries. |
| `EXT_WARP_TRANSITION_FUNCTION` | verified | `F_34CB`: warp-zone-entry bookkeeping (`g_curr_warp_zone_mapping`, the `+0x192`/`+0x1a6`/`+0x16a` table lookups, `g_current_level -= 1`, `g_start_y = 0x10`) matches exactly. |
| `EXT_WARP_TARGET_LEVEL_TABLE` | verified | File offset `0x2583a`: 10×uint16 table `(0,0,0,0,2,0,0,6,7,1)` confirming warp zones only at 1-based levels 5/8/9/10. |
| `EXT_LEVEL6_BUGGY_WARP_DATA` | verified | File offset `0x2932b`: the exact 32 out-of-bounds bytes read by the level-6 warp bug. |
| `EXT_LEVELS_BASE_ADDRESS` | **contradicted** | Claimed `g_levels` base at file offset `0x26E0A` — see below, this is wrong. |
| `EXT_SCORE_LIVES_LOGIC` | verified | `F_0C34`: the extra-life-at-20000-points-or-1/1000th-of-goal logic and the 99999-point score cap, both reproduced exactly including every constant (`0x4e20`, `0x869f`). |
| `EXT_LEVEL_ARRAY_FORMAT` | could_not_check | 1280-byte-record structural claim depends on the now-contradicted base address; not independently testable without first re-deriving the real base. |

### The one real, substantive contradiction: `g_levels` is not at file offset `0x26E0A`

Unlike every other numeric claim in the README, `0x26E0A` is the one the
author attributes to a *third party* (the shikadi.net modding wiki) and
never re-validates himself with a raw byte slice the way he does for
`0x2583a` and `0x2932b`. Two independent checks both say it's wrong:

1. **The bytes don't look like level data.** `build/DAVE_unpacked.exe` at
   file offset `0x26E0A` is `00 2f 8d 2f 8d 2f 8d 2f 00 c5 ce d4 c5 d2 a0 c6
   c9 cc c5 ce c1 cd c5 a0 a8 ac cf d0 d4 ae a0 c6`, which (XOR `0x80` on the
   high-bit-set run) decodes to readable text resembling an "ENTER
   FILENAME..." style prompt — not packed path/tile bytes.
2. **The author's own math doesn't reconcile.** He explains level 6's
   buggy warp data (independently confirmed at file offset `0x2932b`) as
   `g_levels_base + ((-1 * 0x500) mod 0x10000)`. If `g_levels_base` really
   were `0x26E0A`, the two possible interpretations of that wrap give
   `0x2690A` (plain subtraction) or `0x3690A` (full 16-bit-wrapped
   addition) — **neither equals `0x2932b`**, and `(0x2932b - 0x26E0A) /
   0x500 ≈ 7.43` isn't even an integer multiple of the claimed 1280-byte
   stride.

So `0x26E0A` is inconsistent with the author's own verified data point, by
his own stated formula, independent of our text-content observation. The
real `g_levels` base is not yet re-derived by this project — recorded
honestly as an open question (`EXT_LEVEL_ARRAY_FORMAT`) rather than guessed.
This is exactly the "third-party claim repeated by a second party without
re-verification" pattern `docs/vision.md` warns about, caught mechanically.

## New function-census entries or matching-C candidates?

**None needed adding.** Every function address referenced by a verified
fact above (`F_535A`, `F_3BA3`, `F_34CB`, `F_0C34`, and all 7 of
`F_3BA3`'s callees `F_769B`/`F_0DFB`/`F_4E69`/`F_7831`/`F_8EDA`/`F_4D9C`/
`F_3435`, plus `F_34CB`'s callee `F_4E69`) was **already present** in Part
1's call-graph census before this import — a strong, symmetric cross-check
of both this task's call-graph walk and the external project's own
addresses.

What this import *does* add, that Part 1 could not: real semantic identity
for four previously address-only census entries, making them excellent
**matching-C candidates** for `docs/matching-phase.md`'s frontier #4
("First matching-C promotions inside game code"), now with a name and a
known purpose rather than just a boundary:

- `F_535A` — game-state initializer (`g_lives=3`, scores/goals zeroed, etc.)
- `F_3BA3` — level-completion / advance-to-next-level dispatcher
- `F_34CB` — warp-zone-entry transition (backs up the current level, applies
  the three per-level warp tables, jumps into the target level)
- `F_0C34` — score-vs-next-goal extra-life check + 99999-point score cap

## Data addresses recorded but not yet convertible to `file_offset`

`g_lives=0x56ee`, `g_score_lo=0x4c60`, `g_score_hi=0x4c62`,
`g_next_goal_lo=0x6148`, `g_next_goal_hi=0x614a`, `g_is_game_over=0x5792`,
`g_current_level=0x56f4`, `g_some_level_reference=0x57a0`,
`g_maybe_levels_left=0x615a`, `g_is_warp_zone=0x573c`,
`g_curr_warp_zone_mapping=0x6152`, `g_start_y=0x56ec`, plus the two
unnamed per-level tables at DS-relative `+0x192`/`+0x1a6`. All of these were
independently confirmed as the literal operand bytes encoded in real
instructions in `build/DAVE_unpacked.exe` (not merely repeated from the
README) — but they are DS-segment-relative, and this project has not yet
established where the DS segment's own base lands in file-offset terms
(the still-open "_TEXT/_DATA boundary" frontier in `docs/blockers.json`).
Once that's resolved, converting this whole list to `file_offset` is
mechanical.

## Files

- `tools/verify_external_re.py` — the import/verification tool (read-only:
  touches only `build/DAVE_unpacked.exe`, `assets/DAVE.EXE`, and
  `docs/function-census.json` for cross-referencing; never
  `layout/manifest.json` or `docs/blockers.json`).
- `docs/external-re-evidence.json` — the 10 facts, each with `source_url`,
  `source_address` (as given externally), `external_coordinate_convention`
  (documented per-fact, not just once globally), `claimed_semantics`,
  `our_file_offset`/`our_load_module_offset`, `our_census_function_id`,
  `verification_status`, `verification_evidence`, and `provenance`.
