/*
 * @behaviour: REAL FUNCTION F_04D2 (file 0x4d2..0x4fc). `if (p == 0)` on a
 *   stack parameter compiles to `cmp word ptr [bp+4],0; jne` (83 7e 04 00),
 *   a constant 0 argument is `xor ax,ax; push ax`, a parameter argument is
 *   `push word ptr [bp+4]`; every 2-byte cleanup is `inc sp; inc sp`.
 *   A function with no locals ends `pop bp; ret` (no mov sp,bp).
 * @original: 0x4d2 0x4fc
 * @contrast: -G-
 *   -p
 */
void f_6188(void); void f_740f(void); void f_6b64(int); void exit(int);

void f04d2(int code)
{
    f_6188();
    f_740f();
    if (code == 0)
        f_6b64(0);
    exit(code);
}
