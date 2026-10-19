/*
 * F_564D -- print_key_name
 * cs [0x544d,0x5615) / file [0x564d,0x5815), 456 bytes. Strict match: tools/match_function.py.
 *
 * Prints the name of a keyboard scan code (bit 7 masked) at the text cursor:
 * named keys (ESC, BKSP, TAB, CTRL, ... NUMLK), F1-F10 as 'F' + itoa(n),
 * otherwise the ASCII char from the scan-code table D_0F12 via F_7878 at
 * (D_8A12++, D_8A14). Preserves the original quirk that scan code 0x59 (not
 * 0x58) is labelled F12.
 *
 * Evidence for the name: called by config_keyboard for each configured key;
 * string table of key names.
 *
 * Codegen: `key = key & 0x7f` (not `&=`) gives mov ax,si / and / mov si,ax.
 * Long if/else-if chain = compare chain with near jmps to the epilogue.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name print_key_name
 */
/* @flags -G */
/* @seg _DATA 0x10c4 */
extern int D_8A12, D_8A14;
extern char D_0F12[];
void F_7071(char *s);
void F_7878(int x, int y, int c);

void F_564D(register int key)
{
    char buf[4];

    key = key & 0x7f;
    if (key == 1)
        F_7071("ESC");
    else if (key == 14)
        F_7071("BKSP");
    else if (key == 15)
        F_7071("TAB");
    else if (key == 29)
        F_7071("CTRL");
    else if (key == 42)
        F_7071("LSHIFT");
    else if (key == 57)
        F_7071("SPACE");
    else if (key == 58)
        F_7071("CAPSLK");
    else if (key >= 59 && key <= 68) {
        F_7071("F");
        itoa(key - 58, buf, 10);
        F_7071(buf);
    } else if (key == 87)
        F_7071("F11");
    else if (key == 89)
        F_7071("F12");
    else if (key == 70)
        F_7071("SCRLLK");
    else if (key == 28)
        F_7071("ENTER");
    else if (key == 54)
        F_7071("RSHIFT");
    else if (key == 55)
        F_7071("PRTSC");
    else if (key == 56)
        F_7071("ALT");
    else if (key == 71)
        F_7071("HOME");
    else if (key == 73)
        F_7071("PGUP");
    else if (key == 79)
        F_7071("END");
    else if (key == 81)
        F_7071("PGDN");
    else if (key == 82)
        F_7071("INS");
    else if (key == 83)
        F_7071("DEL");
    else if (key == 69)
        F_7071("NUMLK");
    else
        F_7878(D_8A12++, D_8A14, D_0F12[key]);
}
