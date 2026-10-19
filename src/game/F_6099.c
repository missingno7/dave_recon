/*
 * F_6099 -- setup_graphics_pointers
 * cs [0x5e99,0x6013) / file [0x6099,0x6213), 378 bytes. Strict match: tools/match_function.py.
 *
 * Takes a loaded graphics file (header of far pointers relative to the file)
 * and derives runtime pointers: on EGA copies the four tile pointers and
 * computes the 4 plane segments D_65A8[i]; otherwise relocates the four
 * pointers to MK_FP(seg(file)+seg(ptr), 0). Then copies 64 16-byte and 256
 * 32-byte records (huge pointers into the file) to D_8604 and D_65FC.
 *
 * Evidence for the name: EGA plane segments D_65A8 are consumed by F_6213;
 * huge-pointer struct copies via N_PADD@/N_SCOPY@.
 *
 * Codegen: Huge pointers give N_LXLSH@ + N_PADD@ for indexing. MK_FP(seg,
 * off) evaluates seg first.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name setup_graphics_pointers
 */

#include <dos.h>

struct s16 { char b[16]; };
struct s32 { char b[32]; };

struct gfxhdr {
    char far *p0;
    char far *p1;
    char far *p2;
    char far *p3;
    char far *s16;
    char far *s32;
    char far *plane[4];
};

extern int D_8B32;
extern char far *D_8A16, far *D_8A2E, far *D_8A1E, far *D_8A1A;
extern unsigned D_65A8[];
extern struct s16 D_8604[];
extern struct s32 D_65FC[];

void F_6099(char far *data)
{
    struct gfxhdr far *hdr;
    struct s32 huge *p32;
    struct s16 huge *p16;
    register int i;

    hdr = (struct gfxhdr far *)data;
    if (D_8B32 == 2) {
        D_8A16 = hdr->p0;
        D_8A2E = hdr->p1;
        D_8A1E = hdr->p2;
        D_8A1A = hdr->p3;
        for (i = 0; i < 4; i++)
            D_65A8[i] = FP_SEG(hdr->plane[i]) + FP_SEG(hdr);
    } else {
        D_8A16 = MK_FP(FP_SEG(hdr) + FP_SEG(hdr->p0), 0);
        D_8A2E = MK_FP(FP_SEG(hdr) + FP_SEG(hdr->p1), 0);
        D_8A1E = MK_FP(FP_SEG(hdr) + FP_SEG(hdr->p2), 0);
        D_8A1A = MK_FP(FP_SEG(hdr) + FP_SEG(hdr->p3), 0);
    }
    p16 = MK_FP(FP_SEG(hdr->s16) + FP_SEG(hdr), FP_OFF(hdr->s16) + FP_OFF(hdr));
    p32 = MK_FP(FP_SEG(hdr->s32) + FP_SEG(hdr), FP_OFF(hdr->s32) + FP_OFF(hdr));
    for (i = 0; i < 64; i++)
        D_8604[i] = p16[i];
    for (i = 0; i < 256; i++)
        D_65FC[i] = p32[i];
}
