/*
 * F_04D2 -- quit_game
 * cs [0x02d2,0x02fc) / file [0x4d2,0x4fc), 42 bytes.
 *
 * quit_game(code): restores the hardware state (F_6388, F_760F), returns
 * to text mode (F_6D64(0)) when exiting normally, then exit(code).
 * @name quit_game -- evidence: ends in exit(); called by main and by the
 * "Quit?" prompt (F_124B).
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 * exit() is the CS.LIB routine at cs 0x9463.
 */
/* @flags -G */
#include <stdlib.h>
void F_6388(void);
void F_760F(void);
void F_6D64(int);

void F_04D2(int code)
{
    F_6388();
    F_760F();
    if (code == 0)
        F_6D64(0);
    exit(code);
}
