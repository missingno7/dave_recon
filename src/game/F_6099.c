/* @flags -G */
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
