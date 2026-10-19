/*
 * F_7005 -- wait_key_cursor
 * cs [0x6e05,0x6e71) / file [0x7005,0x7071), 108 bytes. Strict match: tools/match_function.py.
 *
 * Waits for a key while animating a blinking cursor (chars 9..12 with
 * delays) at the text cursor, erases it and returns bioskey(0).
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name wait_key_cursor
 */
/* @flags -G */
#include <bios.h>

extern int D_8A12, D_8A14;
void F_7878(int x, int y, int c);
void F_7831(void);

int F_7005(void)
{
    register int i, key;

    do {
        i = 9;
        while ((key = bioskey(1)) == 0 && i < 13) {
            F_7878(D_8A12, D_8A14, i++);
            F_7831();
            F_7831();
            F_7831();
            F_7831();
            F_7831();
        }
    } while (key == 0);
    F_7878(D_8A12, D_8A14, ' ');
    return bioskey(0);
}
