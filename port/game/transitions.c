/*
 * Leaving a level: level_complete (DAVE.C cs 0x39A3, census F_3BA3) and
 * check_warp_transition (cs 0x32CB, census F_34CB).
 *
 * Both are long multi-retrace sequences inside one pipeline call; every
 * WaitVBL is counted in out->retraces at its place, and the loops are
 * written per retrace so that the D2 restructuring (one game step per
 * retrace) is mechanical.
 *
 * Quirks reproduced on purpose:
 *  - the level-6 warp bug (U-M1 item 1, U-M3): leaving the top row at the
 *    far left (view 0, x < 2, y < 16) or far right (view 80, x > 0x132) of
 *    ANY level whose warp is unused starts the warp sequence; the target
 *    table holds 0 for levels without a warp zone, so the next level is
 *    0 - 1 = -1. Level -1 itself is the D4 stand-in (see level.c);
 *  - the warp checks g_level_visited[level] BEFORE the level changes: a
 *    warp zone, once used, bounces Dave back (x = 4 or 0x130) instead;
 *  - level_complete restores the pristine map before anything else and
 *    advances the level BEFORE the warp-zone fix-up (draw_level_number is
 *    called for the intermediate level too);
 *  - the "N more to go" digit is 9 - level, printed only outside warp zones;
 *  - the ending's chasing light runs over 55 border positions where entry 47
 *    (the bottom-left corner) is overwritten by the left column's (0, 8): the
 *    corner is never lit (U-G8).
 */
#include "world.h"

#define TUBE_FALL_END 180
#define CORRIDOR_START_X 0x10
#define CORRIDOR_END_X 0x130
#define LAST_LEVEL 9
#define BORDER_PATH 55

enum { STATUS_TROPHY = 5 };

/* game_constant warp tables, per 0-based level */
static const int16_t warp_target_level_plus1[LEVEL_COUNT] = {0, 0, 0, 0, 2, 0, 0, 6, 7, 1};
static const int16_t warp_tube_tile[LEVEL_COUNT] = {0, 0, 0, 0, 5, 0, 0, 17, 18, 29};
static const int16_t warp_start_scroll_x[LEVEL_COUNT] = {0, 0, 0, 0, 42, 0, 0, 67, 71, 11};
static const int16_t warp_start_x[LEVEL_COUNT] = {0, 0, 0, 0, 144, 0, 0, 64, 144, 144};

static int level_valid(int16_t index)
{
    return index >= 0 && index < LEVEL_COUNT;
}

/* Per-level warp table entry; the original indexes unchecked, which only
 * level -1 could do, and Dave never leaves level -1 (he is not alive). */
static int16_t warp_entry(const int16_t table[LEVEL_COUNT], int16_t level)
{
    return level_valid(level) ? table[level] : 0;
}

static void wait_retraces(struct frame_output *out, int n)
{
    for (int i = 0; i < n; i++)
        out->retraces++;
}

static void blank_view(struct frame_output *out)
{
    for (int y = 0; y < 10; y++)
        for (int x = 0; x < 20; x++)
            out_draw(out, DRAW_TILE, x, y, 0, 0);
}

/* The next level (or the warp target) starts: view, sprites, wait for a key. */
static void enter_level_view(const struct game *g, struct frame_output *out)
{
    out->retraces++;
    out_draw(out, DRAW_LEVEL_VIEW, g->level.index, g->level.scroll_x, 0, 0);
    draw_actors(g, out);
}

void check_warp_transition(struct game *g, const struct resources *r, const struct world_io *io,
                           struct frame_output *out)
{
    int16_t L = g->level.index;
    int at_left_exit = g->dave.y < 16 && g->level.scroll_x == 0 && g->dave.x < 2;
    int at_right_exit = g->level.scroll_x == 80 && g->dave.x > 0x132;
    if (!at_left_exit && !at_right_exit)
        return;
    /* g_level_visited[-1] would be the word in front of the table (a near
     * pointer, never 1): level -1 counts as unvisited */
    int visited = level_valid(L) && g->level.warp_used[L] == 1;
    if (g->level.in_warp_zone == 1 || visited) {
        g->dave.x = g->dave.x < 2 ? 4 : 0x130;
        return;
    }

    /* the tube: Dave falls from the top to y = 180 between two tube columns */
    out_draw(out, DRAW_ERASE_DAVE, 0, 0, 0, 0);
    out_draw(out, DRAW_SET_DAVE_SPRITE, -1, 0, 0, 0);
    out->retraces++;
    blank_view(out);
    out->retraces++;
    for (int y = 0; y < 10; y++) {
        out_draw(out, DRAW_TILE, 8, y, warp_entry(warp_tube_tile, L), 0);
        out_draw(out, DRAW_TILE, 10, y, warp_entry(warp_tube_tile, L), 0);
    }
    out_draw(out, DRAW_XOR_SPRITE, 0x20, 0x5A, SPRITE_WARP_LEFT, 0);
    out_draw(out, DRAW_XOR_SPRITE, 0xC8, 0x5A, SPRITE_WARP_RIGHT, 0);
    g->dave.y = 0;
    g->dave.x = 0x90;
    out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, 0, 0);
    wait_retraces(out, 30);
    out_sound(out, 2);
    while (g->dave.y < TUBE_FALL_END) {
        out->retraces++;
        out_draw(out, DRAW_ERASE_DAVE, 0, 0, 0, 0);
        out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, 0, 0);
        g->dave.y++;
    }
    wait_retraces(out, 30);
    out->retraces++;
    blank_view(out);
    if (g->inv.got_trophy == 1)
        out_draw(out, DRAW_XOR_SPRITE, 0x48, 0xB8, SPRITE_STATUS, STATUS_TROPHY);

    /* leave the level (pristine map back) and load the target */
    restore_level_map(g, r);
    if (level_valid(L))
        g->level.warp_used[L] = 1;
    g->level.warp_return = L;
    int16_t col = warp_entry(warp_start_scroll_x, L);
    int16_t x = warp_entry(warp_start_x, L);
    g->level.index = (int16_t)(warp_entry(warp_target_level_plus1, L) - 1);   /* 0 - 1 = -1: the bug */
    load_level(g, r, out);
    g->level.scroll_x = col;
    g->dave.x = x;
    g->dave.y = 16;
    for (int k = 0; k < MONSTER_COUNT; k++)
        if (g->monsters[k].active == 1)
            g->monsters[k].x = (int16_t)(g->monsters[k].x - g->level.scroll_x * 16);
    enter_level_view(g, out);
    g->dave.state = (uint16_t)((g->dave.state & 0xE0) | DAVE_FALL);
    wait_for_input(g, io, out);
    g->level.in_warp_zone = 1;
}

/* The ending after level 10: a lit tile chasing round the border until Space. */
static void ending(struct game *g, const struct world_io *io, struct frame_output *out)
{
    int16_t xs[BORDER_PATH + 3], ys[BORDER_PATH + 3];
    out_draw(out, DRAW_SET_VIDEO_MODE, 0, 0, 0, 0);
    for (int i = 0; i < 20; i++) {
        out_draw(out, DRAW_TILE, i, 0, 10, 0);
        out_draw(out, DRAW_TILE, i, 9, 10, 0);
        if (i >= 1 && i < 9) {
            out_draw(out, DRAW_TILE, 0, i, 10, 0);
            out_draw(out, DRAW_TILE, 19, i, 10, 0);
        }
    }
    /* the border path, built exactly as the original builds it (U-G8) */
    for (int i = 0; i < 20; i++) { xs[i] = (int16_t)i; ys[i] = 0; }
    for (int i = 1; i < 9; i++) { xs[i + 19] = 19; ys[i + 19] = (int16_t)i; }
    for (int i = 0; i < 20; i++) { xs[i + 28] = (int16_t)(19 - i); ys[i + 28] = 9; }
    for (int i = 1; i < 9; i++) { xs[i + 46] = 0; ys[i + 46] = (int16_t)(9 - i); }

    out_draw(out, DRAW_TEXT_XOR, -1, 0, 0, 0);
    out_draw(out, DRAW_TEXT_CURSOR, 3, 5, 3, 0);
    for (int t = TEXT_CONGRATS_1; t <= TEXT_CONGRATS_10; t++)
        out_draw(out, DRAW_PRINT_STRING, t, 0, 0, 0);
    out_draw(out, DRAW_TEXT_XOR, 0, 0, 0, 0);
    int frame = 0, pos = 0;
    int8_t key;
    do {
        if (frame % 4 == 0)
            out->retraces++;
        key = (int8_t)io->key_peek(io->ctx, out->retraces);   /* char: the ASCII byte */
        if (++frame > 3)
            frame = 0;
        out_draw(out, DRAW_TILE, xs[pos], ys[pos], frame + 10, 0);
        if (++pos > BORDER_PATH - 1)
            pos = 0;
        (void)io->player(io->ctx, out->retraces);   /* polled, result unused */
    } while (key != ' ');
    io->key_take(io->ctx, out->retraces);
    g->game_over = 1;
}

void level_complete(struct game *g, const struct resources *r, const struct world_io *io,
                    struct frame_output *out)
{
    if (g->level.done != 1)
        return;
    out_draw(out, DRAW_XOR_SPRITE, 0x48, 0xB8, SPRITE_STATUS, STATUS_TROPHY);
    restore_level_map(g, r);
    out->retraces++;

    /* the between-levels corridor */
    blank_view(out);
    out_draw(out, DRAW_TILE, 0, 4, 2, 0);
    for (int x = 0; x < 20; x++) {
        out_draw(out, DRAW_TILE, x, 3, 5, 0);
        out_draw(out, DRAW_TILE, x, 5, 5, 0);
    }
    out_draw(out, DRAW_TEXT_XOR, -1, 0, 0, 0);
    out_draw(out, DRAW_TEXT_CURSOR, 6, 7, -1, 0);
    int msg = -1;                       /* uninitialised in the original; levels 0..9 set it */
    int digit = 0;
    if (g->level.index < 8) {
        msg = TEXT_GOOD_WORK;
        digit = 9 - g->level.index;
    }
    if (g->level.index == 8)
        msg = TEXT_LAST_LEVEL;
    if (g->level.index == LAST_LEVEL)
        msg = TEXT_FINISHED;
    if (g->level.in_warp_zone == 0 && msg >= 0)
        out_draw(out, DRAW_PRINT_STRING, msg, digit, 0, 0);
    out_draw(out, DRAW_TEXT_XOR, 0, 0, 0, 0);

    /* Dave walks right across the corridor, 2 px per 3 retraces */
    g->dave.x = CORRIDOR_START_X;
    g->dave.y = 0x50;
    out_draw(out, DRAW_SET_DAVE_SPRITE, 11, g->dave.anim_frame, 0, 0);
    out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, 0, 0);
    out_sound(out, 10);
    for (g->dave.x = CORRIDOR_START_X; g->dave.x < CORRIDOR_END_X; g->dave.x += 2) {
        wait_retraces(out, 3);
        out_draw(out, DRAW_ERASE_DAVE, 0, 0, 0, 0);
        if (g->dave.x % 3 == 2) {
            g->dave.anim_frame++;
            if (g->dave.anim_frame > 3)
                g->dave.anim_frame = 0;
        }
        out_draw(out, DRAW_SET_DAVE_SPRITE, 11, g->dave.anim_frame, 0, 0);
        out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, 0, 0);
        if (g->dave.x % 5 == 4)
            out_sound(out, 4);
    }
    out_sound(out, SOUND_STOP);

    g->level.index++;
    draw_level_number(g, out);
    if (g->level.in_warp_zone == 1) {     /* a warp zone resumes at the level it was entered from */
        g->level.in_warp_zone = 0;
        g->level.index = g->level.warp_return;
    }
    if (g->level.index < LEVEL_COUNT) {
        draw_level_number(g, out);
        load_level(g, r, out);
        enter_level_view(g, out);
        wait_for_input(g, io, out);
    } else {
        ending(g, io, out);
    }
}
