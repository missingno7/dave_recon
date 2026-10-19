# Turbo C++ 1.00 code generation: the rulebook for matching

Every rule here was established by compiling with the pinned Turbo C++ 1.00
(`toolchain/BIN/TCC.EXE`, under DOSBox-X) and, where possible, by reproducing a
real function of `build/DAVE_unpacked.exe` byte for byte. Each rule names the
case in `tools/codegen_lab/cases/` that demonstrates it; `python
tools/codegen_lab/run.py` re-checks all of them in about 5 seconds (one DOSBox-X
session), and `tests/test_codegen_catalog.py` runs it as part of the suite.
Nothing here is carried over from Turbo C 2.0 (duke1_recon) without being
re-tested; several of its rules turned out different (see the last section).

## The compiler profile

```
tcc -c -ms -1- -f- -N -G      (defaults left on: -r -u -b; off: -O -Z -K -a -d -p -k)
```

| Switch | Status | Evidence (original bytes, then the contrast that breaks them) |
|---|---|---|
| `-ms` | settled earlier | `docs/startup-binding-evidence.json` (C0S.OBJ is the only startup that fits) |
| `-N` | settled earlier | every game C function opens `39 26 9a 00 72 03 e8 ..` (stack check) |
| `-G` | **confirmed, new** | `_main` 0x4ce: 2-byte cleanup `44 44` (inc sp; inc sp); `-G-` gives `59` (pop cx). Also F_6EB9 0x6ec7: inner loop counter in SI (`8b 3e 28 8a` = mov di,[outer start]); `-G-` swaps SI/DI. Cases `orig_F0439_main`, `orig_F04D2_exit`, `orig_F6A26_loops`, `orig_F6EB9_G_regweight`, `orig_F0C34_scopy_long` all fail under `-G-`. |
| `-1-` | confirmed | F_0DFB 0xe20: `b8 01 00 50` (mov ax,1; push ax); `-1` emits `6a 01` (push imm) -- `orig_F0DFB_divmod`. No 186+ opcode (push imm, shl r,imm, enter/leave) occurs anywhere in 0x439..0x9613. |
| `-r` (default) | confirmed | F_1B84 0x1b89: `8b 7e 06 8b 76 08` loads register params; F_2D38/F_47F8/F_6A26/F_6EB9 keep locals in SI/DI; `-r-` puts them on the stack -- 5 orig cases fail under `-r-`. |
| no `-O` | confirmed | `_main` 0x478, F_1C28 0x1c66, F_2D38 0x2d81: `eb 00` (jmp to the next instruction) is kept; `-O` deletes it -- `orig_F0439_main`, `orig_F1C28_switch3`, `orig_F2D38_signedchar`, `orig_F47F8_structarray`, `orig_F6A26_loops`, `orig_F1321_hugefar`, `call_returns` fail under `-O`. |
| no `-K` | confirmed | F_2D38 0x2d76: `8a 01 98` (mov al,[bx+di]; cbw); F_0C34 0xd4e: `8a 46 f4 98`; F_07EB 0x820: `cmp byte [bp-1],0x20; jl` -- signed char. `-K` gives `b4 00` (mov ah,0) -- `orig_F2D38_signedchar`, `orig_F0C34_scopy_long`, `types_char_unsigned`. |
| no `-a` | confirmed | F_04FC 0x55b: `8b c6 ba 07 00 f7 ea` -- an array of 7-byte structs (char[3] + long); `-a` pads it to 8 -- `flag_a_struct7`. Also a word table at odd DGROUP offset 0x13dd (F_2D38 0x2d70). `-a` does NOT align functions, so odd function starts prove nothing either way. |
| no `-d` | confirmed | F_0EDF pushes `b8 26 0a` and `b8 b7 0b`: two copies of `"   press space or esc"` in one unit's pool (DGROUP 0xa26 and 0xbb7); likewise 0xa3c/0xbcd (F_0EDF) and `"corner and hit fire:"` at 0xfee/0x102f (both pushed by F_53C3) -- `flag_d_dupstrings` (`-d` merges them). |
| no `-p` | confirmed | caller-pops cleanup after every call, `ret` without operand; `-p` breaks `orig_F0439_main`, `orig_F04D2_exit`, `orig_F2D38_signedchar`, `orig_F0DFB_divmod`. |
| `-Z` | off (irrelevant) | `-Z` alone produces identical code (`flag_Z_needs_O`, and `orig_F0439_main` same-as `-Z`); it only acts together with `-O`, which is ruled out. `-O -Z` would also drop `_main`'s reload at 0x44e (`a3 c0 9e a1 c0 9e` becomes `a3 c0 9e 3d 03 00`). |
| `-k`, `-f`, `-y`, `-v` | unobservable | identical `_TEXT`/`_DATA` for integer code (`flag_unobservable`, `orig_F0439_main` same-as `-k`). Every function always gets `push bp; mov bp,sp`. The EXE contains no FP emulator, so `-f-` is kept. |
| `-u` (default) | required | the C0S startup calls `_main`: names must get the leading underscore. |
| `-b` (default) | unresolved | no enum-typed object identified yet; keep the default. |

**Matching workers: `tools/compile_probe.py` (and so `tools/match_function.py`)
still default to `-ms -1- -f- -N` -- pass `--flags "-G"` until that default is
updated.** Without `-G` every 2-byte argument cleanup and some register choices
come out wrong.

## Rules that decide the code

**Units and order.** Functions are emitted in source order with no padding
(`-a` does not change that). A call to any function of the same unit -- static,
earlier or later -- is `e8` with the displacement already resolved (no fixup),
so when matching one function in isolation declare its callees `extern`; then
every call displacement is a fixup and is accepted by `match_function.py`.
`static` functions have no PUBDEF.

**Frame.** Every function: `push bp; mov bp,sp`, then `dec sp; dec sp` (2 bytes
of locals) or `sub sp,N`, then `push si`/`push di` if used, then *register
parameter loads* (`mov si,[bp+N]`), then the stack check `cmp [__brklvl],sp;
jb +3; call N_OVERFLOW@`. Epilogue `pop di; pop si; [mov sp,bp;] pop bp; ret`
-- `mov sp,bp` only when there are stack locals. (`frame_locals_layout`,
`orig_F1B84_regparams`)

**Locals.** Allocated downward in declaration order: the first declared is
nearest BP. Anything but char goes to an even offset (one-byte holes appear),
the frame is rounded to even. Register candidates take no slot.
(`frame_locals_layout`, `orig_F0C34_scopy_long`: `num` at bp-6, `pad` at bp-0xc)

**Registers.** Candidates: int / unsigned / near-pointer locals whose address is
never taken (never char, long, far pointers, arrays). No `register` keyword is
needed. Order of preference: variables declared `register` first, then by use
count (every mention counts; with `-G` mentions inside loops weigh more). The
first gets SI, the second DI, the rest the stack; ties go to the *later*
declaration. Parameters become register variables when declared `register`, or
with >= 3 mentions, or (with `-G`) when used inside a loop; a pointer parameter
dereferenced twice qualifies. So: reordering declarations or adding a use can
swap SI and DI; renaming never matters. (`regalloc_rules`, `regalloc_G_loops`,
`orig_F6EB9_G_regweight`)

**Calls.** cdecl near calls, arguments pushed right to left, caller cleans up:
nothing for 0 bytes, `inc sp; inc sp` for 2, `add sp,N` for 4 or more. Constant
0 is `xor ax,ax; push ax`, other constants `mov ax,imm; push ax`, memory
operands `push word ptr [..]`, a long pushes its high word first, a char passed
to a prototyped `char` parameter is `mov al,..; push ax` (not widened).
Returns: AX, AL for char, DX:AX for long. `return expr;` always ends with a
`jmp` to the epilogue, `eb 00` when it is adjacent. (`call_cleanup`,
`call_returns`)

**Control flow.** `if (c) s` branches on the inverted condition around `s`;
`if (c) break;`/`continue;` is the inverted test around a `jmp` (`74 02 eb ..`),
never a direct conditional jump. Conditional jumps are short only; a distant
target becomes `jNcc +3; jmp near` (118 such pairs in the game). `while` and
`for` jump forward to a test at the bottom; `do` tests at the bottom; `for(;;)`
loops with `jmp`. Every `break` in a switch is a `jmp`, the last one `eb 00`.
(`expr_misc`, `orig_F6A26_loops`, `orig_F47F8_structarray`)

**switch.** Case values are sorted; then recursively: <= 3 cases make a compare
chain (`or ax,ax` for 0, else `cmp ax,imm; je`, finally `jmp default`); >= 4
cases with range (max-min+1) <= 3n+1 make a jump table (`mov bx,x;
[dec bx | sub bx,min]; cmp bx,range-1; ja default; shl bx,1; jmp cs:[bx+T]`,
the words placed in `_TEXT` right after the function's `ret`, holes pointing at
default); otherwise split at the middle value with `cmp ax,mid; je; jg upper`. A
long selector searches a CS value table with `loop`; a char selector is widened
with cbw first. Bodies always stay in source order. (`switch_forms`,
`switch_threshold`, `orig_F0439_main`, `orig_F1C28_switch3`,
`orig_F6D64_jumptable`; in the original the F_6D64 table sits at 0x6dba, right
after its `ret`)

**Types.** char is signed (cbw, signed jumps, `cmp byte ptr [x],imm` in
place); unsigned char widens with `mov ah,0`; unsigned int compares use
jb/ja/jbe/jae; int to long is cwd. Structs have no padding at all.
(`types_char_unsigned`, `types_struct_index`, `flag_a_struct7`)

**Arithmetic.** `x*2`, `x*4`, `x<<1..3` are repeated `shl ax,1`; shifts by 4+
are `mov cl,n; shl ax,cl`; other multipliers `mov dx,K; imul dx` (two variables:
`imul word ptr [g]`). Signed division is always `cwd; idiv` (even by 2); `>>` on
int is `sar`; unsigned `/2` becomes `shr`. A binary operation whose right side
needs AX/DX (a division, a call) evaluates and pushes the left side first, then
`pop dx; add dx,ax` (or `pop ax; add ax,dx` for `%`). `!x` is `neg ax;
sbb ax,ax; inc ax`; a boolean value is `mov ax,1; jmp; xor ax,ax`.
In-place `inc/dec/add/sub word ptr [g]` for `++ -- += -=`. (`expr_misc`,
`orig_F0DFB_divmod`, `orig_F0C34_scopy_long`)

**long.** `+ -` inline (add/adc, sub/sbb), compares high word first (signed) then
low word (unsigned). `*` N_LXMUL@ (DX:AX x CX:BX), `/ %` N_LDIV@ / N_LMOD@ /
N_LUDIV@ / N_LUMOD@ with both operands pushed (high words first), shifts
N_LXLSH@ / N_LXRSH@ / N_LXURSH@ (unsigned) with the value in DX:AX and the count
in CL. Huge-pointer arithmetic calls N_PADD@ (DX:AX + CX:BX). (`types_long_ops`, `orig_F0C34_scopy_long`,
`orig_F1321_hugefar`)

**Indexing.** Element size 2: `shl bx,1`; 4: two `shl bx,1`; anything else
`mov ax,i; mov dx,SIZE; imul dx; mov bx,ax`; the field offset is folded into
the displacement. Nothing is reused between statements (no CSE): every access
recomputes the address. 2-D `a[i][j]`: imul for the row, shl for the column,
add. (`types_struct_index`, `orig_F47F8_structarray`)

**Aggregates.** Initialised local arrays/structs and struct assignment call
SCOPY@ (`push ss|ds; push off; push ds; push off; mov cx,size`). The
initialiser image of a local is an anonymous object in `_DATA`.
(`orig_F0C34_scopy_long`, `expr_misc`)

**far and huge.** Every `far` variable gets its own segment `<UNIT><n>_FAR`,
class FAR_DATA, paragraph aligned, the object at offset 0 -- so each far array
in the EXE starts on a paragraph (the game's blobs at paragraphs 0x0b31, 0x0c42,
0x11ef, 0x1c2e, 0x1d58, 0x1e84, 0x20cc) and code addresses it as `SEG:0` through
an MZ relocation (`b8 58 1d` = mov ax,SEG). Element access `mov ax,SEG;
mov es,ax; es:[bx+OFF]`; `(T far *)&near_obj` is `mov [bp-4],OFF;
mov [bp-2],ds`; far pointer deref `les bx,[p]`. (`ptr_far_data`,
`orig_F1321_hugefar`, `orig_F6D64_jumptable`)

**_DATA.** Initialised variables (global, static, function-static, zero
initialisers too) in definition order, unpadded; the image of an initialised
local where its function is compiled; then all string literals of the unit in
order of appearance, duplicates kept. Moving a definition or a literal moves
bytes. (`data_order`, `flag_d_dupstrings`)

**_BSS.** Not declaration order. A unit's uninitialised variables are sorted by

    key = (n[0] + 256*n[1] + 8*n[len-2] + 64*len) mod 1024     (key = n[0] if len == 1)

over the C name without its underscore, ties in order of first appearance (an
earlier `extern` declaration counts). The last character never matters, so
names differing only there keep their order. Then everything except char and
char arrays is word aligned -- in `_BSS` only. Fitted on ~800 compiled names and
confirmed on 12 fresh random units (360 names, mixed types);
`python tools/codegen_lab/bss_order.py name:size ...` predicts a layout.
(`bss_order_hash`, `bss_ties_last_char`)

## Checking a change

```
python tools/codegen_lab/run.py                 # all cases, ~5 s
python tools/codegen_lab/run.py -k switch --show # one family, with disassembly
python tools/tcc_batch.py a.c b.c --flags "-ms -1- -f- -N -G"   # ad-hoc compiles
python tools/match_function.py cand.c 0xSTART 0xEND --flags "-G"
```

A new case is a `.c` file with an `@behaviour` header and one of `@original`,
`@expect-text` (filled by `--bless`), `@expect-data`, `@expect-bss`,
`@asm-contains`; `@contrast` lines must break it, `@same-as` lines must not
change it (format in `tools/codegen_lab/run.py`).

## Failed hypotheses

- Turbo C 2.0's `_BSS` key `(first + 4*last + 32*len) mod 1024` -- refuted: the
  last character has no effect at all; positions 0, 1 and len-2 plus the length
  decide (`bss_ties_last_char`). Also refuted along the way: declaration order,
  sum of characters, rolling hashes h*K+c / (h*K)^c for K < 300 in 8/16 bits,
  and the first/last/len family for any modulus up to 4096.
- "`_main`'s store-then-reload (`a3 c0 9e a1 c0 9e`) proves no `-Z`": `-Z`
  alone leaves it (and all other code) unchanged; only `-O -Z` removes it. It
  is evidence against `-O -Z`, not against `-Z`. (`a = b; c = b;` reloads `b`
  even under `-O -Z`.)
- "`_BSS` is unaligned like `_DATA`": ints in `_BSS` are word aligned even
  without `-a`.
- "a char argument is widened with cbw": not for a prototyped char parameter.
- "register variables follow the duke1 rule (SI to the highest weighted count,
  ties in declaration order)": ties go to the *later* declaration, explicit
  `register` beats any count, and loop weighting exists only with `-G`.
- "jump table needs dense cases": n = 4 cases spread over up to 13 values still
  get a table; the bound is range <= 3n+1.
- "`-a` aligns functions": it only pads data and structs.
- "a `register` keyword is needed for SI/DI": locals are auto-registered.
