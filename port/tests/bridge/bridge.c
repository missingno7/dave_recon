/*
 * TEST-ONLY verification bridge (docs/PORT_ROADMAP.md, decision 3).
 *
 * For each original DGROUP snapshot in <in.bin> (DS 0x0000-0x9F20, as
 * captured by tools/oracle.py): import struct game (dgroup_map.c), run one
 * native subsystem, export struct game back into a copy of the snapshot, and
 * append it to <out.bin>. The step's draw commands and sound requests are
 * written to [events.txt]. tools/native_check.py compares the result with the
 * original's snapshot after the same subsystem.
 *
 *   dave_bridge <subsystem> <in.bin> <out.bin> [events.txt]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "anim.h"
#include "dgroup_map.h"
#include "explosions.h"
#include "monsters.h"
#include "shots.h"
#include "output.h"
#include "state.h"
#include "player.h"
#include "world.h"
#include "world_io.h"

/* Every native subsystem gets the state, the immutable resources and the
 * output of the step. */
typedef void (*subsystem_fn)(struct game *, const struct resources *, struct frame_output *);

static void run_identity(struct game *g, const struct resources *r, struct frame_output *o) {
    (void)g; (void)r; (void)o;
}
static void run_animate_tiles(struct game *g, const struct resources *r, struct frame_output *o) {
    (void)r;
    anim_step(&g->anim, g->level.scroll_x, o);
}

/* ---- player (N2): input from bridge_world_io() (world_io.c) ---- */
/* process_input's sample: get_player_input(1) and the waiting BIOS key, as
 * the world's input model sees them at the start of the call. */
static struct frame_input bridge_frame_input(void) {
    const struct world_io *io = bridge_world_io();
    struct frame_input in = io->player(io->ctx, 0);
    in.menu_key = (int16_t)((uint16_t)io->key_peek(io->ctx, 0) >> 8);
    return in;
}
static void run_process_input(struct game *g, const struct resources *r, struct frame_output *o) {
    struct frame_input in = bridge_frame_input();
    (void)player_process_input(g, r, &in, o);
}
static void run_move_dave(struct game *g, const struct resources *r, struct frame_output *o) {
    player_move(g, r, o);
}
static void run_update_jetpack(struct game *g, const struct resources *r, struct frame_output *o) {
    (void)r;
    player_update_jetpack(g, o);
}
/* handle_death incl. its closing wait_for_input (polls through the world io). */
static void run_handle_death(struct game *g, const struct resources *r, struct frame_output *o) {
    (void)player_handle_death(g, r, bridge_world_io(), o);
}

/* Player mutants (tests/test_native.py, the `<name>/mutant` pattern): one
 * deliberate change of each player subsystem's result that the check must
 * catch. (tests/test_native.py also builds source-level mutants of player.c.) */
static void run_process_input_mutant(struct game *g, const struct resources *r, struct frame_output *o) {
    int8_t before = g->buttons.fire_repeat;
    run_process_input(g, r, o);
    if (g->buttons.fire_repeat == 30 && before != 30)   /* fire reload 29 instead of 30 */
        g->buttons.fire_repeat = 29;
}
static void run_move_dave_mutant(struct game *g, const struct resources *r, struct frame_output *o) {
    player_move(g, r, o);
    if (g->dave.move_throttle == 3)                     /* movement throttle reload 2 instead of 3 */
        g->dave.move_throttle = 2;
}
static void run_update_jetpack_mutant(struct game *g, const struct resources *r, struct frame_output *o) {
    (void)r;
    int16_t before = g->inv.fuel_tick;
    player_update_jetpack(g, o);
    if (g->inv.fuel_tick == 15 && before != 15)         /* fuel period 14 instead of 15 */
        g->inv.fuel_tick = 14;
}
static void run_handle_death_mutant(struct game *g, const struct resources *r, struct frame_output *o) {
    int16_t before = g->dave.death_timer;
    run_handle_death(g, r, o);
    if (g->dave.death_timer == before - 1 && g->dave.death_timer > 1)   /* timer steps by 2 */
        g->dave.death_timer--;
}


/* world (N3): the waiting loops' input comes from bridge_world_io() */
static void run_check_collisions(struct game *g, const struct resources *r, struct frame_output *o) {
    check_collisions(g, r, o);
}
static void run_pick_up_items(struct game *g, const struct resources *r, struct frame_output *o) {
    pick_up_items(g, r, o);
}
static void run_level_complete(struct game *g, const struct resources *r, struct frame_output *o) {
    level_complete(g, r, bridge_world_io(), o);
}
static void run_check_warp_transition(struct game *g, const struct resources *r, struct frame_output *o) {
    check_warp_transition(g, r, bridge_world_io(), o);
}
static void run_attract_mode(struct game *g, const struct resources *r, struct frame_output *o) {
    attract_mode(g, r, bridge_world_io(), o);
}
static void run_update_explosions(struct game *g, const struct resources *r, struct frame_output *o) {
    explosions_step(g, r, o);
}
static void run_move_monsters(struct game *g, const struct resources *r, struct frame_output *o) {
    monsters_step(g, r, o);
}
static void run_move_bullets(struct game *g, const struct resources *r, struct frame_output *o) {
    shots_step(g, r, o);
}

/* Mutants (tests/test_native.py): a deliberate one-constant change of each
 * subsystem, reproduced on the native result, which the check must catch. */
static void run_move_monsters_mutant(struct game *g, const struct resources *r, struct frame_output *o) {
    monsters_step(g, r, o);
    for (int i = 0; i < MONSTER_COUNT; i++)      /* move period 4 instead of 5 */
        if (g->monsters[i].active && g->monsters[i].move_count == 5)
            g->monsters[i].move_count = 4;
}
static void run_move_bullets_mutant(struct game *g, const struct resources *r, struct frame_output *o) {
    struct game before = *g;
    shots_step(g, r, o);
    for (int i = 0; i < SHOT_COUNT; i++)         /* speed 3 instead of 2 */
        if (g->shots[i].active && g->shots[i].x != before.shots[i].x)
            g->shots[i].x = (int16_t)(g->shots[i].x + (g->shots[i].x > before.shots[i].x ? 1 : -1));
}
static void run_update_explosions_mutant(struct game *g, const struct resources *r, struct frame_output *o) {
    explosions_step(g, r, o);
    for (int i = 0; i < EXPLOSION_COUNT; i++)    /* frame period 12 instead of 13 */
        if (g->explosions[i].active && g->explosions[i].anim == 13)
            g->explosions[i].anim = 12;
}

/* Registry: one line per native subsystem, named after the original
 * pipeline call it replaces (tools/oracle.py PIPELINE). */
static const struct { const char *name; subsystem_fn run; } subsystems[] = {
    {"identity", run_identity},
    {"animate_tiles", run_animate_tiles},
    /* player (N2) */
    {"process_input", run_process_input},
    {"move_dave", run_move_dave},
    {"update_jetpack", run_update_jetpack},
    {"handle_death", run_handle_death},
    {"check_collisions", run_check_collisions},
    {"pick_up_items", run_pick_up_items},
    {"level_complete", run_level_complete},
    {"check_warp_transition", run_check_warp_transition},
    {"attract_mode", run_attract_mode},
    {"update_explosions", run_update_explosions},
    {"move_monsters", run_move_monsters},
    {"move_bullets", run_move_bullets},
    {"move_monsters/mutant", run_move_monsters_mutant},
    {"move_bullets/mutant", run_move_bullets_mutant},
    {"update_explosions/mutant", run_update_explosions_mutant},
    {"process_input/mutant", run_process_input_mutant},
    {"move_dave/mutant", run_move_dave_mutant},
    {"update_jetpack/mutant", run_update_jetpack_mutant},
    {"handle_death/mutant", run_handle_death_mutant},
};

static void write_events(FILE *f, long index, const struct frame_output *o) {
    for (unsigned i = 0; i < o->n_draws; i++)
        fprintf(f, "%ld draw %u %d %d %d %d\n", index, o->draws[i].op,
                o->draws[i].a, o->draws[i].b, o->draws[i].c, o->draws[i].d);
    if (o->retraces)
        fprintf(f, "%ld retraces %u\n", index, o->retraces);
    for (unsigned i = 0; i < o->n_sounds; i++)
        fprintf(f, "%ld sound %d\n", index, o->sounds[i]);
}

int main(int argc, char **argv) {
    const uint16_t probe = 1;
    if (*(const unsigned char *)&probe != 1) {
        fprintf(stderr, "dave_bridge assumes a little-endian host\n");
        return 2;
    }
    if (argc < 4) {
        fprintf(stderr, "usage: dave_bridge <subsystem> <in.bin> <out.bin> [events.txt]\n");
        return 2;
    }
    subsystem_fn run = NULL;
    for (size_t i = 0; i < sizeof subsystems / sizeof subsystems[0]; i++)
        if (strcmp(argv[1], subsystems[i].name) == 0)
            run = subsystems[i].run;
    if (!run) {
        fprintf(stderr, "unknown subsystem %s\n", argv[1]);
        return 2;
    }
    FILE *in = fopen(argv[2], "rb"), *out = fopen(argv[3], "wb");
    if (!in || !out) {
        perror("open");
        return 2;
    }
    FILE *events = argc > 4 ? fopen(argv[4], "w") : NULL;
    static unsigned char snap[DGROUP_LEN];
    static struct game g;
    static struct frame_output o;
    static struct resources res;
    long index = 0;
    bridge_world_load(&res);              /* world (N3): demo bank, scenario input */
    while (fread(snap, 1, DGROUP_LEN, in) == DGROUP_LEN) {
        dgroup_import(&g, snap);
        dgroup_import_resources(&res, snap);
        bridge_world_begin(index, snap, &g, &res);   /* world (N3): resources, g_tiles, input */
        memset(&o, 0, sizeof o);
        run(&g, &res, &o);
        dgroup_export_levels(&g, &res, snap);    /* world (N3): g_levels records, g_tiles */
        dgroup_export(&g, snap);
        if (events)
            write_events(events, index, &o);
        fwrite(snap, 1, DGROUP_LEN, out);
        index++;
    }
    fclose(in);
    fclose(out);
    if (events)
        fclose(events);
    return 0;
}
