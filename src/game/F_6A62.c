/*
 * F_6A62 -- farmalloc_aligned
 * cs [0x6862,0x68de) / file [0x6a62,0x6ade), 124 bytes. Strict match: tools/match_function.py.
 *
 * farmalloc(size + 15), remembered in D_9EC4; on failure restores text mode
 * and prints 'Out of memory!' then exits via F_04D2(1); returns the block
 * rounded up to a paragraph boundary (offset 0).
 *
 * Evidence for the name: string 'Out of memory!' (DS:0x131E), farmalloc.
 *
 * Codegen: The pointer is `huge` (NULL test via N_PCMP@). Normalisation
 * written as separate statements on register vars: `off = FP_OFF(p); if
 * (off) { seg = FP_SEG(p); seg++; off = 0; p = MK_FP(seg, off); }`.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name farmalloc_aligned
 */
/* @flags -G */
/* @seg _DATA 0x131e */
#include <stdio.h>
#include <dos.h>
#include <alloc.h>

extern void far *D_9EC4;
void F_6D64(int mode);
void F_04D2(int code);

void far *F_6A62(unsigned long size)
{
    void huge *p;
    register unsigned seg, off;

    D_9EC4 = p = farmalloc(size + 15);
    if (p == NULL) {
        F_6D64(0);
        puts("Out of memory!");
        F_04D2(1);
    }
    off = FP_OFF(p);
    if (off) {
        seg = FP_SEG(p);
        seg++;
        off = 0;
        p = MK_FP(seg, off);
    }
    return p;
}

