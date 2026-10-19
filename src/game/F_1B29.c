/*
 * F_1B29 -- draw_masked_sprite
 * cs [0x1929,0x1984) / file [0x1b29,0x1b84), 91 bytes.
 *
 * Per-video-mode dispatch of (x, y, sprite, mask) to the masked sprite
 * blitter (used for Dave and the help-screen monsters).
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 */

extern int D_4F86;
void F_88FD(int, int, int, int);
void F_8525(int, int, int, int);
void F_8778(int, int, int, int);

void F_1B29(int a, int b, int c, int d)
{
    switch (D_4F86) {
    case 0: F_88FD(a, b, c, d); break;
    case 1: F_8525(a, b, c, d); break;
    case 2: F_8778(a, b, c, d); break;
    }
}
