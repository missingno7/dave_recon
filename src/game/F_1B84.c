/*
 * F_1B84 -- draw_tile
 * cs [0x1984,0x19d6) / file [0x1b84,0x1bd6), 82 bytes.
 *
 * Per-video-mode dispatch of (x, y, tile) to the opaque tile blitter (the
 * CGA one writes straight to B800); used for score/level digits.
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 */
/* @flags -G */
extern int D_4F86;
void F_8E5E(int, int, int);
void F_8B9F(int, int, int);
void F_8D17(int, int, int);

void F_1B84(int a, int b, int c)
{
    switch (D_4F86) {
    case 0: F_8E5E(a, b, c); break;
    case 1: F_8B9F(a, b, c); break;
    case 2: F_8D17(a, b, c); break;
    }
}
