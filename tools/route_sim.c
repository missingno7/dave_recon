/*
 * Route planner's fast simulator (tools/route.py; docs/FIDELITY.md section 5).
 *
 * NOT a verification tool: it only PLANS scripted routes for the oracle,
 * which stays the judge (every route is run on the original DAVE.EXE and
 * snapped/verified there). It chains the native port's pipeline calls
 * (port/game, read-only use) from one original DGROUP snapshot, imported
 * through the test bridge's mapping (port/tests/bridge/dgroup_map.c), with a
 * constant input per tick:
 *
 *   route_sim <snapshot.bin> <levels.bin> <demos.bin>
 *   stdin:  s <dir 0..8> <fire 0/1> <jump 0/1>   one pipeline pass (tick)
 *           save <slot> | load <slot> | free <slot>   copies of the whole state
 *           w <dir>                              direction the waiting loops see
 *                                                when the tick's input has none
 *           f                                    flush stdout
 *           q
 *   stdout per step: retraces x y state level scroll score lives trophy
 *           jetpack fuel gun done warp mode game_over death_timer first_poll
 *           jump_pos input_dir throttle sounds (sounds: comma-separated
 *           PlaySound ids, '-' if none; first_poll: retraces into the tick at
 *           the first waiting-loop poll that used the `w` direction, -1 none)
 *
 * Waiting loops (wait_for_input, death restart, level transitions) see the
 * tick's input at every poll, so a tick whose input has a direction leaves
 * them at their first poll; with no direction they see `w` (a key pressed
 * during the wait, which route.py turns into an event before that poll).
 * Menu keys are never pressed.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "dgroup_map.h"
#include "explosions.h"
#include "monsters.h"
#include "output.h"
#include "player.h"
#include "shots.h"
#include "state.h"
#include "world.h"

static struct frame_input cur_in;
static int16_t wait_dir = DIR_E;
static long first_poll = -1;

static struct frame_input io_player(void *ctx, uint32_t retrace)
{
    (void)ctx;
    struct frame_input in = cur_in;
    if (in.dir == DIR_NONE) {
        in.dir = wait_dir;
        if (first_poll < 0)
            first_poll = (long)retrace;
    }
    return in;
}
static int16_t io_peek(void *ctx, uint32_t retrace) { (void)ctx; (void)retrace; return 0; }
static void io_take(void *ctx, uint32_t retrace) { (void)ctx; (void)retrace; }
static uint32_t io_clock(void *ctx, uint32_t retrace) { (void)ctx; (void)retrace; return 662706000u; }

static const struct world_io io = {NULL, io_player, io_peek, io_take, io_clock};

#define SLOTS 200000
static struct game g, *saved[SLOTS];
static long saved_poll[SLOTS];    /* first_poll of the tick before the save */
static struct resources res;
static struct frame_output out;

static int read_file(const char *path, void *buf, size_t n)
{
    FILE *f = fopen(path, "rb");
    if (!f)
        return 0;
    size_t got = fread(buf, 1, n, f);
    fclose(f);
    return got == n;
}

int main(int argc, char **argv)
{
    static unsigned char snap[DGROUP_LEN];
    static unsigned char levels[LEVEL_COUNT * 0x500];
    static unsigned char demos[DEMO_BANK_BYTES + DEMO_OVERRUN_BYTES];
    if (argc < 4 || !read_file(argv[1], snap, DGROUP_LEN) || !read_file(argv[2], levels, sizeof levels)
        || !read_file(argv[3], demos, sizeof demos)) {
        fprintf(stderr, "usage: route_sim <snapshot.bin> <levels.bin> <demos.bin>\n");
        return 2;
    }
    memcpy(res.demos, demos, DEMO_BANK_BYTES);
    memcpy(res.demo_overrun, demos + DEMO_BANK_BYTES, DEMO_OVERRUN_BYTES);
    dgroup_import(&g, snap);
    dgroup_import_resources(&res, snap);
    dgroup_import_world(&g, &res, snap, levels);
    char line[128];
    setvbuf(stdout, NULL, _IOFBF, 1 << 16);
    while (fgets(line, sizeof line, stdin)) {
        int dir, fire, jump, slot;
        if (sscanf(line, "s %d %d %d", &dir, &fire, &jump) == 3) {
            /* a key pressed during the previous tick's wait is still held at
             * this tick's read (route.py plan_events releases it before the
             * NEXT tick head at the earliest) */
            if (dir == DIR_NONE && first_poll >= 0)
                dir = wait_dir;
            cur_in.dir = (int16_t)dir;
            cur_in.fire = (int16_t)fire;
            cur_in.jump = (int16_t)jump;
            cur_in.menu_key = 0;
            memset(&out, 0, sizeof out);
            first_poll = -1;
            /* main()'s pipeline, src/DAVE.C */
            attract_mode(&g, &res, &io, &out);
            (void)player_process_input(&g, &res, &cur_in, &out);
            player_move(&g, &res, &out);
            explosions_step(&g, &res, &out);
            monsters_step(&g, &res, &out);
            shots_step(&g, &res, &out);
            anim_step(&g.anim, g.level.scroll_x, &out);
            check_collisions(&g, &res, &out);
            pick_up_items(&g, &res, &out);
            level_complete(&g, &res, &io, &out);
            check_warp_transition(&g, &res, &io, &out);
            player_update_jetpack(&g, &out);
            (void)player_handle_death(&g, &res, &io, &out);
            printf("%u %d %d %u %d %d %lu %d %d %d %d %d %d %d %d %d %d %ld %d %d %d ", out.retraces,
                   g.dave.x, g.dave.y, g.dave.state, g.level.index, g.level.scroll_x,
                   (unsigned long)g.score, g.lives, g.inv.got_trophy, g.inv.has_jetpack,
                   g.inv.jetpack_fuel, g.inv.has_gun, g.level.done, g.level.in_warp_zone, g.mode,
                   g.game_over, g.dave.death_timer, first_poll, g.dave.jump_pos,
                   g.dave.input_dir, g.dave.move_throttle);
            if (!out.n_sounds)
                printf("-");
            for (unsigned i = 0; i < out.n_sounds; i++)
                printf(i ? ",%d" : "%d", out.sounds[i]);
            printf("\n");
        } else if (sscanf(line, "save %d", &slot) == 1 && slot >= 0 && slot < SLOTS) {
            if (!saved[slot])
                saved[slot] = malloc(sizeof g);
            *saved[slot] = g;
            saved_poll[slot] = first_poll;
        } else if (sscanf(line, "load %d", &slot) == 1 && slot >= 0 && slot < SLOTS && saved[slot]) {
            g = *saved[slot];
            first_poll = saved_poll[slot];
        } else if (sscanf(line, "free %d", &slot) == 1 && slot >= 0 && slot < SLOTS) {
            free(saved[slot]);
            saved[slot] = NULL;
        } else if (sscanf(line, "w %d", &dir) == 1) {
            wait_dir = (int16_t)dir;
        } else if (line[0] == 'f') {
            fflush(stdout);
        } else if (line[0] == 'q') {
            break;
        }
    }
    fflush(stdout);
    return 0;
}
