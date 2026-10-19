/*
 * @behaviour: switch code generation. The case values are sorted, then
 *   recursively: a run of <= 3 cases is a compare chain (`or ax,ax` for 0,
 *   `cmp ax,imm; je` otherwise, then `jmp default`); a run of >= 4 cases
 *   whose value range (max-min+1) is <= 3*n+1 is a jump table
 *   (`mov bx,x; [dec bx | sub bx,min]; cmp bx,range-1; ja default;
 *   shl bx,1; jmp word ptr cs:[bx+TABLE]`) whose words are emitted in _TEXT
 *   right after the function's `ret` (holes point at default); otherwise the
 *   run is split at the middle element: `cmp ax,mid; je; jg upper-half`,
 *   lower half falls through. A long selector searches a CS-resident value
 *   table with `loop` and then `jmp cs:[bx+...]`. A char selector is widened
 *   with cbw first. Case bodies always stay in source order.
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. 8b 46 04 0b
 *   c0 74 14 3d 01 00 74 17 3d 02 00 74 02 eb 18 c7
 *   06 .. .. 01 00 eb 18 c7 06 .. .. 02 00 eb 10 c7
 *   06 .. .. 03 00 eb 08 c7 06 .. .. 63 00 eb 00 5d
 *   c3 55 8b ec 39 26 .. .. 72 03 e8 .. .. 8b 5e 04
 *   83 fb 03 77 27 d1 e3 2e ff a7 .. .. c7 06 .. ..
 *   01 00 eb 20 c7 06 .. .. 02 00 eb 18 c7 06 .. ..
 *   03 00 eb 10 c7 06 .. .. 04 00 eb 08 c7 06 .. ..
 *   63 00 eb 00 5d c3 .. .. .. .. .. .. .. .. 55 8b
 *   ec 39 26 .. .. 72 03 e8 .. .. 8b 5e 04 4b 83 fb
 *   04 77 27 d1 e3 2e ff a7 .. .. c7 06 .. .. 01 00
 *   eb 18 c7 06 .. .. 02 00 eb 10 c7 06 .. .. 03 00
 *   eb 08 c7 06 .. .. 04 00 eb 00 5d c3 .. .. .. ..
 *   .. .. .. .. .. .. 55 8b ec 39 26 .. .. 72 03 e8
 *   .. .. 8b 5e 04 83 eb 0a 83 fb 03 77 27 d1 e3 2e
 *   ff a7 .. .. c7 06 .. .. 01 00 eb 18 c7 06 .. ..
 *   02 00 eb 10 c7 06 .. .. 03 00 eb 08 c7 06 .. ..
 *   04 00 eb 00 5d c3 .. .. .. .. .. .. .. .. 55 8b
 *   ec 39 26 .. .. 72 03 e8 .. .. 8b 46 04 3d 64 00
 *   74 2a 7f 0c 3d 01 00 74 13 3d 0a 00 74 16 eb 34
 *   3d e8 03 74 1f 3d 88 13 74 22 eb 28 c7 06 .. ..
 *   01 00 eb 20 c7 06 .. .. 02 00 eb 18 c7 06 .. ..
 *   03 00 eb 10 c7 06 .. .. 04 00 eb 08 c7 06 .. ..
 *   05 00 eb 00 5d c3 55 8b ec 83 ec 04 39 26 .. ..
 *   72 03 e8 .. .. 8b 46 06 8b 56 04 89 56 fc 89 46
 *   fe b9 03 00 bb .. .. 2e 8b 07 3b 46 fc 75 09 2e
 *   8b 47 06 3b 46 fe 74 06 43 43 e2 eb eb 1c 2e ff
 *   67 0c c7 06 .. .. 01 00 eb 10 c7 06 .. .. 02 00
 *   eb 08 c7 06 .. .. 03 00 eb 00 8b e5 5d c3 00 00
 *   01 00 02 00 00 00 00 00 00 00 .. .. .. .. .. ..
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. 8a 46 04 98
 *   8b d8 83 fb 03 77 27 d1 e3 2e ff a7 .. .. c7 06
 *   .. .. 01 00 eb 18 c7 06 .. .. 02 00 eb 10 c7 06
 *   .. .. 03 00 eb 08 c7 06 .. .. 04 00 eb 00 5d c3
 *   .. .. .. .. .. .. .. ..
 * @asm-contains: or ax, ax
 *   cmp bx, 3
 *   dec bx
 *   sub bx, 0xa
 *   jg 0x
 *   loop 0x
 *   cwde
 */
int g;

void chain3(int x)
{
    switch (x) {
    case 2: g = 1; break;
    case 0: g = 2; break;
    case 1: g = 3; break;
    default: g = 99; break;
    }
}

void table4(int x)
{
    switch (x) {
    case 0: g = 1; break;
    case 1: g = 2; break;
    case 2: g = 3; break;
    case 3: g = 4; break;
    default: g = 99; break;
    }
}

void table_base1(int x)
{
    switch (x) {
    case 1: g = 1; break;
    case 2: g = 2; break;
    case 3: g = 3; break;
    case 5: g = 4; break;
    }
}

void table_base10(int x)
{
    switch (x) {
    case 10: g = 1; break;
    case 11: g = 2; break;
    case 12: g = 3; break;
    case 13: g = 4; break;
    }
}

void split(int x)
{
    switch (x) {
    case 1: g = 1; break;
    case 10: g = 2; break;
    case 100: g = 3; break;
    case 1000: g = 4; break;
    case 5000: g = 5; break;
    }
}

void longsel(long x)
{
    switch (x) {
    case 0: g = 1; break;
    case 1: g = 2; break;
    case 2: g = 3; break;
    }
}

void charsel(char c)
{
    switch (c) {
    case 0: g = 1; break;
    case 1: g = 2; break;
    case 2: g = 3; break;
    case 3: g = 4; break;
    }
}
