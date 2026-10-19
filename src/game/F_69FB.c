/*
 * F_69FB -- demo_save
 * cs [0x67fb,0x6826) / file [0x69fb,0x6a26), 43 bytes. Strict match: tools/match_function.py.
 *
 * Writes the recorded demo (D_8B34 .. D_8A2C) to a file with F_6B94 and
 * stops recording (D_9EC2 = 0).
 *
 * Codegen: Same `(char far *)(long)` far-argument form as demo_play_start;
 * the pointer difference is converted to long (cwd).
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name demo_save
 */
/* @flags -G */
extern char *D_8A2C;
extern char D_8B34[];
extern int D_9EC2;
void F_6B94(char *name, char far *buf, long len);

void F_69FB(char *name)
{
    F_6B94(name, (char far *)(long)D_8B34, D_8A2C - D_8B34);
    D_9EC2 = 0;
}
