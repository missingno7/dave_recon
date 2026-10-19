/*
 * F_535A -- init_game_state()
 * cs [0x515a,0x51c3) / file [0x535a,0x53c3), 105 bytes.
 * Strict match: tools/match_function.py.
 *
 * Resets the per-game state at the start of a new game: clears a 10-word
 * table at DS:0x57AA, sets lives (DS:0x56EE) to 3, zeroes the 32-bit score
 * (DS:0x4C60/62) and the 32-bit next-extra-life goal (DS:0x6148/4A), clears
 * the game-over flag (DS:0x5792), the current level (DS:0x56F4), the level
 * reference (DS:0x57A0), sets the levels-left counter (DS:0x615A) to 10,
 * clears the warp-zone flag (DS:0x573C) and finally re-applies the video
 * mode held in DS:0x8B32 via F_6D64 (set_video_mode).
 *
 * @name init_game_state
 * Evidence: docs/external-re-evidence.md EXT_INIT_FUNCTION (g_lives=3,
 * scores/goals zeroed, g_maybe_levels_left=10 ...), verified byte-for-byte.
 *
 * Codegen notes: needs the -G flag (optimise for speed, directive below):
 * without it the 2-byte argument cleanup is `pop cx` instead of
 * `inc sp; inc sp`. `for` with a register int counter compiles to
 * `xor si,si; jmp cond; body; inc si; cond: cmp si,N; jl body`.
 */


extern int D_57AA[];            /* 10-word per-game table */
extern int D_56EE;              /* g_lives */
extern int D_4C60;              /* g_score low word */
extern int D_4C62;              /* g_score high word */
extern int D_6148;              /* g_next_goal low word */
extern int D_614A;              /* g_next_goal high word */
extern int D_5792;              /* g_is_game_over */
extern int D_56F4;              /* g_current_level */
extern int D_57A0;              /* g_some_level_reference */
extern int D_615A;              /* g_levels_left */
extern int D_573C;              /* g_is_warp_zone */
extern int D_8B32;              /* video mode */

void F_6D64(int mode);

void F_535A(void)
{
    int i;

    for (i = 0; i < 10; i++)
        D_57AA[i] = 0;
    D_56EE = 3;
    D_4C60 = 0;
    D_4C62 = 0;
    D_6148 = 0;
    D_614A = 0;
    D_5792 = 0;
    D_56F4 = 0;
    D_57A0 = 0;
    D_615A = 10;
    D_573C = 0;
    F_6D64(D_8B32);
}

