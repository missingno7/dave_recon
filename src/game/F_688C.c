/* @flags -G */
struct input {
    int dir;
    int fire;
    int jump;
};

extern int D_9EC2;
extern int D_12F0[];
extern char *D_8A2C;
struct input F_63AF(void);
struct input F_6505(void);
struct input F_66F2(int stick);

struct input F_688C(int player)
{
    struct input in;
    int packed;

    if (D_9EC2 == 0 || D_9EC2 == 2) {
        switch (D_12F0[player]) {
        case 0: in = F_63AF(); break;
        case 1: in = F_6505(); break;
        case 2: in = F_66F2(1); break;
        case 3: in = F_66F2(2); break;
        }
        if (D_9EC2 == 2) {
            packed = in.dir << 2 | in.jump << 1 | in.fire;
            *D_8A2C = packed;
            D_8A2C++;
        }
    } else {
        packed = *D_8A2C;
        D_8A2C++;
        in.fire = packed & 1;
        in.jump = packed & 1;
        in.dir = (packed & 0x3c) >> 2;
    }
    return in;
}
