/*
 * F_69B9 -- demo_record_start
 * cs [0x67b9,0x67d3) / file [0x69b9,0x69d3), 26 bytes. Strict match: tools/match_function.py.
 *
 * Starts demo recording: buffer pointer D_8A2C = D_8B34, mode D_9EC2 = 2.
 *
 * Evidence for the name: consumer get_player_input.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name demo_record_start
 */
/* @flags -G */
extern char *D_8A2C;
extern char D_8B34[];
extern int D_9EC2;

void F_69B9(void)
{
    D_8A2C = D_8B34;
    D_9EC2 = 2;
}
