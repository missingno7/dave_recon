/* @flags -G */
struct input {
    int dir;
    int fire;
    int jump;
};

extern int D_8A32[];
extern char D_1310[];

struct input F_63AF(void)
{
    struct input in;
    register int dx, dy;

    dx = 0;
    dy = 0;
    if (D_8A32[D_1310[0]])
        dy = -1;
    if (D_8A32[D_1310[2]])
        dx = 1;
    if (D_8A32[D_1310[4]])
        dy = 1;
    if (D_8A32[D_1310[6]])
        dx = -1;
    if (D_8A32[D_1310[1]]) {
        dy = -1;
        dx = 1;
    }
    if (D_8A32[D_1310[7]]) {
        dy = -1;
        dx = -1;
    }
    if (D_8A32[D_1310[3]]) {
        dy = 1;
        dx = 1;
    }
    if (D_8A32[D_1310[5]]) {
        dy = 1;
        dx = -1;
    }
    switch (dy * 3 + dx) {
    case -4: in.dir = 7; break;
    case -3: in.dir = 0; break;
    case -2: in.dir = 1; break;
    case -1: in.dir = 6; break;
    case 0: in.dir = 8; break;
    case 1: in.dir = 2; break;
    case 2: in.dir = 5; break;
    case 3: in.dir = 4; break;
    case 4: in.dir = 3; break;
    }
    in.fire = D_8A32[D_1310[8]];
    in.jump = D_8A32[D_1310[9]];
    return in;
}
