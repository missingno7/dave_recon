/*
 * F_1BD6 -- xor_sprite
 * cs [0x19d6,0x1a28) / file [0x1bd6,0x1c28), 82 bytes.
 *
 * Per-video-mode dispatch of (x, y, sprite) to the sprite blitter that is
 * used both to draw and to erase (F_18F6 draws the same frame twice).
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 */

extern int D_4F86;
void F_8D95(int, int, int);
void F_8A88(int, int, int);
void F_8C66(int, int, int);

void F_1BD6(int a, int b, int c)
{
    switch (D_4F86) {
    case 0: F_8D95(a, b, c); break;
    case 1: F_8A88(a, b, c); break;
    case 2: F_8C66(a, b, c); break;
    }
}
