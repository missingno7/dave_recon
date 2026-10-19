/*
 * @behaviour: REAL FUNCTION F_0C34 (file 0xc34..0xdfb, 455 bytes). An
 *   initialised local array is copied from an anonymous _DATA image with
 *   SCOPY@ (`push ss; lea ax,[bp-6]; push ax; push ds; mov ax,OFF; push ax;
 *   mov cx,6; call SCOPY@`), one call per array, in declaration order; the
 *   first-declared local gets the highest address (bp-6, then bp-0xc).
 *   unsigned long: `a - b >= K` is sub/sbb then a high-word-first unsigned
 *   compare (or ax,ax; jb; jne; cmp dx,K; jb); `/` calls LUDIV@ with the
 *   operands pushed, `*` calls LXMUL@ with DX:AX * CX:BX (pop cx; pop bx);
 *   `x > 99999L` compares the high word (cmp ..,1; jb; ja) then the low word
 *   (jbe). `g * h` of two ints is `mov ax,[g]; imul word ptr [h]`, `x << 4`
 *   is `mov cl,4; shl ax,cl` (8086), char + int is cbw then add.
 *   Two-statement form `b = s; b = b / K * K;` is what the bytes show.
 * @original: 0xc34 0xdfb
 * @expect-data:
 *   00 00 00 00 00 00 30 30 30 30 30 00
 * @contrast: -G-
 *   -K
 */
extern unsigned long g_score, g_bonus;
extern int g_lives, g_208, g_4f86;
extern int g_216[], g_1ea[];
void f_19d6(int, int, int);
void f_743e(int);
void f_1984(int, int, int);
char *ultoa(unsigned long, char *, int);
unsigned strlen(char *);
void movmem(void *, void *, unsigned);

void f0c34(void)
{
    char num[6] = "";
    char pad[6] = "00000";

    if (g_score - g_bonus >= 20000) {
        g_bonus = g_score;
        g_bonus = g_bonus / 20000 * 20000;
        if (g_lives < 3) {
            f_19d6((g_lives << 4) + 0x100, 0, g_216[g_208 * g_4f86]);
            g_lives++;
            f_743e(12);
        }
    }
    if (g_score > 99999L)
        g_score = 99999L;
    ultoa(g_score, num, 10);
    movmem(num, &pad[5 - strlen(num)], strlen(num));
    f_1984(0x40, 1, g_1ea[g_4f86] + pad[0] - '0');
    f_1984(0x48, 1, g_1ea[g_4f86] + pad[1] - '0');
    f_1984(0x50, 1, g_1ea[g_4f86] + pad[2] - '0');
    f_1984(0x58, 1, g_1ea[g_4f86] + pad[3] - '0');
    f_1984(0x60, 1, g_1ea[g_4f86] + pad[4] - '0');
}
