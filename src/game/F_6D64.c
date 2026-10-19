/*
 * F_6D64 -- set_video_mode(mode)
 * cs [0x6b64,0x6bc2) / file [0x6d64,0x6dc2), 94 bytes incl. the 4-entry
 * switch jump table. Strict match: tools/match_function.py.
 *
 * mode 0: BIOS text mode 3
 * mode 1: CGA 320x200x4 (mode 4)
 * mode 2: EGA 320x200x16 (mode 0Dh), then F_6213
 * mode 3: VGA 320x200x256 (mode 13h), then INT 10h AX=1012h loads all 256
 *         DAC registers from the palette at DS:0x143A
 *
 * Codegen note: `_ES = FP_SEG(p); _DX = FP_OFF(p);` compiles to a single
 * `les dx,[bp-4]`; every `break` emits a jmp to the epilogue, even the last
 * one (eb 00), because jump optimisation is off.
 */
#include <dos.h>

extern unsigned char D_143A[];          /* VGA palette, 256 x RGB */
void F_6213(void);

void F_6D64(int mode)
{
    unsigned char far *pal = D_143A;

    switch (mode) {
    case 0: _AX = 3; geninterrupt(0x10); break;
    case 1: _AX = 4; geninterrupt(0x10); break;
    case 2: _AX = 0xd; geninterrupt(0x10); F_6213(); break;
    case 3: _AX = 0x13; geninterrupt(0x10);
        _ES = FP_SEG(pal); _DX = FP_OFF(pal); _BX = 0; _CX = 0x100; _AX = 0x1012;
        geninterrupt(0x10);
        break;
    }
}
