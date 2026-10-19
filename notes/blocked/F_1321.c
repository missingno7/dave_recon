/* @flags -G */
/* @seg _DATA 0x0d5e */
extern char far FAR_1D58[];
extern char far FAR_0C42[];
extern char far FAR_1E84[];
extern char far FAR_20CC[];
extern char far FAR_11EF[];
extern int D_8B32;
extern int D_4F86;
extern char far *D_56F0;
void F_6099(char far *, int);
void F_7E00(char huge *, char far *, long);
void F_6ADE(char *, char far *);

void F_1321(void)
{
    char huge *p;

    switch (D_8B32) {
    case 1:
        F_6099(FAR_1D58, 0);
        p = FAR_0C42;
        F_7E00(p + 4, D_56F0, *(long huge *)p);
        break;
    case 2:
        F_6099(FAR_1E84, 0);
        F_6ADE("EGADAVE.DAV", D_56F0);
        break;
    case 3:
        F_6099(FAR_20CC, 0);
        p = FAR_11EF;
        F_7E00(p + 4, D_56F0, *(long huge *)p);
        break;
    }
    D_4F86 = D_8B32 - 1;
}
