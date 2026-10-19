/*
 * F_1A90 -- restore_background
 * cs [0x1890,0x18ce) / file [0x1a90,0x1ace), 62 bytes.
 *
 * Per-video-mode dispatch (D_4F86: 0 CGA, 1 EGA, 2 VGA) to the assembler
 * routine that restores a saved background buffer.
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 */
/* @flags -G */
extern int D_4F86;
void F_8994(int);
void F_862A(int);
void F_882C(int);

void F_1A90(int x)
{
    switch (D_4F86) {
    case 0: F_8994(x); break;
    case 1: F_862A(x); break;
    case 2: F_882C(x); break;
    }
}
