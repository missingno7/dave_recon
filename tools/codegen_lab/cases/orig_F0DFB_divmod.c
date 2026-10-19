/*
 * @behaviour: REAL FUNCTION F_0DFB (file 0xdfb..0xe57). Constant arguments
 *   are `mov ax,imm; push ax` (no 186 `push imm`: -1-). `a + b/10` where the
 *   right operand needs AX/DX: the left operand is evaluated first and
 *   PUSHED, then `cwd; idiv bx`, then `pop dx; add dx,ax`; for `%` the
 *   remainder is in DX so it is `pop ax; add ax,dx`. Indexing an int array
 *   by an int global: `mov bx,[g]; shl bx,1; mov ax,[bx+arr]`.
 * @original: 0xdfb 0xe57
 * @contrast: -1        # 80186: push imm
 *   -p
 */
extern int g_4f86, g_56f4;
extern int g_1ea[];
void f_1984(int, int, int);

void f0dfb(void)
{
    f_1984(0xb0, 1, g_1ea[g_4f86] + (g_56f4 + 1) / 10);
    f_1984(0xb8, 1, g_1ea[g_4f86] + (g_56f4 + 1) % 10);
}
