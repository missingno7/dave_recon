/*
 * @behaviour: far data and far pointers in the small model. EVERY `far`
 *   variable (initialised or not) gets its own segment named
 *   <MODULE><n>_FAR, class FAR_DATA, paragraph aligned, the variable at
 *   offset 0 -- so in the linked EXE each far array starts on a paragraph
 *   and code addresses it as SEG:0 (the original's 7 far blobs at paragraphs
 *   0x0b31, 0x0c42, 0x11ef, 0x1c2e, 0x1d58, 0x1e84, 0x20cc, see
 *   orig_F1321_hugefar). Element access: `mov ax,SEG; mov bx,i; mov es,ax;
 *   mov al,es:[bx+OFF]`. `return farray;` is `mov dx,SEG; mov ax,OFF`.
 *   A near address converted to far: `mov [bp-4],OFF; mov [bp-2],ds`.
 *   Dereferencing a far pointer variable: `les bx,[p]; ... es:[bx]`.
 *   Initialised near data is _DATA (class DATA, word aligned SEGDEF);
 *   uninitialised near data _BSS (class BSS) -- both in DGROUP.
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. b8 .. .. 8b
 *   5e 04 8e c0 26 8a 87 .. .. eb 00 5d c3 55 8b ec
 *   39 26 .. .. 72 03 e8 .. .. ba .. .. b8 .. .. eb
 *   00 5d c3 55 8b ec 39 26 .. .. 72 03 e8 .. .. b8
 *   .. .. 8b 5e 04 8e c0 26 c6 87 .. .. 01 5d c3 55
 *   8b ec 83 ec 04 39 26 .. .. 72 03 e8 .. .. c7 46
 *   fc .. .. 8c 5e fe c4 5e fc 26 8b 07 eb 00 8b e5
 *   5d c3
 * @expect-segs: _TEXT CODE byte 114
 *   _DATA DATA word 2
 *   _BSS BSS word 2
 *   MOD5_FAR FAR_DATA para 4
 *   MOD6_FAR FAR_DATA para 3
 *   MOD7_FAR FAR_DATA para 10
 * @asm-contains: mov word ptr [bp - 2], ds
 *   mov es, ax
 *   les bx, ptr [bp - 4]
 */
char far tiles[4] = {1, 2, 3, 4};
char far tiles2[3] = {5, 6, 7};
char far scratch[10];
int near_init = 9;
int near_bss;

char get(int i)
{
    return tiles[i];
}

char far *addr(void)
{
    return tiles2;
}

void put(int i)
{
    scratch[i] = 1;
}

int via_far(void)
{
    int far *p = (int far *)&near_bss;
    return *p;
}
