/* One pass of main()'s inner loop (see game.h). */
#include "game.h"
#include "anim.h"
#include "explosions.h"
#include "monsters.h"
#include "shots.h"

/* process_input's device sample at its place in the pass: get_player_input(1)
 * and the waiting BIOS key (bioskey(1) >> 8, read by handle_menu_key). */
static struct frame_input sample_input(const struct world_io *io, const struct frame_output *out)
{
    struct frame_input in = io->player(io->ctx, out->retraces);
    in.menu_key = (int16_t)((uint16_t)io->key_peek(io->ctx, out->retraces) >> 8);
    return in;
}

struct tick_result game_tick(struct game *g, const struct resources *r, const struct world_io *io,
                             struct frame_output *out)
{
    struct tick_result res = {TICK_CONTINUE, MENU_NONE};

    attract_mode(g, r, io, out);
    struct frame_input in = sample_input(io, out);
    res.menu = player_process_input(g, r, &in, out);
    if (res.menu != MENU_NONE) {        /* handle_menu_key's sequence: not run (game.h) */
        res.status = TICK_MENU;
        return res;
    }
    player_move(g, r, out);
    explosions_step(g, r, out);
    monsters_step(g, r, out);
    shots_step(g, r, out);
    anim_step(&g->anim, g->level.scroll_x, out);
    check_collisions(g, r, out);
    pick_up_items(g, r, out);
    level_complete(g, r, io, out);
    check_warp_transition(g, r, io, out);
    player_update_jetpack(g, out);
    (void)player_handle_death(g, r, io, out);

    if (g->game_over != 0)              /* `while (g_game_over == 0)` */
        res.status = TICK_GAME_OVER;
    return res;
}
