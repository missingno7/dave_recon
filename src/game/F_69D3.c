/*
 * F_69D3 -- demo_play_start
 * cs [0x67d3,0x67fb) / file [0x69d3,0x69fb), 40 bytes. Strict match: tools/match_function.py.
 *
 * Loads a demo file into D_8B34 (F_6ADE) and starts playback (D_9EC2 = 1).
 *
 * Evidence for the name: consumer get_player_input.
 *
 * Codegen: The far argument is written `(char far *)(long)D_8B34`: this
 * reproduces `mov ax,OFF; push ds; push ax`; a plain near->far conversion
 * pushes ds before loading the offset.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name demo_play_start
 */
/* @flags -G */
extern char *D_8A2C;
extern char D_8B34[];
extern int D_9EC2;
long F_6ADE(char *name, char far *buf);

void F_69D3(char *name)
{
    F_6ADE(name, (char far *)(long)D_8B34);
    D_8A2C = D_8B34;
    D_9EC2 = 1;
}
