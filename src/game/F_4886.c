/*
 * F_4886 -- spawn_object(x, y, flag, kind, id)
 * cs [0x4686,0x4797) / file [0x4886,0x4997), 273 bytes.
 * Strict match: tools/match_function.py.
 *
 * Unless the level tile at pixel (x, y + 1) has attribute 1 (solid, via
 * F_2D38), takes the first free record of the 5-entry, 14-byte object table
 * at DS:0x56F6, fills it (active = 1, x, y, id, flag, frame = 0, kind) and
 * draws it once at (x, y) with the sprite F_3205 would use for it.
 *
 * @name spawn_object
 */
/* @flags -G */

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

int F_2D38(int x, int y, int dx, int dy);
void F_1BD6(int x, int y, int sprite);

void F_4886(int x, int y, int flag, int kind, int id)
{
    int base;
    int i;
    int sprite;

    base = D_4F86 * 4;
    if (F_2D38(x, y, 0, 1) == 1)
        return;
    for (i = 0; i < 5; i++) {
        if (D_56F6[i].active == 0) {
            D_56F6[i].active = 1;
            D_56F6[i].x = x;
            D_56F6[i].y = y;
            D_56F6[i].id = id;
            D_56F6[i].flag = flag;
            D_56F6[i].frame = 0;
            D_56F6[i].kind = kind;
            sprite = D_0376[base];
            if (flag == 0)
                sprite = D_038E[base];
            if (kind == 1) {
                sprite = D_01C6[D_4F86];
                if (flag == 0)
                    sprite = D_01CC[D_4F86];
            }
            F_1BD6(x, y, sprite);
            return;
        }
    }
}
