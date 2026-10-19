/*
 * @behaviour: _DATA order. Initialised variables (globals, file statics and
 *   function statics alike) are emitted in definition order with NO
 *   alignment padding (an int may sit at an odd offset), explicit zero
 *   initialisers included (they stay in _DATA, not _BSS). String literals
 *   come after ALL initialised variables of the unit, in order of
 *   appearance in the source (a pointer initialised with a literal points
 *   into that trailing pool). The anonymous image of an initialised LOCAL
 *   array/struct (copied with SCOPY@) is NOT a literal: it is emitted like a
 *   variable, at the point where its function is compiled.
 *   Layout here: c1@0 i1@1 zero@3 st@5 fs@7, local image "xyz"@9,
 *   ptr@0xd, then the pool "lit-a"@0xf "lit-b"@0x15 "ptr"@0x1b.
 * @expect-data:
 *   01 02 00 00 00 03 00 04 00 78 79 7a 00 1b 00 6c
 *   69 74 2d 61 00 6c 69 74 2d 62 00 70 74 72 00
 * @expect-text:
 *   55 8b ec 83 ec 04 39 26 .. .. 72 03 e8 .. .. 16
 *   8d 46 fc 50 1e b8 .. .. 50 b9 04 00 e8 .. .. b8
 *   .. .. 50 e8 .. .. 44 44 8d 46 fc 50 e8 .. .. 44
 *   44 b8 .. .. 50 e8 .. .. 44 44 ff 06 .. .. ff 06
 *   .. .. 8b e5 5d c3
 */
void use(char *);

char c1 = 1;
int i1 = 2;
int zero = 0;
static int st = 3;

void f(void)
{
    static int fs = 4;
    char loc[4] = "xyz";
    use("lit-a");
    use(loc);
    use("lit-b");
    fs++;
    st++;
}

char *ptr = "ptr";
