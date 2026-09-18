/*
 * F_6D64 -- file offset [0x6d64, 0x6d8a) of build/DAVE_unpacked.exe.
 *
 * PROVEN (by tools/match_function.py, see docs/matching-evidence.json):
 * this file, compiled with the pinned Turbo C++ 1.00 toolchain under
 * -ms -1- -f- -N (tools/compile_probe.py's defaults), reproduces the
 * declared 38-byte range byte-for-byte with zero unexplained differences.
 * Every differing byte falls on a FIXUPP-declared location (the stack-check
 * global, the stack-check handler call, the near-to-far pointer's segment
 * reference, and the switch jump-table address) -- the same "match modulo
 * fixups" standard used for STARTUP_C0S and the CS.LIB promotions in
 * layout/manifest.json.
 *
 * What the disassembly of the real bytes independently shows:
 *   push bp; mov bp,sp; sub sp,4         -- one 4-byte (far pointer) local
 *   [-N stack-overflow check, as everywhere else in this binary]
 *   mov word ptr [bp-4], 0x143a          -- offset half of a far pointer,
 *                                            fixup-covered (an address-of on
 *                                            a near global/static)
 *   mov word ptr [bp-2], ds              -- segment half of the same far
 *                                            pointer (near-to-far promotion
 *                                            combines the known offset with
 *                                            the runtime DS register)
 *   mov bx, [bp+4]                       -- the function's one parameter
 *   cmp bx, 3 ; ja <default/end>         -- range-check against 4 cases
 *   shl bx, 1 ; jmp word ptr cs:[bx+tbl] -- classic compiled switch(x)
 *                                            with a 4-entry jump table
 *
 * NOT proven and NOT claimed: the identity of the near global the far
 * pointer refers to, the parameter's name/meaning, or the four case
 * bodies' actual behavior. The census boundary this range comes from
 * (docs/function-census.json's F_6D64, [0x6d64,0x6d8a)) is only the
 * switch's *dispatch head* -- a naive prologue/RET scan cuts off here
 * because the real function has no RET in this span (it ends in an
 * indirect JMP through the table instead). The real case bodies and the
 * jump table itself live immediately afterward (file offsets
 * ~0x6d8a-0x6dba) and remain RAW_UNKNOWN; they are a good next candidate
 * for a follow-up promotion once their own semantics are independently
 * disassembled and understood, but are NOT reconstructed here.
 *
 * The struct/global names and the four case bodies below are placeholders
 * chosen only so the dispatch head's exact byte pattern comes out right
 * (in particular, the case bodies' total compiled size -- not their
 * content -- has to match the real binary's, or the "ja" out-of-range
 * branch's displacement byte, which is NOT fixup-covered, would differ).
 * They are deliberately not claimed as accurate; only file offset
 * [0x6d64,0x6d8a) is promoted to MATCHING_C by this source.
 */

struct GameStuff { char data[4]; };
struct GameStuff huge_thing;

void f6d64(int which)
{
    struct GameStuff far *p = (struct GameStuff far *)&huge_thing;

    switch (which) {
    case 0: p->data[0] = 0; p->data[2] = 5; break;
    case 1: p->data[0] = 1; break;
    case 2: p->data[0] = 2; break;
    case 3: p->data[0] = 3; break;
    }
}
