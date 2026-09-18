# Function census: call-graph walk rooted at `_main`

This supersedes the naive prologue scan as the authoritative
`docs/function-census.json`. The prologue scan's own writeup (the `_main`
coordinate-bug resolution, and the original 193-function scan's methodology
and spot-checks) is preserved unmodified at
[`function-census-prologue-scan.md`](function-census-prologue-scan.md) /
[`function-census-prologue-scan.json`](function-census-prologue-scan.json) —
this document only covers what changed and why, per
`docs/blockers.json`'s "Function census rooted at `_main` @ 0x439" frontier,
which explicitly asked for the prologue scan to be rebuilt as a call-graph
walk.

## Why rebuild it

A pure byte-pattern scan for `55 8B EC` (`push bp; mov bp, sp`) has two
structural weaknesses documents itself already flagged:

- It cannot see **frameless functions** (leaf routines with no stack frame —
  e.g. Turbo C++'s tiny `inport()`/`inportb()` wrappers).
- It has **no notion of reachability** — every matching byte pattern is
  reported as a "function," including any that occur coincidentally inside
  data.

A call-graph walk rooted at the one address we have independently, exactly
proven (`_main @ file offset 0x439`) fixes both: it only reports addresses
that are actual near-CALL targets from other reachable code, and it finds
frameless functions as a side effect of simply following calls to wherever
they land, prologue or not.

## Tooling

- `tools/function_census.py` — unchanged in method, **renamed in role**: it
  is now a baseline/cross-reference input only, writing
  `docs/function-census-prologue-scan.json` (schema
  `dave-function-census-prologue-scan-v1`) instead of
  `docs/function-census.json`. `tools/library_scanner.py` (out of scope for
  this task, actively used by other work) still reads
  `docs/function-census.json` for its own size-anchoring heuristic; the new
  authoritative file keeps a `start` field (identical in value to
  `file_offset`) specifically so that dependency keeps working unmodified.
- `tools/call_graph_census.py` — new, produces the authoritative
  `docs/function-census.json` (schema `dave-function-census-v2`).

## Method

1. **Worklist seeded with `_main` (file offset `0x439`).**
2. For each worklist address: disassemble linearly forward with Capstone
   (`CS_MODE_16`), passing load-module-relative addresses (i.e. `file_offset
   - 0x200`) exactly as the prologue scan already did, so self-relative
   `CALL`/`JMP rel16` targets resolve to the right file offsets instead of
   reproducing the historical file/load-module double-counting bug (see
   `tools/coordinates.py`).
3. The body ends at the first of:
   - a `RET`/`RETF` (`stop_reason: "ret"`) — the common case, 155/172
     (90%) of the reachable functions;
   - an **indirect `JMP`** through a register/memory operand
     (`stop_reason: "indirect_jmp"`) — the classic Turbo C switch-dispatch
     idiom (`jmp word ptr cs:[bx+table]`); continuing past it would read the
     jump table's raw word data as instructions, so the sweep stops there
     instead and records the site as unresolved indirect control flow;
   - a **backward-out-of-function unconditional `JMP`**
     (`stop_reason: "jmp_out_of_function"`) — discovered empirically at file
     offset `0xB4FF` (see "A real bug this caught" below);
   - or a hard byte cap with none of the above (`stop_reason:
     "cap_reached_no_terminator"`), always flagged, never trusted silently.
4. Every near `CALL rel16` target is resolved **two independent ways** and
   asserted equal: once via Capstone's own resolved operand, and once by
   re-deriving it from the raw opcode bytes through
   `tools/coordinates.py`'s `resolve_self_relative_call`. This is a standing
   regression guard for the exact class of bug that produced the historical
   "0x639 instead of 0x439" mistake — every single call resolution in this
   census re-proves that fix.
5. Resolved targets `>= 0x439` are enqueued (if unvisited) as new census
   functions. Targets `< 0x439` land inside the already-identified
   `STARTUP_C0S` library region (`layout/manifest.json`'s `KNOWN_LIBRARY`
   entry, file offset `[0x200, 0x439)`) and are recorded as call edges to a
   `LIBRARY@0x...` pseudo-node rather than walked further or given their own
   `F_XXXX` entry — that region is already owned/classified, outside this
   census's scope.
6. Once the worklist is exhausted, a **finalize pass** recomputes every
   function's extent capped at the *next known function start* (mirroring
   the prologue scan's own capping convention) instead of the generous
   exploratory cap, to get clean, comparable, mostly non-overlapping
   extents. Any case where this tighter cap cuts a function off before its
   own terminator is recorded verbatim as an `overlap_anomaly` — not guessed
   away in either direction.

## A real bug this caught: naive "stop at RET" is not enough

The very first run produced two `overlap_anomalies`. One
(file offset `0xB4FF`) turned out to be a genuine disassembly-quality bug,
not a false alarm.

`0xB4FF` is a 6-instruction, 12-byte routine:

```
push cs
pop  ds
mov  dx, 0xb2ed      ; -> DS:DX = address of an error message
mov  ah, 9           ; DOS "print string" function
int  0x21
jmp  0x1012e         ; wraps mod 0x10000 to load-module offset 0x012e
                      ;   = file offset 0x32e = 814, i.e. inside STARTUP_C0S
```

This is Turbo C++ 1.00's `-N` stack-overflow handler — the very routine
`_main`'s own prologue conditionally calls (`cmp [stackbase],sp; jb +3; call
<here>`, see `docs/flag-investigation.md`). It ends with an unconditional
near `JMP` back into the C startup module's exit sequence, **not a `RET`**.
The original sweep (which only stopped at `RET`/`RETF`) kept reading
straight through the `JMP` into the handler's own error-message string bytes
and disassembled ~2500 bogus "instructions" out of coincidental string/data
bytes before stumbling onto something that looked like a `RET` far away —
inflating both the function's reported extent and (before a second, related
fix) its reported instruction count.

Fix: an unconditional near `JMP` with an immediate target is only treated as
ending the function body if the **target address is before the function's
own start** — i.e. a tail-jump clean out of it. A forward `JMP` (e.g.
`_main`'s own `jmp 0x272`-style early-return chains to a nearby local
epilogue, still inside its own body) is explicitly *not* treated this way,
since blanket-stopping at every unconditional `JMP` would wrongly truncate
ordinary structured-control-flow functions at their first early-return
branch. This is a narrow, empirically-justified rule, not a general
control-flow reconstruction — it is still a linear sweep, not a real CFG.

The other `overlap_anomaly` (file offset `0xB093`) was investigated and left
unresolved on purpose: it is a set of four tiny 7-8 byte "thunks" (`pop cx;
push cs; push cx; mov cx,<selector>; jmp <shared body>`) that all jump
forward into one shared body ending in a **far `RET`** (`retf 8`) — a
Borland long-arithmetic (32-bit multiply/divide) runtime helper with
multiple entry points sharing one body, a pattern this census's
single-entry/first-terminator model cannot represent. This region (file
offset range roughly `0x9613`–`0xB49B`) is already claimed as `KNOWN_LIBRARY`
by the concurrent library-scanning work (`docs/library-scan-evidence.md`),
so it is flagged honestly here (`low` confidence, noted anomaly) rather than
force-fit into a shape it doesn't have.

## Results

| | prologue scan (baseline) | call-graph walk |
|---|---|---|
| functions found | 193 | **172** |
| region | file offset `0x439`–`0xB483` (byte-pattern scan over the whole span) | same region, but only addresses actually reached from `_main` |
| method | scan for `55 8B EC`, walk to next `RET`/`RETF` or next candidate start | recursive near-CALL walk from `_main`, walk to `RET`/indirect-`JMP`/backward-tail-`JMP`, finalize-capped at next known start |

Breakdown of the 172 call-graph functions:

- **133** also appear in the prologue-scan baseline (have the `55 8B EC`
  prologue) — cross-checked both ways: every call-graph start with a
  prologue *is* in the baseline (0 exceptions, as it must be, since the
  baseline scan is exhaustive over this byte pattern across the same
  region — a useful sanity invariant).
- **39** are reached by the call graph but have **no** `55 8B EC` prologue
  and are **not** in the baseline — frameless functions the prologue scan
  structurally cannot see. Most cluster in file offset range roughly
  `0x75D6`–`0xB4FF`, i.e. the same tail-of-code-region the prologue scan's
  own writeup already flagged as worth re-examining, and overlapping the
  region the concurrent library-scan work has independently started
  claiming as Turbo C++ runtime support code. These are **not** claimed as
  game logic — `likely_type: "unknown"`, `confidence: "medium"` or `"low"`,
  explicitly flagged as "not yet spot-checked" pending either matching-C
  work or the "scan Turbo C++ libraries" frontier.
- **60** baseline (prologue-scan) functions are **not** reached by the call
  graph from `_main` at all. This is expected, not a bug: a conservative
  near-CALL walk cannot follow calls made only through **unresolved
  indirect control flow** (see below) — most plausibly per-state or
  per-actor function-pointer dispatch tables, which this census
  deliberately does not guess the contents of.

Confidence distribution across all 172: 127 `high`, 5 `medium`, 1
`library_routine`/`medium` (spot-check hint, see below), 38 `unknown`/
`medium`, 1 `unknown`/`low` (the `0xB093` anomaly).

### Unresolved indirect control flow (never silently ignored)

8 sites recorded in `unresolved_indirect_targets`:

- **5 indirect `JMP`s** (`jmp word ptr cs:[bx + 0x....]`) at file offsets
  `0x1D91`, `0x4B13`, `0x67C6`, `0x68BF`, `0x6D85` — classic switch-dispatch
  jump tables. Resolving these (reading the table itself and each entry's
  target) is future work; they are exactly the kind of "for every state a
  function pointer/jump target might hide behind" case flagged as an honest
  blocker rather than guessed.
- **2 indirect `CALL`s** through a register (`call ax`) and a memory operand
  (`call word ptr [bx - 0x6138]`) — function-pointer calls, likely how some
  of the 60 unreached baseline functions actually get invoked.
- **1 tail-jump-out-of-function** (`0xB4FF`'s `jmp` into `STARTUP_C0S`,
  discussed above) — resolved as a fact (target file offset 814), but
  recorded here rather than as a call edge since it is not a `CALL`.

### Calls into the known `STARTUP_C0S` library region

1 recorded: `F_9663` (file offset `0x9663`) calls file offset `783`
(`0x30F`), inside the already-identified `STARTUP_C0S` region. Plausibly a
call into `_exit`/an equivalent library shutdown routine — consistent with
the prologue-scan writeup's own note about the same target.

## Schema (`docs/function-census.json`, `dave-function-census-v2`)

Each entry in `functions[]` has (fields the task required, plus a few kept
for prologue-scan continuity / `tools/library_scanner.py` compatibility):

- `id` — `F_XXXX` (file offset, hex).
- `file_offset`, `load_module_offset`, `end`, `size` — see
  `tools/coordinates.py` for the two coordinate systems.
- `start` — identical value to `file_offset`; kept only because
  `tools/library_scanner.py` (out of scope here) reads this field name.
- `callers` — inverted call graph (list of `F_XXXX` ids).
- `direct_callees` — list of `F_XXXX` ids, or `LIBRARY@0x...` for calls into
  `STARTUP_C0S`.
- `likely_type` — `"c_function"` / `"library_routine"` / `"unknown"`.
- `confidence` / `confidence_reason` — honest self-assessment, always with a
  stated reason (never a bare label).
- `matching_status` — `"unmatched"` for every entry; matching-C promotion is
  a separate frontier, not attempted here.
- `blockers` — free-text list, e.g. indirect jump tables, far calls,
  overlap anomalies, hard-cap truncation.
- `has_prologue`, `has_sub_sp`, `stop_reason`, `insn_count`,
  `in_prologue_scan_baseline` — supporting diagnostic fields.

Top level also has `call_edges` (843 caller→callee pairs),
`unresolved_indirect_targets`, `calls_into_known_library`,
`overlap_anomalies`, `cross_reference` (the baseline comparison numbers
above, machine-readable), and `discovery_order` (BFS visit order from
`_main`, for anyone re-deriving the walk).

## What's still open

1. **Resolve the 5 switch-dispatch jump tables.** Each is a small, bounded
   task: read the jump table's own base address and stride, enumerate its
   entries, and add each resolved entry as a new call-graph edge/worklist
   seed. Would very likely close some of the "60 baseline functions not
   reached" gap.
2. **The 2 indirect (register/memory) calls** are harder — they require
   understanding what value ends up in the register/memory operand at the
   call site (a genuine data-flow question, not just more disassembly).
3. **The 39 frameless, not-yet-spot-checked functions** are the most likely
   next source of "scan Turbo C++ libraries" matches (per
   `docs/blockers.json`) or, for any that turn out to be original game code,
   matching-C candidates — this census deliberately stops at classification,
   leaving that promotion work to the dedicated frontier.
4. **The `0xB093` multi-entry-point library routine** needs a model this
   census doesn't have (shared bodies with multiple thunk entry points) —
   likely resolved for free once the library-scanning work's own module
   boundaries are consulted, rather than re-derived here.
