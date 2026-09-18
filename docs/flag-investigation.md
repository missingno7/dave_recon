# Compiler flag investigation

## Memory model: small (`-ms`)

Established in `docs/startup-binding-evidence.json` /
`tools/recover_startup_binding.py`: comparing the game's C startup code
against all 5 Turbo C++ 1.00 memory-model startup objects, `C0S.OBJ`
(small) is the unique model where every differing byte is explained by a
linker fixup. `tools/compile_probe.py` now defaults to `--model s`.

## Stack overflow checking: `-N` (ON), not `-N-`

Empirically confirmed, not assumed from documentation.

**Evidence**: `_main` at file offset `0x439` opens with:

```
55 8B EC 39 26 9A 00 72 03 E8 ...
push bp
mov  bp, sp
cmp  word ptr [0x9A], sp   ; 0x9A is a fixup-resolved global (the stack limit)
jb   +3
call <stack-overflow handler>
```

Compiling `tests/fixtures/probe2.c` (a function with local variables) under
`-ms -1- -f- -N` produces, instruction for instruction:

```
55 8B EC 83 EC 1A 39 26 00 00 72 03 E8 00 00 ...
push bp
mov  bp, sp
sub  sp, 0x1A              ; (probe2 has locals; _main apparently has none)
cmp  word ptr [0], sp      ; unresolved fixup to the same stack-limit global
jb   +3
call <stack-overflow handler>
```

The only structural difference is the `sub sp,0x1A` (probe2 reserves stack
space for its locals; `_main` reserves none — plausible for a `main()` that
mostly just dispatches to other functions). Compiling the same probe with
`-N-` (checking off) omits the `cmp`/`jb`/`call` triplet entirely — see
`tools/compile_probe.py` git history / re-run with `--flags=-N-` to
reproduce. This is decisive: the game was built with stack checking **on**.

Regression-tested in `tests/test_flag_investigation.py`.

## Not yet determined

- `-1-` (no 80186/80286 instructions) and `-f-` (no floating point) were
  carried over from `empires_reconstruction`'s convention and have not been
  independently falsified or confirmed for this game. They are plausible
  defaults for a 1990 DOS game but should be revisited once a floating-point
  or 186+-instruction candidate function is found (if any).
- Optimization level (`-O`, register variable allocation, etc.) is
  completely unexplored. The `_main` prologue evidence above only bears on
  stack-check and memory model, not general optimization settings.
