/*
 * F_70F8 -- print_long
 * cs [0x6ef8,0x6f25) / file [0x70f8,0x7125), 45 bytes. Strict match: tools/match_function.py.
 *
 * ltoa(n) then print_string - original bug: n is an int and ltoa is
 * unprototyped, so only one word is pushed.
 *
 * Codegen: No <stdlib.h>: ltoa called with an int argument.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name print_long
 */
/* @flags -G */
void F_7071(char *s);

void F_70F8(int n)
{
    char buf[20];

    ltoa(n, buf, 10);
    F_7071(buf);
}
