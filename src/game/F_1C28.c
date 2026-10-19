/*
 * F_1C28 -- erase_dave
 * cs [0x1a28,0x1a6a) / file [0x1c28,0x1c6a), 66 bytes.
 *
 * Per-video-mode restore of the background saved under Dave (buffer
 * D_4C64).
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 */
/* @flags -G */
extern int D_4F86;
extern unsigned char D_4C64[];
void F_8994(void *);
void F_862A(void *);
void F_882C(void *);

void F_1C28(void)
{
    switch (D_4F86) {
    case 0: F_8994(D_4C64); break;
    case 1: F_862A(D_4C64); break;
    case 2: F_882C(D_4C64); break;
    }
}
