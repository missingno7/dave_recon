/* TEST-ONLY bridge mapping; see dgroup_map.h. */
#include <stddef.h>
#include <string.h>
#include "dgroup_map.h"

struct field {
    size_t   off;          /* offsetof(struct game, ...) of element 0 */
    size_t   native_stride;/* bytes between elements in struct game */
    uint16_t ds;           /* DS offset of element 0 */
    uint16_t ds_stride;    /* bytes between elements in DGROUP */
    uint16_t count;        /* elements */
    uint8_t  width;        /* 1, 2 or 4 bytes, little endian */
};

#define ONE(member, ds_, w) \
    { offsetof(struct game, member), 0, ds_, 0, 1, w }
#define ARR(member0, nstride, ds_, dstride, n, w) \
    { offsetof(struct game, member0), nstride, ds_, dstride, n, w }

#define MON(f, k)  ARR(monsters[0].f, sizeof(struct monster), 0x5742 + 8 * (k), 2, MONSTER_COUNT, 2)
#define SHOT(f, k) ARR(shots[0].f, sizeof(struct shot), 0x56F6 + 2 * (k), 14, SHOT_COUNT, 2)
#define EXPL(f, k) ARR(explosions[0].f, sizeof(struct explosion), 0x4F8E + 2 * (k), 0x13A, EXPLOSION_COUNT, 2)
#define ANIM(f, k) ARR(anim.tiles[0].f, sizeof(struct anim_tile), 0x57E8 + 2 * (k), 12, ANIM_MAX_TILES, 2)

static const struct field fields[] = {
    ONE(mode, 0x00AA, 2), ONE(game_over, 0x5792, 2), ONE(rng_seed, 0x4BB6, 4),
    ONE(score, 0x4C60, 4), ONE(next_extra_life, 0x6148, 4), ONE(lives, 0x56EE, 2),
    ONE(dave.x, 0x56EA, 2), ONE(dave.y, 0x56EC, 2), ONE(dave.state, 0x6156, 2),
    ONE(dave.facing, 0x5740, 2), ONE(dave.jet_facing, 0x57E6, 2), ONE(dave.jump_pos, 0x579A, 2),
    ONE(dave.move_throttle, 0x5794, 2), ONE(dave.input_dir, 0x57E2, 2), ONE(dave.prev_dir, 0x579E, 2),
    ONE(dave.anim_frame, 0x6150, 2), ONE(dave.anim_delay, 0x6548, 2), ONE(dave.death_timer, 0x6546, 2),
    ONE(inv.has_gun, 0x4F84, 2), ONE(inv.has_jetpack, 0x4F8A, 2), ONE(inv.got_trophy, 0x4F88, 2),
    ONE(inv.jetpack_fuel, 0x5798, 2), ONE(inv.fuel_tick, 0x6154, 2),
    ONE(level.index, 0x56F4, 2), ONE(level.scroll_x, 0x57A0, 2), ONE(level.done, 0x6158, 2),
    ONE(level.in_warp_zone, 0x573C, 2), ONE(level.warp_return, 0x6152, 2),
    ARR(level.warp_used[0], sizeof(int16_t), 0x57AA, 2, LEVEL_COUNT, 2),
    ANIM(active, 0), ANIM(first, 1), ANIM(cur, 2), ANIM(col, 3), ANIM(row, 4), ANIM(count, 5),
    ONE(anim.tick_divider, 0x615A, 2),
    MON(active, 0), MON(x, 1), MON(y, 2), MON(path_pos, 3), MON(reload, 4),
    /* field 5 (.sprite) is a per-mode presentation id (D3): not game state */
    MON(anim_count, 6), MON(anim_frame, 7), MON(fire_count, 8), MON(move_count, 9),
    SHOT(active, 0), SHOT(x, 1), SHOT(y, 2), SHOT(dir, 3), SHOT(frame, 4), SHOT(kind, 5), SHOT(owner, 6),
    ONE(shot_anim_count, 0x5796, 2),
    EXPL(active, 0), EXPL(x, 1), EXPL(y, 2), EXPL(frame, 3), EXPL(life, 4), EXPL(anim, 5), EXPL(type, 6),
    ONE(buttons.fire_repeat, 0x00AC, 1), ONE(buttons.jetpack_repeat, 0x00AD, 1),
    ONE(demo.pos, 0x57A2, 2), ONE(demo.idle_run, 0x6544, 1),
    ARR(scores[0].level, sizeof(struct score_entry), 0x57BE, 7, SCORE_ENTRIES, 2),
    ARR(scores[0].score16, sizeof(struct score_entry), 0x57C0, 7, SCORE_ENTRIES, 2),
    ARR(scores[0].initials[0], sizeof(struct score_entry), 0x57C2, 7, SCORE_ENTRIES, 1),
    ARR(scores[0].initials[1], sizeof(struct score_entry), 0x57C3, 7, SCORE_ENTRIES, 1),
    ARR(scores[0].initials[2], sizeof(struct score_entry), 0x57C4, 7, SCORE_ENTRIES, 1),
};

/* The live level map is the current record of g_levels (DS 0x173A, 0x500
 * bytes per level, tiles at +0x100). Level -1 (U-M3) addresses DS 0x133A,
 * the same arithmetic the original uses. */
static unsigned map_ds(int16_t index) {
    return (unsigned)(0x173A + 0x500 * (int)index + 0x100) & 0xFFFFu;
}

/* g_monsters.sprite[4] (DS 0x576A) <-> monster.shown_frame (D3, state-model
 * section 5). The id is base[mode] + step[mode] * ((level - 2) * 4 + frame)
 * with mode = g_gfx_index (DS 0x4F86: 0 CGA, 1 EGA, 2 VGA), as move_monsters,
 * redraw_screen and load_level compute it. An id that decodes to no frame
 * 0..3 (e.g. a slot never drawn on this level) imports as
 * MONSTER_FRAME_UNKNOWN and is exported unchanged. */
#define MONSTER_SPRITE_DS 0x576A
#define GFX_INDEX_DS 0x4F86
static const int monster_sprite_base[3] = {0x7D, 0xC5, 0x59};
static const int monster_sprite_step[3] = {2, 4, 1};

static int gfx_mode(const unsigned char *m) {
    int mode = m[GFX_INDEX_DS] | (m[GFX_INDEX_DS + 1] << 8);
    return mode >= 0 && mode <= 2 ? mode : -1;
}

static void import_monster_frames(struct game *g, const unsigned char *m) {
    int mode = gfx_mode(m);
    for (int i = 0; i < MONSTER_COUNT; i++) {
        int16_t id = (int16_t)(m[MONSTER_SPRITE_DS + 2 * i] | (m[MONSTER_SPRITE_DS + 2 * i + 1] << 8));
        g->monsters[i].shown_frame = MONSTER_FRAME_UNKNOWN;
        if (mode < 0)
            continue;
        int rel = id - monster_sprite_base[mode];
        if (rel % monster_sprite_step[mode] != 0)
            continue;
        int frame = rel / monster_sprite_step[mode] - (g->level.index - 2) * 4;
        if (frame >= 0 && frame <= 3)
            g->monsters[i].shown_frame = (int16_t)frame;
    }
}

static void export_monster_frames(const struct game *g, unsigned char *m) {
    int mode = gfx_mode(m);
    for (int i = 0; i < MONSTER_COUNT; i++) {
        if (mode < 0 || g->monsters[i].shown_frame == MONSTER_FRAME_UNKNOWN)
            continue;
        int id = monster_sprite_base[mode] +
                 monster_sprite_step[mode] * ((g->level.index - 2) * 4 + g->monsters[i].shown_frame);
        m[MONSTER_SPRITE_DS + 2 * i] = (unsigned char)(id & 0xFF);
        m[MONSTER_SPRITE_DS + 2 * i + 1] = (unsigned char)((id >> 8) & 0xFF);
    }
}

void dgroup_import(struct game *g, const unsigned char *m) {
    memset(g, 0, sizeof *g);
    for (size_t i = 0; i < sizeof fields / sizeof fields[0]; i++) {
        const struct field *f = &fields[i];
        for (unsigned k = 0; k < f->count; k++) {
            const unsigned char *src = m + f->ds + k * f->ds_stride;
            unsigned char *dst = (unsigned char *)g + f->off + k * f->native_stride;
            memcpy(dst, src, f->width);      /* both sides little endian (checked by the test) */
        }
    }
    unsigned ds = map_ds(g->level.index);
    if (ds + LEVEL_ROWS * LEVEL_COLS <= DGROUP_LEN)
        memcpy(g->level.map, m + ds, LEVEL_ROWS * LEVEL_COLS);
    import_monster_frames(g, m);
}

void dgroup_export(const struct game *g, unsigned char *m) {
    for (size_t i = 0; i < sizeof fields / sizeof fields[0]; i++) {
        const struct field *f = &fields[i];
        for (unsigned k = 0; k < f->count; k++) {
            const unsigned char *src = (const unsigned char *)g + f->off + k * f->native_stride;
            memcpy(m + f->ds + k * f->ds_stride, src, f->width);
        }
    }
    unsigned ds = map_ds(g->level.index);
    if (ds + LEVEL_ROWS * LEVEL_COLS <= DGROUP_LEN)
        memcpy(m + ds, g->level.map, LEVEL_ROWS * LEVEL_COLS);
    export_monster_frames(g, m);
}

void dgroup_import_resources(struct resources *r, const unsigned char *m) {
    for (int lv = 0; lv < LEVEL_COUNT; lv++) {
        const unsigned char *rec = m + 0x173A + 0x500 * lv;
        memcpy(r->levels[lv].path, rec, LEVEL_PATH_BYTES);
        memcpy(r->levels[lv].map, rec + 0x100, LEVEL_ROWS * LEVEL_COLS);
        memcpy(r->levels[lv].trailer, rec + 0x100 + LEVEL_ROWS * LEVEL_COLS, LEVEL_TRAILER_BYTES);
    }
    int16_t cur = (int16_t)(m[0x56F4] | (m[0x56F5] << 8));
    if (cur >= 0 && cur < LEVEL_COUNT)
        memcpy(r->levels[cur].map, m + 0x615C, LEVEL_ROWS * LEVEL_COLS);
}

/* ---- world (N3) additions ---- */

#define G_LEVELS_DS 0x173A
#define G_TILES_DS 0x615C
#define G_KEYDOWN_DS 0x8A32
#define G_KEY_SCANS_DS 0x1310
#define G_INPUT_DEVICE_DS 0x12F0

void dgroup_import_world(struct game *g, struct resources *r, const unsigned char *m,
                         const unsigned char *pristine_levels) {
    if (pristine_levels) {
        /* the immutable resource itself: g_levels as DAVE.EXE initialises it */
        for (int lv = 0; lv < LEVEL_COUNT; lv++) {
            const unsigned char *rec = pristine_levels + LEVEL_RECORD_BYTES * lv;
            memcpy(r->levels[lv].path, rec, LEVEL_PATH_BYTES);
            memcpy(r->levels[lv].map, rec + LEVEL_PATH_BYTES, LEVEL_ROWS * LEVEL_COLS);
            memcpy(r->levels[lv].trailer, rec + LEVEL_PATH_BYTES + LEVEL_ROWS * LEVEL_COLS,
                   LEVEL_TRAILER_BYTES);
        }
    }   /* else: dgroup_import_resources took them from the snapshot */
    /* data:g_tiles -> level.pristine_loaded: still all zero before the first load_level */
    g->level.pristine_loaded = 0;
    for (int i = 0; i < LEVEL_ROWS * LEVEL_COLS; i++)
        if (m[G_TILES_DS + i])
            g->level.pristine_loaded = 1;
}

void dgroup_export_levels(const struct game *g, const struct resources *r, unsigned char *m) {
    for (int lv = 0; lv < LEVEL_COUNT; lv++)
        if (lv != g->level.index)
            memcpy(m + G_LEVELS_DS + LEVEL_RECORD_BYTES * lv + LEVEL_PATH_BYTES,
                   r->levels[lv].map, LEVEL_ROWS * LEVEL_COLS);
    if (g->level.pristine_loaded && g->level.index >= 0 && g->level.index < LEVEL_COUNT)
        memcpy(m + G_TILES_DS, r->levels[g->level.index].map, LEVEL_ROWS * LEVEL_COLS);
    else if (!g->level.pristine_loaded)
        memset(m + G_TILES_DS, 0, LEVEL_ROWS * LEVEL_COLS);
}

void dgroup_import_keyboard(struct dgroup_keyboard *k, const unsigned char *m) {
    for (int i = 0; i < 128; i++)
        k->keydown[i] = (int16_t)(m[G_KEYDOWN_DS + 2 * i] | m[G_KEYDOWN_DS + 2 * i + 1] << 8);
    memcpy(k->scans, m + G_KEY_SCANS_DS, 10);
    k->device = (int16_t)(m[G_INPUT_DEVICE_DS + 2] | m[G_INPUT_DEVICE_DS + 3] << 8);
}
