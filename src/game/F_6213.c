/*
 * F_6213 -- ega_upload_planes
 * cs [0x6013,0x6093) / file [0x6213,0x6293), 128 bytes. Strict match: tools/match_function.py.
 *
 * Copies the four EGA tile planes (segments D_65A8[0..3], size (D_65AA -
 * D_65A8[0]) paragraphs) into video memory at A200:0000, selecting each
 * plane with sequencer map mask (3C4h index 2), then re-enables all four
 * planes.
 *
 * Evidence for the name: outportb 0x3C4/0x3C5 map mask, movedata to segment
 * 0xA200; called after setting EGA mode.
 *
 * Codegen: `int i` stays on the stack (no auto register allocation here).
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name ega_upload_planes
 */

#include <dos.h>
#include <mem.h>

extern unsigned D_65A8[];
extern unsigned D_65AA;

void F_6213(void)
{
    int i;

    for (i = 0; i < 4; i++) {
        outportb(0x3c4, 2);
        outportb(0x3c5, 1 << i);
        movedata(D_65A8[i], 0, 0xa200, 0, (D_65AA - D_65A8[0]) << 4);
    }
    outportb(0x3c4, 2);
    outportb(0x3c5, 0xf);
}
