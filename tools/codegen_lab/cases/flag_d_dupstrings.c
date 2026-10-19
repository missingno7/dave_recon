/*
 * @behaviour: No -d (duplicate string merging). Every string literal is its
 *   own copy in _DATA, in order of appearance, AFTER the unit's initialised
 *   variables (here `msg` at offset 0 points at the 4th literal).
 *   ORIGINAL EVIDENCE: F_0EDF pushes 0xa26 and 0xbb7, two separate copies of
 *   "   press space or esc" (DGROUP 0xa26 and 0xbb7, file 0x260f6/0x26287),
 *   and 0xa3c / 0xbcd, two copies of "       dangerous dave\r\n\n".
 * @expect-data:
 *   14 00 68 65 6c 6c 6f 00 77 6f 72 6c 64 00 68 65
 *   6c 6c 6f 00 77 6f 72 6c 64 00
 * @contrast: -d
 */
void puts(char *);

void show(void)
{
    puts("hello");
    puts("world");
    puts("hello");
}

char *msg = "world";
