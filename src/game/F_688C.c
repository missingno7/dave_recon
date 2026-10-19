/*
 * F_688C -- get_player_input
 * cs [0x668c,0x67b9) / file [0x688c,0x69b9), 301 bytes. Strict match: tools/match_function.py.
 *
 * Input dispatcher: in live (D_9EC2 0) or record (2) mode reads the device
 * selected by D_12F0[player] (0 keyboard, 1 mouse, 2/3 joystick 1/2); in
 * record mode appends a packed byte dir<<2|jump<<1|fire to the demo buffer
 * D_8A2C. In playback mode (1) unpacks the next demo byte. Preserves the
 * original bug that playback sets BOTH fire and jump from bit 0.
 *
 * Evidence for the name: demo buffer pointer D_8A2C set by F_69B9/F_69D3;
 * mode D_9EC2.
 *
 * Codegen: Struct-returning calls go through compiler temporaries +
 * N_SCOPY@.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name get_player_input
 */
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
