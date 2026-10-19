/*
 * @behaviour: Switches with no observable effect on integer code in the small
 *   model: -k (standard stack frame: every function already gets
 *   push bp; mov bp,sp, even with no locals and no parameters), -f
 *   (floating point emulation: integer-only units are unchanged; the game
 *   links no FP emulator, so -f- is kept), -y/-v (debug info goes to
 *   separate OMF records, code identical), -b- (enums: none here).
 *   An empty function still gets a frame and the -N stack check.
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. 5d c3 55 8b
 *   ec 39 26 .. .. 72 03 e8 .. .. e8 .. .. 5d c3 55
 *   8b ec 39 26 .. .. 72 03 e8 .. .. 8b 46 04 40 eb
 *   00 5d c3
 * @asm-contains: push bp
 *   mov bp, sp
 * @same-as: -k
 *   -f
 *   -y
 *   -v
 */
int g;
void h(void);

void empty(void)
{
}

void calls(void)
{
    h();
}

int add1(int x)
{
    return x + 1;
}
