/*
 * F_332C -- animate_tiles()
 * cs [0x312c,0x3235) / file [0x332c,0x3435), 265 bytes.
 * Strict match: tools/match_function.py.
 *
 * Every 10th call (countdown DS:0x615A, reloaded with 10) steps the list of
 * animated level tiles at DS:0x57E8 (12-byte records, terminated by a
 * record whose frame count is <= 0): for each active record the current
 * tile id (+4) advances and wraps from first + count back to first (+2);
 * if its level column (+6) lies within the visible window
 * [DS:0x57A0, DS:0x57A0 + 19], the tile is redrawn via
 * F_92D6(column - DS:0x57A0, row (+8), tile).
 *
 * @name animate_tiles
 *
 * Codegen notes: the visibility test is a bitwise `&` of two comparisons
 * (both materialised as 0/1, then `test ax,dx`), not `&&`. The countdown
 * here shares DS:0x615A with init_game_state's "levels left = 10".
 */
/* @flags -G */

struct anim {
    int active;
    int first;
    int cur;
    int col;
    int row;
    int count;
};

extern int D_615A;
extern struct anim D_57E8[];
extern int D_57A0;              /* first visible level column */

void F_92D6(int x, int y, int tile);

void F_332C(void)
{
    int i;

    if (--D_615A == 0) {
        for (i = 0, D_615A = 10; D_57E8[i].count > 0; i++) {
            if (D_57E8[i].active != 0) {
                if (D_57E8[i].first + D_57E8[i].count <= ++D_57E8[i].cur)
                    D_57E8[i].cur = D_57E8[i].first;
                if ((D_57E8[i].col >= D_57A0) & (D_57E8[i].col <= D_57A0 + 19))
                    F_92D6(D_57E8[i].col - D_57A0, D_57E8[i].row, D_57E8[i].cur);
            }
        }
    }
}
