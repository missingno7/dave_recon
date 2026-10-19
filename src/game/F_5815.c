/* @flags -G */
/* @seg _DATA 0x1133 */
extern int D_8A12, D_8A14;
extern int D_8A32[];
extern char D_1310[];
void F_6EF1(int w, int h);
void F_7071(char *s);
void F_7878(int x, int y, int c);
int F_7005(void);
void F_6EB9(void);
void F_6A26(void);
void F_564D(int key);

void F_5815(void)
{
    char c;
    int savex, savey, key;
    register int action, i;

    F_6EF1(22, 14);
    F_7071("Keyboard Configuration\n\r");
    F_7071("----------------------");
    F_7071("\n\r0 north    :");
    F_7071("\n\r1 northeast:");
    F_7071("\n\r2 east     :");
    F_7071("\n\r3 southeast:");
    F_7071("\n\r4 south    :");
    F_7071("\n\r5 southwest:");
    F_7071("\n\r6 west     :");
    F_7071("\n\r7 northwest:");
    F_7071("\n\r8 button1  :");
    F_7071("\n\r9 button2  :");
    F_7071("\n\n\rModify which action:");
    savex = D_8A12;
    savey = D_8A14;
    for (i = 0; i < 8; i++) {
        D_8A12 = 22;
        D_8A14 = i + 7;
        F_564D(D_1310[i]);
    }
    D_8A12 = 22;
    D_8A14 = 15;
    F_564D(D_1310[8]);
    D_8A12 = 22;
    D_8A14 = 16;
    F_564D(D_1310[9]);
    do {
        D_8A12 = savex;
        D_8A14 = savey;
        c = F_7005() % 256;
        if (c < '0' || c > '9')
            continue;
        action = c - '0';
        F_7878(D_8A12, D_8A14, c);
        action = c - '0';
        F_7071("\n\rPress the new key:");
        F_6A26();
        key = -1;
        while (!D_8A32[++key])
            if (key == 127)
                key = -1;
        F_6A26();
        F_7071("\r                  ");
        if (action < 8)
            D_1310[action] = key;
        if (action == 8)
            D_1310[8] = key;
        if (action == 9)
            D_1310[9] = key;
        D_8A14 = action + 7;
        D_8A12 = 22;
        F_7071("        ");
        D_8A12 = 22;
        F_564D(key);
        c = '0';
    } while (c >= '0' && c <= '9');
    F_6EB9();
}
