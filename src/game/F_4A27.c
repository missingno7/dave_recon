/*
 * F_4A27 -- process_input()
 * cs [0x4827,0x4b9c) / file [0x4a27,0x4c9c), 885 bytes incl. the 8-entry
 * switch jump table. Strict match: tools/match_function.py.
 *
 * Per-frame input handling. Reads the input state (F_688C(1): direction
 * 0..8, fire, jetpack). In demo playback (DS:0x00AA == 1) the state is
 * replaced from the demo stream g_demo_data (far, DS:0x57A4) at index
 * DS:0x57A2: ' ' n = n idle frames (counter DS:0x6544), '0' = end of demo
 * (restore the level grid, leave playback), otherwise a packed byte
 * (bit 7 fire, bit 6 jetpack, low nibble direction). The direction maps
 * to the movement state DS:0x57E2. Fire / jetpack auto-repeat counters
 * (signed chars DS:0x00AC / 0x00AD, reload 30) are reset when the button
 * is released. In demo recording (DS:0x00A8 == 1) the state is appended to
 * the stream run-length encoded. Firing (if Dave has the gun DS:0x4F84,
 * no own bullet (id 5) alive and 8 < y < 0xAA) spawns a bullet left or
 * right of Dave (facing DS:0x5740). The jetpack button toggles jetpack
 * flight (bit 0 of DS:0x6156; needs fuel DS:0x4F8A > 0; sounds 11 / 2)
 * and selects the matching player sprites. Finally F_4997 handles keys.
 *
 * @name process_input
 *
 * Codegen notes: the packed byte is a local of an inner block, so it is
 * allocated after the struct-return temporary (bp-0x0D vs bp-0x0C).
 * `char = a << 7 | b << 6 | c` is computed in byte registers.
 */
/* @flags -G */

struct input {
    int dir;
    int fire;
    int jet;
};

extern int D_00AA;              /* demo playback */
extern int D_00A8;              /* demo recording */
extern char D_6544;             /* demo run-length counter */
extern char far *D_57A4;        /* g_demo_data */
extern int D_57A2;              /* g_demo_pos */
extern char D_615C[];
extern char *D_57A8;
extern int D_57E2;              /* movement state */
extern signed char D_00AC;      /* fire repeat counter */
extern signed char D_00AD;      /* jetpack repeat counter */
extern int D_6156;
extern int D_4F84;              /* has gun */
extern int D_56EA;
extern int D_56EC;
extern int D_5740;              /* facing */
extern int D_4F8A;              /* jetpack fuel */
extern int D_57E6;
extern int D_4F86;
extern int D_6150;
extern int D_573E;
extern int D_57E4;
extern int D_03A6[];
extern int D_03BE[];
extern int D_03D6[];
extern int D_03EE[];
extern int D_579E;
extern int D_0336[];
extern int D_033C[];

struct input F_688C(int mode);
void movmem(void *src, void *dest, unsigned length);
int F_483F(int id);
void F_4886(int x, int y, int flag, int kind, int id);
void F_763E(int snd);
void F_4997(void);

void F_4A27(void)
{
    struct input in;

    in = F_688C(1);
    if (D_00AA == 1) {
        if (D_6544 == 0) {
            if (D_57A4[D_57A2] == ' ') {
                D_57A2++;
                D_6544 = D_57A4[D_57A2];
                D_57A2++;
            } else if (D_57A4[D_57A2] == '0') {
                D_00AA++;
                movmem(D_615C, D_57A8, 1000);
            } else {
                in.dir = D_57A4[D_57A2] & 0xf;
                in.fire = D_57A4[D_57A2] >> 7 & 1;
                in.jet = D_57A4[D_57A2] >> 6;
                D_57A2++;
            }
        } else {
            D_6544--;
            in.dir = 8;
            in.fire = 0;
            in.jet = 0;
        }
    }
    switch (in.dir) {
    case 4: D_57E2 = 4; break;
    case 5:
    case 6: D_57E2 = 6; break;
    case 2:
    case 3: D_57E2 = 2; break;
    case 0: D_57E2 = 0; break;
    case 7: D_57E2 = 7; break;
    case 1: D_57E2 = 1; break;
    }
    if (D_00AC > 0 && in.fire == 1)
        D_00AC--;
    if (D_00AC != 30 && in.fire == 0)
        D_00AC = 0;
    if (D_00AD > 0 && in.jet == 1)
        D_00AD--;
    if (D_00AD != 30 && in.jet == 0)
        D_00AD = 0;
    if (D_00A8 == 1) {
        if (in.dir == 8 && in.fire == 0 && in.jet == 0)
            D_6544++;
        else {
            char packed;

            packed = in.fire << 7 | in.jet << 6 | in.dir;
            if (D_6544 != 0) {
                D_57A4[D_57A2] = ' ';
                D_57A2++;
                D_57A4[D_57A2] = D_6544 - 1;
                D_57A2++;
                D_6544 = 0;
            }
            D_57A4[D_57A2] = packed;
            D_57A2++;
        }
    }
    if (D_00AC == 0 && (D_6156 & 0x20)) {
        D_00AC = 30;
        if (D_4F84 > 0 && !F_483F(5) && D_56EC > 8 && D_56EC < 0xaa) {
            if (D_5740 == 0)
                F_4886(D_56EA - 10, D_56EC + 7, 0, 1, 5);
            else
                F_4886(D_56EA + 20, D_56EC + 7, 1, 1, 5);
        }
    }
    if (D_00AD == 0 && (D_6156 & 0x20)) {
        D_00AD = 30;
        if (!(D_6156 & 1) && D_4F8A > 0) {
            F_763E(11);
            D_6156 = (D_6156 & 0xe0) | 1;
            D_57E6 = 1;
            D_573E = D_03A6[D_4F86 * 4 + D_6150];
            D_57E4 = D_03BE[D_4F86 * 4 + D_6150];
            if (D_57E2 == 6 || D_57E2 == 7 || D_57E2 == 5) {
                D_57E6 = 0;
                D_573E = D_03D6[D_4F86 * 4 + D_6150];
                D_57E4 = D_03EE[D_4F86 * 4 + D_6150];
            }
        } else if ((D_6156 & 1) == 1) {
            D_6156 = (D_6156 & 0xfe) | 8;
            F_763E(2);
            D_579E = D_57E2;
            D_57E2 = 8;
            D_573E = D_0336[D_4F86];
            D_57E4 = D_033C[D_4F86];
        }
    }
    F_4997();
}
