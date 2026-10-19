/*
 * F_6B94 -- write_file_far(name, buf, len)
 * cs [0x6994,0x6a1e) / file [0x6b94,0x6c1e), 138 bytes. EXACT (strict).
 *
 * Creates `name` (INT 21h AH=3Ch), writes `len` bytes from the far buffer
 * in 0x8000-byte chunks (buffer segment advanced by 0x800 each) and then
 * the remainder, and closes it. Used for DSCORES.DAV and demo saving.
 * The two locals initialised to 0 are never used (kept: they are in the
 * original frame).
 *
 * @name write_file_far
 * Original inline asm (see F_6ADE.c). The `eb 00` before `done:` is the
 * compiled `goto done;` -- with no jump optimisation TC emits the jump even
 * to the next statement.
 */
#include <dos.h>

void F_6B94(char *name, char far *buf, long len)
{
    int handle;
    unsigned off = FP_OFF(buf);
    unsigned seg = FP_SEG(buf);
    unsigned poslo = 0;
    unsigned poshi = 0;

    asm mov dx, name
    asm mov ax, 3c00h
    asm xor cx, cx
    asm int 21h
    asm jb done
    asm mov handle, ax
    asm cmp word ptr len+2, 0
    asm je last
big:
    asm push ds
    asm mov bx, handle
    asm mov cx, 8000h
    asm mov dx, off
    asm mov ax, seg
    asm mov ds, ax
    asm mov ah, 40h
    asm int 21h
    asm pop ds
    asm add seg, 800h
    asm sub word ptr len, 8000h
    asm sbb word ptr len+2, 0
    asm cmp word ptr len+2, 0
    asm ja big
    asm cmp word ptr len, 8000h
    asm jae big
last:
    asm push ds
    asm mov bx, handle
    asm mov cx, word ptr len
    asm mov dx, off
    asm mov ax, seg
    asm mov ds, ax
    asm mov ah, 40h
    asm int 21h
    asm pop ds
    goto done;
done:
    asm mov bx, handle
    asm mov ah, 3eh
    asm int 21h
}
