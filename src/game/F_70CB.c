/*
 * F_70CB -- print_int
 * cs [0x6ecb,0x6ef8) / file [0x70cb,0x70f8), 45 bytes. Strict match: tools/match_function.py.
 *
 * itoa(n) then print_string.
 *
 * Codegen: Calls itoa/ltoa without a prototype (no <stdlib.h>).
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name print_int
 */

void F_7071(char *s);

void F_70CB(int n)
{
    char buf[20];

    itoa(n, buf, 10);
    F_7071(buf);
}
