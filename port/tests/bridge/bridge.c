/*
 * TEST-ONLY verification bridge (docs/PORT_ROADMAP.md, decision 3).
 *
 * Imports native state from an original DGROUP snapshot (DS 0x0000-0x9F20, as
 * captured by tools/oracle.py), runs one native subsystem, and exports the
 * native state back into a copy of the snapshot, so the result can be compared
 * byte for byte with the original's snapshot after the same subsystem.
 * This is the only code that knows original DS offsets; the game layer never
 * sees them.
 *
 *   dave_bridge <subsystem> <in.bin> <out.bin> [events.txt]
 *   in.bin / out.bin: N concatenated snapshots of DGROUP_LEN bytes.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "anim.h"

#define DGROUP_LEN 0x9F20

/* Original DS offsets (layout/bss-map.json). */
#define DS_ANIM_TILES        0x57E8   /* struct anim[200] */
#define DS_ANIM_TICK_DIVIDER 0x615A
#define DS_SCROLL_X          0x57A0

static int16_t rd16(const unsigned char *m, unsigned off) {
    return (int16_t)(m[off] | (m[off + 1] << 8));
}
static void wr16(unsigned char *m, unsigned off, int16_t v) {
    m[off] = (unsigned char)(v & 0xFF);
    m[off + 1] = (unsigned char)((v >> 8) & 0xFF);
}

static void import_anim(struct anim_state *a, const unsigned char *m) {
    for (int i = 0; i < ANIM_MAX_TILES; i++) {
        unsigned b = DS_ANIM_TILES + 12u * (unsigned)i;
        a->tiles[i].active = rd16(m, b + 0);
        a->tiles[i].first = rd16(m, b + 2);
        a->tiles[i].cur = rd16(m, b + 4);
        a->tiles[i].col = rd16(m, b + 6);
        a->tiles[i].row = rd16(m, b + 8);
        a->tiles[i].count = rd16(m, b + 10);
    }
    a->tick_divider = rd16(m, DS_ANIM_TICK_DIVIDER);
}

static void export_anim(const struct anim_state *a, unsigned char *m) {
    for (int i = 0; i < ANIM_MAX_TILES; i++) {
        unsigned b = DS_ANIM_TILES + 12u * (unsigned)i;
        wr16(m, b + 0, a->tiles[i].active);
        wr16(m, b + 2, a->tiles[i].first);
        wr16(m, b + 4, a->tiles[i].cur);
        wr16(m, b + 6, a->tiles[i].col);
        wr16(m, b + 8, a->tiles[i].row);
        wr16(m, b + 10, a->tiles[i].count);
    }
    wr16(m, DS_ANIM_TICK_DIVIDER, a->tick_divider);
}

static FILE *events;
static long snapshot_index;
static void log_redraw(void *ctx, int view_col, int row, int tile) {
    (void)ctx;
    if (events)
        fprintf(events, "%ld %d %d %d\n", snapshot_index, view_col, row, tile);
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "usage: dave_bridge <subsystem> <in.bin> <out.bin> [events.txt]\n");
        return 2;
    }
    if (strcmp(argv[1], "animate_tiles") != 0) {
        fprintf(stderr, "unknown subsystem %s\n", argv[1]);
        return 2;
    }
    FILE *in = fopen(argv[2], "rb"), *out = fopen(argv[3], "wb");
    if (!in || !out) {
        perror("open");
        return 2;
    }
    events = argc > 4 ? fopen(argv[4], "w") : NULL;
    static unsigned char snap[DGROUP_LEN];
    static struct anim_state a;
    while (fread(snap, 1, DGROUP_LEN, in) == DGROUP_LEN) {
        import_anim(&a, snap);
        anim_step(&a, rd16(snap, DS_SCROLL_X), log_redraw, NULL);
        export_anim(&a, snap);
        fwrite(snap, 1, DGROUP_LEN, out);
        snapshot_index++;
    }
    fclose(in);
    fclose(out);
    if (events)
        fclose(events);
    return 0;
}
