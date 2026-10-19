/*
 * F_1321 -- load_graphics()
 * cs [0x1121,0x11ff) / file [0x1321,0x13ff), 222 bytes. EXACT (strict, 30
 * fixups incl. five far-segment references checked against MZ relocations).
 *
 * Per video mode (D_8B32: 1 CGA, 2 EGA, 3 VGA) passes the mode's
 * config-screen graphics segment to F_6099 (setup_graphics_pointers), then
 * loads the tileset into the far graphics buffer D_56F0:
 *   CGA/VGA: RLE-decompresses (F_7E00) the tileset linked into the EXE
 *            (far segments 0C42 / 11EF; first dword = unpacked length);
 *   EGA:     reads EGADAVE.DAV from disk (F_6ADE).
 * Finally D_4F86 (graphics index) = video mode - 1.
 *
 * @name load_graphics
 * Far segments (docs/data-layout.md): 1D58/1E84/20CC CGA/EGA/VGA config
 * graphics, 0C42 CGA tileset, 11EF VGA tileset.
 */
/* @seg _DATA 0x0d5e */
extern char far P1D58_0000[];
extern char far P0C42_0000[];
extern char far P1E84_0000[];
extern char far P20CC_0000[];
extern char far P11EF_0000[];
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
        F_6099(P1D58_0000, 0);
        p = P0C42_0000;
        F_7E00(p + 4, D_56F0, *(long huge *)p);
        break;
    case 2:
        F_6099(P1E84_0000, 0);
        F_6ADE("EGADAVE.DAV", D_56F0);
        break;
    case 3:
        F_6099(P20CC_0000, 0);
        p = P11EF_0000;
        F_7E00(p + 4, D_56F0, *(long huge *)p);
        break;
    }
    D_4F86 = D_8B32 - 1;
}
