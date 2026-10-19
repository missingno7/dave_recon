/*
 * F_2C1F -- animate_tick()
 * cs [0x2a1f,0x2a70) / file [0x2c1f,0x2c70), 81 bytes.
 * Strict match: tools/match_function.py.
 *
 * Frame-rate divider for a 4-frame animation: the countdown at DS:0x6548 is
 * decremented and, when it reaches zero, reloaded with 2 and the frame index
 * DS:0x6150 advances modulo 4. The new frame then selects two words from
 * the 2-D int tables [?][4] at DS:0x0406 and DS:0x041E, row DS:0x4F86,
 * stored to DS:0x573E and DS:0x57E4 (likely the current sprite/tile ids of
 * some animated object; the row is probably a direction/state).
 *
 * @name animate_tick (tentative: only structure is known)
 *
 * Codegen notes: `x++; x = x & 3;` gives `inc [x]; mov ax,[x]; and ax,3;
 * mov [x],ax` (no register-load suppression). The index is written flat,
 * `t[row * 4 + i]`: that gives `shl bx,1; shl bx,1; add bx,i; shl bx,1`,
 * whereas a true 2-D `t[row][i]` scales row and column separately.
 */


extern int D_6548;              /* animation countdown */
extern int D_6150;              /* animation frame 0..3 */
extern int D_4F86;              /* table row (state/direction) */
extern int D_0406[];
extern int D_041E[];
extern int D_573E;
extern int D_57E4;

void F_2C1F(void)
{
    if (--D_6548 == 0) {
        D_6548 = 2;
        D_6150++;
        D_6150 = D_6150 & 3;
        D_573E = D_0406[D_4F86 * 4 + D_6150];
        D_57E4 = D_041E[D_4F86 * 4 + D_6150];
    }
}
