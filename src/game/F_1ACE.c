/*
 * F_1ACE -- save_background
 * cs [0x18ce,0x1929) / file [0x1ace,0x1b29), 91 bytes.
 *
 * Per-video-mode dispatch of (x, y, sprite, buffer) to the assembler routine
 * that saves the screen area under a sprite (F_1C6A passes Dave's
 * position and the buffer D_4C64).
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 * params 3 and 4 become DI and SI (loaded before the stack check).
 */

extern int D_4F86;
void F_89E6(int, int, int, int);
void F_86A9(int, int, int, int);
void F_8871(int, int, int, int);

void F_1ACE(int a, int b, int c, int d)
{
    switch (D_4F86) {
    case 0: F_89E6(a, b, c, d); break;
    case 1: F_86A9(a, b, c, d); break;
    case 2: F_8871(a, b, c, d); break;
    }
}
