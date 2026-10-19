/*
 * F_156E -- show_cga_picture
 * cs [0x136e,0x13a5) / file [0x156e,0x15a5), 55 bytes.
 *
 * Sets CGA mode 4, copies 16 KB to B800:0000 with movedata() from a local
 * far pointer that is never initialised (a bug in the original, kept), then
 * waits for a key.
 * @name show_cga_picture -- evidence: CGA mode + 0x4000-byte copy to B800.
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 * the uninitialised `char far *p` occupies [bp-4]/[bp-2].
 */

#include <dos.h>
#include <mem.h>
#include <bios.h>

void F_156E(void)
{
    char far *p;

    _AX = 4; geninterrupt(0x10);
    movedata(FP_SEG(p), FP_OFF(p), 0xb800, 0, 0x4000);
    bioskey(0);
}
