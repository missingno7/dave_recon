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
#include "output.h"
#include "state.h"
#include "player.h"

/* The snapshot being processed (set by main before each run): subsystems
 * that read input reconstruct it from here (dgroup_import_input). */
static const unsigned char *current_snapshot;

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

/* ---- player (N2) ---- */
static void run_process_input(struct game *g, const struct resources *r, struct frame_output *o) {
    struct frame_input in;
    dgroup_import_input(&in, current_snapshot);
    (void)player_process_input(g, r, &in, o);
}
static void run_move_dave(struct game *g, const struct resources *r, struct frame_output *o) {
    player_move(g, r, o);
}
static void run_update_jetpack(struct game *g, const struct resources *r, struct frame_output *o) {
    (void)r;
    player_update_jetpack(g, o);
}
/* handle_death incl. its closing wait_for_input. The snapshot holds the
 * input at the start of the call only, so every poll sees that input: the
 * wait ends at its first poll if a direction is held (n2_death.txt holds
 * Right), and cannot be reproduced otherwise (one round is run). */
static void run_handle_death(struct game *g, const struct resources *r, struct frame_output *o) {
    if (player_handle_death(g, r, o) == DEATH_RESTARTED) {
        struct frame_input in;
        dgroup_import_input(&in, current_snapshot);
        (void)player_wait_for_input_round(g, &in, o);
    }
}

/* The demo bank (far segment 0x0B31 of the load module) from the unpacked
 * DAVE.EXE: $DAVE_UNPACKED_EXE, else build/DAVE_unpacked.exe next to
 * build/port/dave_bridge.exe. */
static void load_demo_bank(struct resources *res, const char *argv0) {
    char path[1024];
    const char *env = getenv("DAVE_UNPACKED_EXE");
    if (env) {
        snprintf(path, sizeof path, "%s", env);
    } else {
        snprintf(path, sizeof path, "%s", argv0);
        char *slash = NULL;
        for (char *p = path; *p; p++)
            if (*p == '/' || *p == '\\')
                slash = p;
        if (slash)
            snprintf(slash + 1, sizeof path - (size_t)(slash + 1 - path), "../DAVE_unpacked.exe");
        else
            snprintf(path, sizeof path, "../DAVE_unpacked.exe");
    }
    FILE *f = fopen(path, "rb");
    if (!f)
        return;
    unsigned char hdr[10];
    if (fread(hdr, 1, sizeof hdr, f) == sizeof hdr) {
        long at = (long)(hdr[8] | (hdr[9] << 8)) * 16 + 0x0B31L * 16;
        if (fseek(f, at, SEEK_SET) == 0 && fread(res->demo_bank, 1, DEMO_BANK_BYTES, f) != DEMO_BANK_BYTES)
            memset(res->demo_bank, 0, DEMO_BANK_BYTES);
    }
    fclose(f);
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
    load_demo_bank(&res, argv[0]);
    while (fread(snap, 1, DGROUP_LEN, in) == DGROUP_LEN) {
        current_snapshot = snap;
        dgroup_import(&g, snap);
        dgroup_import_resources(&res, snap);
        memset(&o, 0, sizeof o);
        run(&g, &res, &o);
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
