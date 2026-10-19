/*
 * F_6A26 -- flush_keyboard
 * cs [0x6826,0x6862) / file [0x6a26,0x6a62), 60 bytes. Strict match: tools/match_function.py.
 *
 * Drains the BIOS keyboard buffer (bioskey) and clears the key-state table
 * D_8A32.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name flush_keyboard
 */
/* @flags -G */
#include <bios.h>

extern int D_8A32[];

void F_6A26(void)
{
    register int i;

    while (bioskey(1))
        bioskey(0);
    for (i = 0; i < 128; i++)
        D_8A32[i] = 0;
}
