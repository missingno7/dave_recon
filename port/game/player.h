/*
 * Dave: input handling, movement, jetpack fuel, death and restart.
 *
 * Native versions of four calls of the original per-tick pipeline (main in
 * src/DAVE.C; tools/oracle.py PIPELINE), with the helpers they call:
 *
 *   player_process_input   process_input  (F_4A27): demo playback, direction
 *                          latch, release-triggered fire / jetpack buttons
 *                          (U-G9), Dave's shot (spawn_object), jetpack
 *                          toggle, handle_menu_key's dispatch
 *   player_move            move_dave      (F_1D16): the movement state
 *                          machine incl. scroll_screen, animate_tick,
 *                          draw_dave / erase_dave and the death explosion
 *   player_update_jetpack  update_jetpack (F_1780): fuel consumption
 *   player_handle_death    handle_death   (F_15A5): death timer, life loss,
 *                          game over or restart (+ wait_for_input)
 *
 * Every function performs one whole original call: the vertical retraces
 * the original waits for inside it are counted in out->retraces, drawing is
 * emitted as draw commands in the original order (output.h) and sounds as
 * requests (out_sound). The code keeps each retrace wait (`retrace()` in
 * player.c) as an explicit boundary between segments, so the later
 * conversion to one-retrace steps (state-model D2) is mechanical.
 *
 * Quirks reproduced on purpose (ledger references in docs/UNDERSTANDING_LEDGER.md):
 *  - y is 8-bit in jump and fall steps: y = (y + t) & 0xFF (U-G2); landing
 *    snaps with & 0xF0; climbing and the jetpack use plain int y.
 *  - Movement throttle (U-G2, "g_death_pause"): decremented every alive
 *    call, reloaded with 3 after a move: walk every 3rd, jump/climb every
 *    2nd, fall/jetpack every call (the fall test `> 3` can never hold).
 *  - Branch order 0x04, 0x08, 0x10, 0x02, 0x01, 0x40: several movement bits
 *    may be set at once (a ladder grabbed on a jump's last step sets 0x02
 *    and 0x08) and only the first branch runs (U-G9 a).
 *  - The killed bit 0x40 is only acted on when no movement bit is set, and
 *    that path waits for no retrace (two pipeline ticks in one retrace).
 *  - Walking left does not record prev_dir at the end; walking right does.
 *  - A walk step that starts a fall still animates and moves 2 px more.
 *  - The fall's landing probe ORs two attributes: 3 (solid + deadly) does
 *    nothing at all; the jetpack's sideways probe treats 3 as free.
 *  - Demo bytes are signed: the jump button is `byte >> 6`, so a byte with
 *    the fire bit set gives -1 / -2 and leaves the jetpack counter alone.
 *  - Fire / jetpack act when their counter reaches 0: on the release tick,
 *    or after 30 held calls (signed 8-bit counters, U-G9 b).
 *  - tile_at() accepts rows 10 and 11; RowTimes100 has 10 entries, so those
 *    rows read the next table (offsets 640, 1280) -- kept in level_byte().
 *  - handle_death's timer is a 16-bit int that keeps counting through -1
 *    when it was never armed (level -1 only).
 */
#ifndef DAVE_PLAYER_H
#define DAVE_PLAYER_H

#include "input.h"
#include "output.h"
#include "resources.h"
#include "state.h"

/* What handle_menu_key decided; the caller runs the menu (they are
 * interactive sequences of their own, outside this subsystem). */
enum menu_request {
    MENU_NONE = 0,
    MENU_HELP,            /* F1  -> show_help */
    MENU_CONTROL_PANEL,   /* F2  -> control_panel */
    MENU_RESTART,         /* F3  -> ask_restart */
    MENU_PAUSE,           /* F9  -> pause_game */
    MENU_QUIT,            /* F10 / Esc -> ask_quit */
    MENU_END_DEMO,        /* any other key during a demo: restore the map, mode = play,
                             StopSound, init_game_state, load_level, redraw_screen, wait_for_input */
};

enum death_result {
    DEATH_NOTHING = 0,    /* alive, or the death timer still running */
    DEATH_GAME_OVER,      /* last life lost: game_over set, map restored */
    DEATH_RESTARTED,      /* Dave back at the start; wait_for_input must follow */
};

/* process_input(): `in` is this call's device sample (input.h). */
enum menu_request player_process_input(struct game *g, const struct resources *r,
                                       const struct frame_input *in, struct frame_output *out);

/* move_dave() */
void player_move(struct game *g, const struct resources *r, struct frame_output *out);

/* update_jetpack() */
void player_update_jetpack(struct game *g, struct frame_output *out);

/* handle_death() up to (not including) its closing wait_for_input(). */
enum death_result player_handle_death(struct game *g, const struct resources *r,
                                      struct frame_output *out);

/* One round of wait_for_input()'s loop: erase Dave, 10 x (retrace,
 * animate_tiles), draw Dave, 10 x (retrace, animate_tiles), then poll `in`.
 * Returns 1 when the wait is over (a direction, or a key pressed since the
 * wait began -- the original first flushes the waiting BIOS key, which the
 * platform's key queue does), after the closing sound. */
int player_wait_for_input_round(struct game *g, const struct frame_input *in,
                                struct frame_output *out);

#endif
