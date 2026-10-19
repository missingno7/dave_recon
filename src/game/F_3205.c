/*
 * F_3205 -- draw_object(i)
 * cs [0x3005,0x312c) / file [0x3205,0x332c), 295 bytes.
 * Strict match: tools/match_function.py.
 *
 * Draws record i of the 5-entry, 14-byte object table at DS:0x56F6 at its
 * (x, y) = words +2/+4. Word +0x0A selects the kind: kind 0 is animated
 * (sprite from DS:0x038E or, when word +6 is non-zero, DS:0x0376, indexed
 * DS:0x4F86 * 4 + frame (word +8)); kind 1 is static (sprite DS:0x01CC or,
 * when word +6 is non-zero, DS:0x01C6, indexed DS:0x4F86). Other kinds
 * draw nothing.
 *
 * @name draw_object
 */


struct obj {
    int active;
    int x;
    int y;
    int flag;
    int frame;
    int kind;
    int id;
};

extern struct obj D_56F6[];
extern int D_4F86;
extern int D_038E[];
extern int D_0376[];
extern int D_01CC[];
extern int D_01C6[];

void F_1BD6(int x, int y, int sprite);

void F_3205(int i)
{
    switch (D_56F6[i].kind) {
    case 0:
        if (D_56F6[i].flag == 0)
            F_1BD6(D_56F6[i].x, D_56F6[i].y, D_038E[D_4F86 * 4 + D_56F6[i].frame]);
        else
            F_1BD6(D_56F6[i].x, D_56F6[i].y, D_0376[D_4F86 * 4 + D_56F6[i].frame]);
        break;
    case 1:
        if (D_56F6[i].flag == 0)
            F_1BD6(D_56F6[i].x, D_56F6[i].y, D_01CC[D_4F86]);
        else
            F_1BD6(D_56F6[i].x, D_56F6[i].y, D_01C6[D_4F86]);
        break;
    }
}
