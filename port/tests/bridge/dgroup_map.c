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
    dgroup_import_player_view(g, m);
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
    dgroup_export_player_view(g, m);
}

void dgroup_import_resources(struct resources *r, const unsigned char *m) {
    for (int lv = 0; lv < LEVEL_COUNT; lv++) {
        const unsigned char *rec = m + 0x173A + 0x500 * lv;
        memcpy(r->levels[lv].path, rec, LEVEL_PATH_BYTES);
        memcpy(r->levels[lv].map, rec + 0x100, LEVEL_ROWS * LEVEL_COLS);
    }
    int16_t cur = (int16_t)(m[0x56F4] | (m[0x56F5] << 8));
    if (cur >= 0 && cur < LEVEL_COUNT)
        memcpy(r->levels[cur].map, m + 0x615C, LEVEL_ROWS * LEVEL_COLS);
    dgroup_import_level_tails(r, m);
}

/* ---- player (N2): Dave's pose (D3), the input sample, level tails -------- */

#define DS_GFX_INDEX 0x4F86      /* g_gfx_index: 0 CGA, 1 EGA, 2 VGA */
#define DS_DAVE_SPRITE 0x573E    /* g_dave_sprite */
#define DS_DAVE_MASK 0x57E4      /* g_dave_mask */

/* Per-mode sprite / mask ids of each pose (src/DAVE.C: g_sprite_sets[set]
 * [mode][frame] for the animated poses, g_spr_* / g_mask_* for the still
 * ones, which repeat their one id over the 4 frames). [pose][sprite/mask][mode][frame] */
static const int16_t pose_ids[POSE_JET_LEFT + 1][2][3][4] = {
    [POSE_FRONT] = {{{59, 59, 59, 59}, {65, 65, 65, 65}, {56, 56, 56, 56}},
                    {{73, 73, 73, 73}, {93, 93, 93, 93}, {63, 63, 63, 63}}},
    [POSE_WALK_LEFT] = {{{61, 63, 65, 63}, {69, 73, 77, 73}, {57, 58, 59, 58}},      /* sets 9 / 10 */
                        {{75, 77, 79, 77}, {97, 101, 105, 101}, {64, 65, 66, 65}}},
    [POSE_WALK_RIGHT] = {{{53, 55, 57, 55}, {53, 57, 61, 57}, {53, 54, 55, 54}},     /* sets 11 / 12 */
                         {{67, 69, 71, 69}, {81, 85, 89, 85}, {60, 61, 62, 61}}},
    [POSE_JUMP_LEFT] = {{{83, 83, 83, 83}, {113, 113, 113, 113}, {68, 68, 68, 68}},
                        {{87, 87, 87, 87}, {121, 121, 121, 121}, {70, 70, 70, 70}}},
    [POSE_JUMP_RIGHT] = {{{81, 81, 81, 81}, {109, 109, 109, 109}, {67, 67, 67, 67}},
                         {{85, 85, 85, 85}, {117, 117, 117, 117}, {69, 69, 69, 69}}},
    [POSE_CLIMB] = {{{89, 91, 93, 91}, {125, 129, 133, 129}, {71, 72, 73, 72}},      /* sets 7 / 8 */
                    {{95, 97, 99, 97}, {137, 141, 145, 141}, {74, 75, 76, 75}}},
    [POSE_JET_RIGHT] = {{{101, 103, 105, 103}, {149, 153, 157, 153}, {77, 78, 79, 78}},  /* sets 3 / 4 */
                        {{113, 115, 117, 115}, {173, 177, 181, 177}, {83, 84, 85, 84}}},
    [POSE_JET_LEFT] = {{{107, 109, 111, 109}, {161, 165, 169, 165}, {80, 81, 82, 81}},   /* sets 5 / 6 */
                       {{119, 121, 123, 121}, {185, 189, 193, 189}, {86, 87, 88, 87}}},
};

static int16_t rd16(const unsigned char *m, unsigned ds) { return (int16_t)(m[ds] | (m[ds + 1] << 8)); }
static void wr16(unsigned char *m, unsigned ds, int16_t v)
{
    m[ds] = (unsigned char)(v & 0xFF);
    m[ds + 1] = (unsigned char)((v >> 8) & 0xFF);
}

/* g_dave_sprite + g_dave_mask -> pose, frame (the first frame with that
 * picture: frames 1 and 3 share one). Unknown pairs import as POSE_UNSET,
 * and exporting POSE_UNSET leaves the original bytes untouched. */
void dgroup_import_player_view(struct game *g, const unsigned char *m)
{
    int mode = rd16(m, DS_GFX_INDEX);
    int16_t sprite = rd16(m, DS_DAVE_SPRITE), mask = rd16(m, DS_DAVE_MASK);
    g->dave.pose = POSE_UNSET;
    g->dave.pose_frame = 0;
    if (mode < 0 || mode > 2)
        return;
    for (int p = POSE_FRONT; p <= POSE_JET_LEFT; p++)
        for (int f = 0; f < 4; f++)
            if (pose_ids[p][0][mode][f] == sprite && pose_ids[p][1][mode][f] == mask) {
                g->dave.pose = (uint8_t)p;
                g->dave.pose_frame = (uint8_t)f;
                return;
            }
}

void dgroup_export_player_view(const struct game *g, unsigned char *m)
{
    int mode = rd16(m, DS_GFX_INDEX);
    if (g->dave.pose == POSE_UNSET || g->dave.pose > POSE_JET_LEFT || mode < 0 || mode > 2)
        return;
    wr16(m, DS_DAVE_SPRITE, pose_ids[g->dave.pose][0][mode][g->dave.pose_frame & 3]);
    wr16(m, DS_DAVE_MASK, pose_ids[g->dave.pose][1][mode][g->dave.pose_frame & 3]);
}

#define DS_INPUT_DEVICE 0x12F0   /* int g_input_device[3] */
#define DS_KEY_SCANS 0x1310      /* char g_key_scans[10] */
#define DS_KEYDOWN 0x8A32        /* int g_keydown[128] */

void dgroup_import_input_settings(struct input_settings *s, const unsigned char *m)
{
    s->device = rd16(m, DS_INPUT_DEVICE + 2 * 1);
    for (int k = 0; k < BIND_COUNT; k++)
        s->keys[k] = m[DS_KEY_SCANS + k];
}

int dgroup_import_input(struct frame_input *in, const unsigned char *m)
{
    struct input_settings s;
    dgroup_import_input_settings(&s, m);
    in->dir = DIR_NONE;
    in->fire = 0;
    in->jump = 0;
    in->menu_key = 0;
    in->dos_seconds = 0;
    if (s.device != DEVICE_KEYBOARD)
        return -1;
    uint8_t down[128];
    for (int k = 0; k < 128; k++)
        down[k] = rd16(m, DS_KEYDOWN + 2 * k) != 0;
    input_from_keyboard(in, down, &s);
    return 0;
}

void dgroup_import_level_tails(struct resources *r, const unsigned char *m)
{
    for (int lv = 0; lv < LEVEL_COUNT; lv++)
        memcpy(r->levels[lv].tail, m + 0x173A + 0x500 * lv + 0x100 + LEVEL_ROWS * LEVEL_COLS, 24);
}
