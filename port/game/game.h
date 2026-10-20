/*
 * One game tick: one pass of the original main loop's inner body
 * (src/DAVE.C main, the `do { ... } while (g_game_over == 0)` loop): the 13
 * native pipeline subsystems in the original order (tools/oracle.py
 * PIPELINE), with the conventions they already share:
 *
 *   - state: struct game, the only gameplay state (state.h); nothing of the
 *     tick is kept anywhere else between two calls;
 *   - resources: immutable (resources.h);
 *   - output: ONE struct frame_output for the whole pass, so draw commands
 *     and sound requests are in the original's call order across subsystems
 *     and out->retraces is the number of retraces waited since the tick
 *     head; the waiting loops poll `io` with that running count, i.e. at the
 *     time of the poll measured from the tick head;
 *   - input: process_input's sample is taken from `io` at its place in the
 *     pass (after attract_mode's retraces), exactly as get_player_input(1)
 *     and bioskey(1) are read there; the waiting loops (title, high scores,
 *     wait_for_input, the ending) poll `io` themselves.
 *
 * Not modelled yet (state-model D2): the per-retrace step; a tick still runs
 * every wait of the pass to completion and reports their count.
 *
 * Outside the pipeline, and therefore outside game_tick:
 *   - main()'s code between two inner loops: `g_game_over = 0;
 *     check_high_score()` (high-score entry), then `g_demo_mode = 3`;
 *   - init_game_once (program start), handle_menu_key's popups (F1 help,
 *     F2 control panel, F3 restart, F9 pause, F10/Esc quit) and the end of a
 *     demo by a key (MENU_END_DEMO): process_input decides them
 *     (player_process_input returns the request) but the original then runs
 *     them INSIDE process_input, before move_dave. game_tick cannot resume a
 *     pass after an interactive sequence yet, so it stops the pass there and
 *     returns the request (TICK_MENU); the caller must not continue as if the
 *     pass had completed.
 */
#ifndef DAVE_GAME_H
#define DAVE_GAME_H

#include "output.h"
#include "player.h"
#include "resources.h"
#include "state.h"
#include "world.h"

enum tick_status {
    TICK_CONTINUE = 0,   /* the pass completed and g_game_over is 0: the inner loop goes on */
    TICK_GAME_OVER,      /* the pass completed with g_game_over set: the inner loop ends
                            (main() then clears it and runs check_high_score, mode 3) */
    TICK_MENU,           /* process_input asked for a menu / demo end the port does not run
                            yet: the pass stopped after process_input (see above) */
};

struct tick_result {
    enum tick_status status;
    enum menu_request menu;        /* TICK_MENU: process_input's request */
};

struct tick_result game_tick(struct game *g, const struct resources *r, const struct world_io *io,
                             struct frame_output *out);

#endif
