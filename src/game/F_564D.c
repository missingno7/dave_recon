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
