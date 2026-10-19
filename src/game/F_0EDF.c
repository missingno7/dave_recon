/*
 * F_0EDF -- show_help
 * cs [0x0cdf,0x104b) / file [0xedf,0x124b), 876 bytes.
 *
 * The F1 help screen: three pages of text inside a window opened with
 * F_6EF1, each headed "dangerous dave" with two pairs of monster/item
 * sprites drawn by F_1B29 from the per-mode sprite table at DS 0x035E.
 * Page 1 lists the function keys, page 2 the goal and controls, page 3 the
 * hazards. SPACE advances, ESC leaves early (F_13FF redraws the screen).
 * @name show_help -- evidence: "f1 = help" text, the three text pages.
 *
 * Codegen notes: the literals are pooled in order of appearance starting at
 * DS 0x0923 (identical strings are NOT merged). `D_8A12 = D_8A22 += 2`
 * style chains reload the stored value (add [x],2; mov ax,[x]).
 */
/* @flags -G */
/* @seg _DATA 0x0923 */
#include <bios.h>
extern int D_8A12;
extern int D_8A14;
extern int D_8A22;
extern int D_4F86;
extern int D_035E[][3][4];      /* sprite ids [kind][gfx mode][frame] */
void F_6EF1(int, int);
void F_7071(char *);
void F_1B29(int, int, int, int);
void F_92D6(int, int, int);
void F_13FF(void);

void F_0EDF(void)
{
    int i;
    char c;

    for (i = 0; i < 0x1d; i += 7)
        F_6EF1(i, 0x14);
    D_8A22 += 2;
    D_8A12 = D_8A22;
    D_8A14 = 3;
    F_7071("     dangerous dave\r\n\n\n\n\n");
    F_1B29(0x4c, 0x10, D_035E[11][D_4F86][0], D_035E[12][D_4F86][0]);
    F_1B29(0xf0, 0x10, D_035E[9][D_4F86][0], D_035E[10][D_4F86][0]);
    for (i = 0; i < 13; i++)
        F_92D6(i + 4, 1, 3);
    F_7071("you use the keyboard,\r\n");
    F_7071("joystick or a mouse to\r\n");
    F_7071("to control dave.\r\n\n");
    F_7071("these are the function\r\n");
    F_7071("keys that are available\r\n");
    F_7071("at any time:\r\n\n");
    F_7071("f1 = help\r\n");
    F_7071("f2 = control panel\r\n");
    F_7071("f3 = restart game\r\n");
    F_7071("f9 = pause game\r\n");
    F_7071("f10 or esc = quit game\r\n\n");
    F_7071("   press space or esc");
    do {
        c = bioskey(0);
    } while (c != ' ' && c != 0x1b);
    if (c == 0x1b) {
        F_13FF();
        return;
    }

    F_6EF1(0x1c, 0x14);
    D_8A22++;
    D_8A12 = D_8A22;
    D_8A14 = 3;
    F_7071("       dangerous dave\r\n\n");
    F_1B29(0x4c, 0x10, D_035E[3][D_4F86][0], D_035E[4][D_4F86][0]);
    F_1B29(0xf0, 0x10, D_035E[5][D_4F86][0], D_035E[6][D_4F86][0]);
    F_7071("the object of the game is\r\n");
    F_7071("to guide dave through 10\r\n");
    F_7071("perilous areas in clyde's\r\n");
    F_7071("hideout. there are guns &\r\n");
    F_7071("jetpacks to aid you.\r\n\n");
    F_7071("in the control panel (f2),\r\n");
    F_7071("you will find the keyboard\r\n");
    F_7071("keys used for moving (they\r\n");
    F_7071("can be redefined). using\r\n");
    F_7071("the joystick or mouse, the\r\n");
    F_7071("left button will shoot and\r\n");
    F_7071("the right will turn on/off\r\n");
    F_7071("the jetpack.\r\n\n\n\n");
    F_7071("   press space or esc");
    do {
        c = bioskey(0);
    } while (c != ' ' && c != 0x1b);
    if (c == 0x1b) {
        F_13FF();
        return;
    }

    F_6EF1(0x1c, 0x14);
    D_8A22++;
    D_8A12 = D_8A22;
    D_8A14 = 3;
    F_7071("       dangerous dave\r\n\n");
    F_1B29(0x4c, 0x10, D_035E[7][D_4F86][0], D_035E[8][D_4F86][0]);
    F_1B29(0xf0, 0x10, D_035E[7][D_4F86][2], D_035E[8][D_4F86][2]);
    F_7071("watch out for fire, water\r\n");
    F_7071("and weirdweeds! these will\r\n");
    F_7071("toast dave very blackly!\r\n\n");
    F_7071("merely grab the trophy and\r\n");
    F_7071("walk through the door. it's\r\n");
    F_7071("that simple! of course, you\r\n");
    F_7071("might run into a few (?)\r\n");
    F_7071("monsters...\r\n\n");
    F_7071("also ... there are a few\r\n");
    F_7071("places dave can go by try-\r\n");
    F_7071("ing something strange and\r\n");
    F_7071("dangerous...\r\n\n\n");
    F_7071("        press space");
    do {
        c = bioskey(0);
    } while (c != ' ' && c != 0x1b);
    F_13FF();
}
