/*
 * Dave: process_input, move_dave, update_jetpack, handle_death (see player.h
 * for the contract and the list of reproduced quirks).
 *
 * Reading guide: each public function follows the original routine of the
 * same role in src/DAVE.C statement by statement, in the same order, with
 * the original's global names translated to struct game fields:
 *
 *   g_player_x/_y -> dave.x/.y          g_dave_state  -> dave.state
 *   g_death_pause -> dave.move_throttle g_bonus_timer -> dave.death_timer
 *   g_input_dir   -> dave.input_dir     g_prev_dir    -> dave.prev_dir
 *   g_dave_sprite + g_dave_mask         -> dave.pose + dave.pose_frame (D3)
 *   g_scroll_x    -> level.scroll_x     g_level (live map) -> level.map
 *   g_actors      -> explosions         g_shots       -> shots
 */
#include "player.h"

/* ---- constant tables of the original (src/DAVE.C _DATA) ------------------ */

/* g_jump_dy (DS 0x00BA): y step per jump position; 0x80 ends the rise and
 * switches to falling (U-G2). */
#define JUMP_END 0x80
static const int16_t jump_dy[47] = {
    0, -3, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -1, -1, -1, -1, -1, -1,
    -1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 3, JUMP_END, 0
};

/* g_level_flags (DS 0x0118): Dave's state on (re)entering each level (U-G3). */
static const uint8_t level_start_state[LEVEL_COUNT] = {36, 36, 36, 40, 36, 36, 40, 36, 40, 36};
static const int16_t level_start_x[LEVEL_COUNT] = {32, 16, 32, 16, 32, 32, 16, 32, 96, 32};
static const int16_t level_start_y[LEVEL_COUNT] = {144, 144, 96, 96, 144, 144, 48, 144, 32, 144};
/* g_warp_start_scroll_x / g_warp_start_x: where a warp zone (re)starts Dave,
 * indexed by the level the warp was taken from (level.warp_return). */
static const int16_t warp_start_scroll_x[LEVEL_COUNT] = {0, 0, 0, 0, 42, 0, 0, 67, 71, 11};
static const int16_t warp_start_x[LEVEL_COUNT] = {0, 0, 0, 0, 144, 0, 0, 64, 144, 144};

#define TILE_IDS 53
/* g_tile_climbable (DS 0x0262) and g_tile_attr (DS 0x02CC) per tile id. */
static const int16_t tile_climbable[TILE_IDS] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0,
    0, 0, 0, 0
};
enum { ATTR_FREE = 0, ATTR_SOLID = 1, ATTR_DEADLY = 2 };
static const int16_t tile_attr[TILE_IDS] = {
    0, 1, 0, 1, 0, 1, 2, 2, 2, 2, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1,
    2, 2, 2, 2, 1, 1, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0
};

/* Sounds (PlaySound ids, sound bank SPK). */
enum {
    SND_BUMP = 1, SND_FALL = 2, SND_DEATH = 3, SND_STEP = 4, SND_JUMP = 5,
    SND_JETPACK = 9, SND_JETPACK_ON = 11
};

enum { SHOT_KIND_DAVE = 1, SHOT_OWNER_DAVE = 5, EXPLOSION_DEATH = 5 };
enum { DIR_LEFT = 0, DIR_RIGHT = 1 };   /* dave.facing / jet_facing / shot.dir */

/* ---- output helpers ------------------------------------------------------- */

/* WaitVBL(). Every call is a boundary between two retrace segments (D2). */
static void retrace(struct frame_output *out) { out->retraces++; }

static void set_pose(struct game *g, int pose, int frame)
{
    g->dave.pose = (uint8_t)pose;
    g->dave.pose_frame = (uint8_t)frame;
}

/* draw_dave(): save the background under Dave, then draw him. */
static void draw_dave(const struct game *g, struct frame_output *out)
{
    out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, g->dave.pose, g->dave.pose_frame);
}

/* erase_dave(): restore what draw_dave saved. */
static void erase_dave(struct frame_output *out) { out_draw(out, ERASE_DAVE, 0, 0, 0, 0); }

static void xor_sprite(struct frame_output *out, int x, int y, int table, int index)
{
    out_draw(out, XOR_SPRITE, x, y, table, index);
}

/* draw_status_meter(): jetpack meter frame and one bar per fuel unit. */
static void draw_status_meter(const struct game *g, struct frame_output *out)
{
    xor_sprite(out, 0x48, 0xAA, SPRITES_METER_LABEL, 0);
    for (int i = 0; i < g->inv.jetpack_fuel; i++)
        xor_sprite(out, i * 2 + 0x4C, 0xAE, SPRITES_METER_BAR, 0);
}

/* draw_object(i): one shot. */
static void draw_shot(const struct shot *s, struct frame_output *out)
{
    switch (s->kind) {
    case 0:   /* monster shot: animated */
        xor_sprite(out, s->x, s->y, s->dir == 0 ? SPRITES_SET0 + 2 : SPRITES_SET0 + 1, s->frame);
        break;
    case SHOT_KIND_DAVE:
        xor_sprite(out, s->x, s->y, s->dir == 0 ? SPRITES_SHOT_B0 : SPRITES_SHOT_B1, 0);
        break;
    }
}

/* draw_actors(): Dave (if on the playfield and alive), the monsters, the
 * shots and the explosions, in that order. */
static void draw_actors(const struct game *g, struct frame_output *out)
{
    if (g->dave.y > 15 && (g->dave.state & DAVE_ALIVE))
        draw_dave(g, out);
    for (int i = 0; i < MONSTER_COUNT; i++)
        if (g->monsters[i].active == 1)
            xor_sprite(out, g->monsters[i].x, g->monsters[i].y, SPRITES_MONSTER_SLOT, i);
    for (int i = 0; i < SHOT_COUNT; i++)
        if (g->shots[i].active == 1)
            draw_shot(&g->shots[i], out);
    for (int i = 0; i < EXPLOSION_COUNT; i++)
        if (g->explosions[i].active == 1)
            xor_sprite(out, g->explosions[i].x, g->explosions[i].y, SPRITES_SET0, g->explosions[i].frame);
}

/* The end-of-move redraw shared by every movement branch: erase and redraw
 * Dave around the retrace, ordered by the half of the screen he is in so
 * the beam does not catch him half drawn. */
static void redraw_dave_around_retrace(const struct game *g, struct frame_output *out)
{
    if (g->dave.y >= 100)
        retrace(out);
    erase_dave(out);
    draw_dave(g, out);
    if (g->dave.y < 100)
        retrace(out);
}

static void finish_move(const struct game *g, int moved, struct frame_output *out)
{
    if (moved)
        redraw_dave_around_retrace(g, out);
    else
        retrace(out);
}

/* ---- level probes --------------------------------------------------------- */

/* RowTimes100 (tiles.asm, DS 0x13DD) has 10 entries; rows 10..19 read the
 * following table TileRowOfs ((n + 1) * 640). Only tile_at can ask for
 * rows 10 and 11 (and tile_attr_at_offset is unchecked). */
static int row_offset(int row)
{
    if (row >= 0 && row < 10)
        return row * LEVEL_COLS;
    if (row >= 10 && row < 20)
        return (row - 9) * 640;
    return -1000000;   /* out of the equivalence contract (never reached) */
}

/* The byte at flat offset `flat` from the start of the current level's map,
 * as the original's unchecked `g_level[...]` reads it inside g_levels: the
 * live map, then this record's 24-byte tail, then the next record's path;
 * negative offsets read this record's own path. Anything further away is
 * outside the equivalence contract (live BSS after g_levels, level -1:
 * state-model D4) and reads as 0. */
static int level_byte(const struct game *g, const struct resources *r, int flat)
{
    int lv = g->level.index;
    if (lv < 0 || lv >= LEVEL_COUNT)
        return 0;
    if (flat >= 0 && flat < LEVEL_ROWS * LEVEL_COLS)
        return g->level.map[flat / LEVEL_COLS][flat % LEVEL_COLS];
    if (flat >= LEVEL_ROWS * LEVEL_COLS && flat < LEVEL_ROWS * LEVEL_COLS + 24)
        return r->levels[lv].tail[flat - LEVEL_ROWS * LEVEL_COLS];
    if (flat >= LEVEL_ROWS * LEVEL_COLS + 24 && flat < LEVEL_ROWS * LEVEL_COLS + 24 + LEVEL_PATH_BYTES
        && lv + 1 < LEVEL_COUNT)
        return r->levels[lv + 1].path[flat - LEVEL_ROWS * LEVEL_COLS - 24];
    if (flat < 0 && flat >= -LEVEL_PATH_BYTES)
        return r->levels[lv].path[LEVEL_PATH_BYTES + flat];
    return 0;
}

/* g_tile_attr / g_tile_climbable lookups; ids outside 0..52 come only from
 * the out-of-map bytes above, and read neighbouring tables in the original:
 * outside the equivalence contract (no shipped level reaches them). */
static int attr_of(int tile) { return tile >= 0 && tile < TILE_IDS ? tile_attr[tile] : 0; }
static int climbable(int tile) { return tile >= 0 && tile < TILE_IDS ? tile_climbable[tile] : 0; }

/* Column of a view pixel. C division truncates toward zero, so the 15
 * pixels left of the view still map to column scroll_x. */
static int column_at(const struct game *g, int view_x) { return view_x / 16 + g->level.scroll_x; }

/* tile_attr_at(dx, dy): attribute of the tile under Dave + (dx, dy); 0 above
 * the playfield (y < 16) and below row 9. */
static int tile_attr_at(const struct game *g, const struct resources *r, int dx, int dy)
{
    if (g->dave.y + dy < 16)
        return 0;
    int col = column_at(g, dx + g->dave.x);
    int row = (g->dave.y + dy - 16) / 16;
    if (row > 9)
        return 0;
    return attr_of(level_byte(g, r, row_offset(row) + col));
}

/* tile_at(dx, dy): raw tile id under Dave + (dx, dy); rows 10 and 11 are
 * accepted (see row_offset). */
static int tile_at(const struct game *g, const struct resources *r, int dx, int dy)
{
    if (g->dave.y + dy < 16)
        return 0;
    int col = column_at(g, dx + g->dave.x);
    int row = (g->dave.y + dy - 16) / 16;
    if (row > 11)
        return 0;
    return level_byte(g, r, row_offset(row) + col);
}

/* tile_attr_at_offset(x, y, dx, dy): attribute at view pixel (x+dx, y+dy),
 * with no range checks at all. */
static int tile_attr_at_offset(const struct game *g, const struct resources *r,
                               int x, int y, int dx, int dy)
{
    int col = column_at(g, dx + x);
    int row = (y + dy - 16) / 16;
    return attr_of(level_byte(g, r, row_offset(row) + col));
}

/* ---- shared sub-routines ---------------------------------------------------- */

static void kill_dave(struct game *g)
{
    /* every deadly-tile death: movement bits cleared, killed bit set; Dave
     * stays alive (0x20) until the next move_dave turns it into the explosion */
    g->dave.state = (uint16_t)((g->dave.state & 0xE0) | DAVE_KILLED);
}

/* spawn_explosion(x, y, type): first free slot; type 5 arms the death timer. */
static void spawn_explosion(struct game *g, int x, int y, int type, struct frame_output *out)
{
    for (int i = 0; i < EXPLOSION_COUNT; i++) {
        struct explosion *e = &g->explosions[i];
        if (e->active == 0) {
            e->x = (int16_t)x;
            e->y = (int16_t)y;
            e->type = (int16_t)type;
            e->active = 1;
            e->frame = 0;
            e->life = 0x6E;
            e->anim = 0xD;
            xor_sprite(out, x, y, SPRITES_SET0, 0);
            if (type == EXPLOSION_DEATH)
                g->dave.death_timer = 300;
            break;
        }
    }
}

/* object_exists(id) */
static int shot_exists(const struct game *g, int owner)
{
    for (int i = 0; i < SHOT_COUNT; i++)
        if (g->shots[i].active == 1 && g->shots[i].owner == owner)
            return 1;
    return 0;
}

/* spawn_object(x, y, dir, kind, owner): unless the tile just below (x, y)
 * is solid, fill the first free shot slot and draw it once. */
static void spawn_shot(struct game *g, const struct resources *r, int x, int y, int dir, int kind,
                       int owner, struct frame_output *out)
{
    if (tile_attr_at_offset(g, r, x, y, 0, 1) == ATTR_SOLID)
        return;
    for (int i = 0; i < SHOT_COUNT; i++) {
        struct shot *s = &g->shots[i];
        if (s->active == 0) {
            s->active = 1;
            s->x = (int16_t)x;
            s->y = (int16_t)y;
            s->owner = (int16_t)owner;
            s->dir = (int16_t)dir;
            s->frame = 0;
            s->kind = (int16_t)kind;
            draw_shot(s, out);
            return;
        }
    }
}

/* scroll_screen(): when Dave passes x 0x118 (or drops below 0x20) the view
 * scrolls 15 columns, one per retrace, moving every entity by 16 px. */
static void scroll_screen(struct game *g, struct frame_output *out)
{
    int step;
    if (g->dave.x > 0x118 && g->level.scroll_x < 80) {
        step = 1;
        out_sound(out, SOUND_PAUSE);
        if (g->dave.y < 16)
            erase_dave(out);
    } else if (g->dave.x < 0x20 && g->level.scroll_x > 0) {
        step = -1;
        /* the left scroll erases before pausing the sound (the right one after) */
        if (g->dave.y < 16)
            erase_dave(out);
        out_sound(out, SOUND_PAUSE);
    } else {
        return;
    }
    for (int j = 0; j < 15; j++) {
        if (step > 0 ? g->level.scroll_x >= 80 : g->level.scroll_x <= 0)
            break;
        g->level.scroll_x = (int16_t)(g->level.scroll_x + step);
        /* every slot moves, active or not (16-bit arithmetic) */
        for (int i = 0; i < MONSTER_COUNT; i++)
            g->monsters[i].x = (int16_t)(g->monsters[i].x - 16 * step);
        for (int i = 0; i < SHOT_COUNT; i++)
            g->shots[i].x = (int16_t)(g->shots[i].x - 16 * step);
        for (int i = 0; i < EXPLOSION_COUNT; i++)
            g->explosions[i].x = (int16_t)(g->explosions[i].x - 16 * step);
        g->dave.x = (int16_t)(g->dave.x - 16 * step);
        retrace(out);
        out_draw(out, DRAW_LEVEL_VIEW, g->level.scroll_x, g->level.index, 0, 0);
        draw_actors(g, out);
    }
    out_sound(out, SOUND_RESUME);
    if (g->dave.y < 16)
        draw_dave(g, out);
}

/* animate_tick(): the climbing animation (every 2nd call). */
static void animate_climb(struct game *g)
{
    if (--g->dave.anim_delay == 0) {
        g->dave.anim_delay = 2;
        g->dave.anim_frame = (int16_t)((g->dave.anim_frame + 1) & 3);
        set_pose(g, POSE_CLIMB, g->dave.anim_frame);
    }
}

/* Consume the latched direction: remember it, then clear the latch. */
static void consume_dir(struct player *d)
{
    d->prev_dir = d->input_dir;
    d->input_dir = DIR_NONE;
}

static int prev_dir_is_right(const struct player *d)
{
    return d->prev_dir == DIR_E || d->prev_dir == DIR_NE || d->prev_dir == DIR_SE;
}

/* ---- process_input ------------------------------------------------------- */

static int demo_byte(const struct resources *r, int16_t pos)
{
    /* the bank is read through a signed `char far *` */
    return pos >= 0 && pos < DEMO_BANK_BYTES ? (int8_t)r->demo_bank[pos] : 0;
}

/* `signed char >> 6`: arithmetic shift written out (floor division). */
static int16_t shift_right_6(int b) { return (int16_t)(b >= 0 ? b / 64 : -((-b + 63) / 64)); }

static enum menu_request handle_menu_key(const struct game *g, const struct frame_input *in)
{
    switch (in->menu_key) {
    case SCAN_F1: return MENU_HELP;
    case SCAN_F2: return MENU_CONTROL_PANEL;
    case SCAN_F3: return MENU_RESTART;
    case SCAN_F9: return MENU_PAUSE;
    case SCAN_ESC:
    case SCAN_F10: return MENU_QUIT;
    default:
        return g->mode == MODE_DEMO && in->menu_key != 0 ? MENU_END_DEMO : MENU_NONE;
    }
}

static void restore_level_map(struct game *g, const struct resources *r)
{
    /* movmem(g_tiles, g_level, 1000): back to the pristine map */
    if (g->level.index >= 0 && g->level.index < LEVEL_COUNT)
        for (int row = 0; row < LEVEL_ROWS; row++)
            for (int col = 0; col < LEVEL_COLS; col++)
                g->level.map[row][col] = r->levels[g->level.index].map[row][col];
}

enum menu_request player_process_input(struct game *g, const struct resources *r,
                                       const struct frame_input *in, struct frame_output *out)
{
    struct player *d = &g->dave;
    int16_t dir = in->dir, fire = in->fire, jump = in->jump;

    if (g->mode == MODE_DEMO) {
        if (g->demo.idle_run == 0) {
            int b = demo_byte(r, g->demo.pos);
            if (b == ' ') {                 /* ' ' n: the next n calls are idle */
                g->demo.pos++;
                g->demo.idle_run = (int8_t)demo_byte(r, g->demo.pos);
                g->demo.pos++;              /* this call keeps the live input */
            } else if (b == '0') {          /* end of demo: on to the high scores */
                g->mode++;                  /* position not advanced; live input kept */
                restore_level_map(g, r);
            } else {
                dir = (int16_t)(b & 0xF);
                fire = (int16_t)((b >> 7) & 1);
                jump = shift_right_6(b);    /* -1 / -2 when the fire bit is set */
                g->demo.pos++;
            }
        } else {
            g->demo.idle_run--;             /* signed char: wraps (8-bit) */
            dir = DIR_NONE;
            fire = 0;
            jump = 0;
        }
    }

    /* the latch only takes the directions move_dave acts on: diagonals down
     * are walks, anything else (none, or demo nibbles 9..15) keeps it */
    switch (dir) {
    case DIR_S: d->input_dir = DIR_S; break;
    case DIR_SW:
    case DIR_W: d->input_dir = DIR_W; break;
    case DIR_E:
    case DIR_SE: d->input_dir = DIR_E; break;
    case DIR_N: d->input_dir = DIR_N; break;
    case DIR_NW: d->input_dir = DIR_NW; break;
    case DIR_NE: d->input_dir = DIR_NE; break;
    }

    /* release-triggered buttons (U-G9 b): a held button counts down from 30;
     * releasing it before 30 calls passed drops the counter to 0 */
    if (g->buttons.fire_repeat > 0 && fire == 1)
        g->buttons.fire_repeat--;
    if (g->buttons.fire_repeat != 30 && fire == 0)
        g->buttons.fire_repeat = 0;
    if (g->buttons.jetpack_repeat > 0 && jump == 1)
        g->buttons.jetpack_repeat--;
    if (g->buttons.jetpack_repeat != 30 && jump == 0)
        g->buttons.jetpack_repeat = 0;
    /* (the original's demo recorder block here is dead: g_demo_recording
     * is never set, state-model.md section 4) */

    if (g->buttons.fire_repeat == 0 && (d->state & DAVE_ALIVE)) {
        g->buttons.fire_repeat = 30;
        if (g->inv.has_gun > 0 && !shot_exists(g, SHOT_OWNER_DAVE) && d->y > 8 && d->y < 0xAA) {
            if (d->facing == DIR_LEFT)
                spawn_shot(g, r, d->x - 10, d->y + 7, 0, SHOT_KIND_DAVE, SHOT_OWNER_DAVE, out);
            else
                spawn_shot(g, r, d->x + 20, d->y + 7, 1, SHOT_KIND_DAVE, SHOT_OWNER_DAVE, out);
        }
    }

    if (g->buttons.jetpack_repeat == 0 && (d->state & DAVE_ALIVE)) {
        g->buttons.jetpack_repeat = 30;
        if (!(d->state & DAVE_JETPACK) && g->inv.has_jetpack > 0) {
            out_sound(out, SND_JETPACK_ON);
            d->state = (uint16_t)((d->state & 0xE0) | DAVE_JETPACK);
            d->jet_facing = DIR_RIGHT;
            set_pose(g, POSE_JET_RIGHT, d->anim_frame);
            if (d->input_dir == DIR_W || d->input_dir == DIR_NW || d->input_dir == DIR_SW) {
                d->jet_facing = DIR_LEFT;
                set_pose(g, POSE_JET_LEFT, d->anim_frame);
            }
        } else if ((d->state & DAVE_JETPACK) == DAVE_JETPACK) {
            d->state = (uint16_t)((d->state & 0xFE) | DAVE_FALL);
            out_sound(out, SND_FALL);
            consume_dir(d);
            set_pose(g, POSE_FRONT, 0);
        }
    }

    return handle_menu_key(g, in);
}

/* ---- move_dave: one branch per movement bit, in the original's order ---- */

static void walk(struct game *g, const struct resources *r, struct frame_output *out)
{
    struct player *d = &g->dave;
    int moved = 0;

    switch (d->input_dir) {
    case DIR_W:
        if (d->prev_dir == DIR_E && tile_attr_at(g, r, -2, 0) == ATTR_FREE) {
            d->x -= 2;              /* turn-around step */
            d->prev_dir = d->input_dir;
            moved++;
        }
        d->facing = DIR_LEFT;
        if (tile_attr_at(g, r, -2, 0) == ATTR_SOLID) {
            consume_dir(d);
            out_sound(out, SND_BUMP);
            break;
        }
        if (tile_attr_at(g, r, 0, 0) == ATTR_DEADLY) {
            consume_dir(d);
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        if (tile_attr_at(g, r, 2, 16) == ATTR_FREE && tile_attr_at(g, r, 8, 16) == ATTR_FREE) {
            out_sound(out, SND_FALL);
            d->state = (uint16_t)((d->state & 0xFB) | DAVE_FALL);
            d->y = (int16_t)((d->y + 1) & 0xFF);    /* 8-bit y (U-G2) */
            d->x--;
            moved++;
        }
        if (tile_attr_at(g, r, 2, 16) == ATTR_DEADLY) {
            consume_dir(d);
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        if (--d->anim_delay == 0) {
            d->anim_delay = 2;
            d->anim_frame = (int16_t)((d->anim_frame + 1) & 3);
        }
        set_pose(g, POSE_WALK_LEFT, d->anim_frame);
        d->x -= 2;
        scroll_screen(g, out);
        out_sound(out, SND_STEP);
        moved++;
        d->input_dir = DIR_NONE;    /* quirk: prev_dir not updated (walking right does) */
        break;
    case DIR_E:
        if (d->prev_dir == DIR_W && tile_attr_at(g, r, 13, 0) == ATTR_FREE) {
            d->x += 2;              /* turn-around step */
            moved++;
            d->prev_dir = d->input_dir;
        }
        d->facing = DIR_RIGHT;
        if (tile_attr_at(g, r, 15, 0) == ATTR_SOLID) {
            consume_dir(d);
            out_sound(out, SND_BUMP);
            break;
        }
        if (tile_attr_at(g, r, 13, 0) == ATTR_DEADLY) {
            consume_dir(d);
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        if (tile_attr_at(g, r, 5, 16) == ATTR_FREE && tile_attr_at(g, r, 11, 16) == ATTR_FREE) {
            out_sound(out, SND_FALL);
            d->state = (uint16_t)((d->state & 0xFB) | DAVE_FALL);
            d->y = (int16_t)((d->y + 1) & 0xFF);
            d->x++;
            moved++;
        }
        if (tile_attr_at(g, r, 9, 16) == ATTR_DEADLY) {
            consume_dir(d);
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        if (--d->anim_delay == 0) {
            d->anim_delay = 2;
            d->anim_frame = (int16_t)((d->anim_frame + 1) & 3);
        }
        set_pose(g, POSE_WALK_RIGHT, d->anim_frame);
        d->x += 2;
        scroll_screen(g, out);
        out_sound(out, SND_STEP);
        moved++;
        consume_dir(d);
        break;
    case DIR_N:
        if (climbable(tile_at(g, r, 6, -2)) == 1) {   /* grab a ladder above */
            d->state = (uint16_t)((d->state & 0xFB) | DAVE_CLIMB);
            consume_dir(d);
            set_pose(g, POSE_FRONT, 0);
            break;
        }
        /* no ladder: jump straight up (falls through, as in the original) */
        /* fall through */
    case DIR_NE:
    case DIR_NW:
        d->jump_pos = 0;
        out_sound(out, SND_JUMP);
        d->state = (uint16_t)((d->state & 0xFB) | DAVE_JUMP);
        if (d->input_dir == DIR_N) {
            if (d->facing == DIR_LEFT)
                set_pose(g, POSE_JUMP_LEFT, 0);
            else if (d->facing == DIR_RIGHT)
                set_pose(g, POSE_JUMP_RIGHT, 0);
        } else {
            set_pose(g, POSE_JUMP_RIGHT, 0);
            d->facing = DIR_RIGHT;
            if (d->input_dir == DIR_NW) {
                set_pose(g, POSE_JUMP_LEFT, 0);
                d->facing = DIR_LEFT;
            }
        }
        consume_dir(d);
        break;
    }
    finish_move(g, moved, out);
}

static void fall(struct game *g, const struct resources *r, struct frame_output *out)
{
    struct player *d = &g->dave;
    int moved = 0;

    switch (d->input_dir) {
    case DIR_N:
    case DIR_S:
        consume_dir(d);
        break;
    case DIR_SW:
    case DIR_W:
    case DIR_NW:
        if (tile_attr_at(g, r, -2, 6) != ATTR_SOLID && tile_attr_at(g, r, -4, 15) != ATTR_SOLID) {
            d->x--;
            set_pose(g, POSE_WALK_LEFT, 0);
            scroll_screen(g, out);
            moved++;
        } else {
            consume_dir(d);
        }
        d->facing = DIR_LEFT;
        break;
    case DIR_NE:
    case DIR_E:
    case DIR_SE:
        if (tile_attr_at(g, r, 13, 6) != ATTR_SOLID && tile_attr_at(g, r, 15, 15) != ATTR_SOLID) {
            d->x++;
            set_pose(g, POSE_WALK_RIGHT, 0);
            scroll_screen(g, out);
            moved++;
        } else {
            consume_dir(d);
        }
        d->facing = DIR_RIGHT;
        break;
    }
    /* what is under the feet: the two attributes ORed (3 = do nothing) */
    switch (tile_attr_at(g, r, 5, 17) | tile_attr_at(g, r, 8, 17)) {
    case ATTR_FREE:
        d->y = (int16_t)((d->y + 1) & 0xFF);    /* 8-bit y (U-G2) */
        moved++;
        break;
    case ATTR_SOLID:                            /* landed */
        set_pose(g, POSE_WALK_LEFT, 1);
        if (d->prev_dir == DIR_N || d->prev_dir == DIR_S || d->prev_dir == DIR_NONE)
            set_pose(g, POSE_FRONT, 0);
        if (prev_dir_is_right(d))
            set_pose(g, POSE_WALK_RIGHT, 1);
        d->state = (uint16_t)((d->state & 0xF7) | DAVE_WALK);
        d->y = (int16_t)((d->y + 1) & 0xF0);    /* snap to the tile row */
        out_sound(out, SOUND_STOP);
        moved++;
        break;
    case ATTR_DEADLY:
        d->input_dir = DIR_NONE;
        out_sound(out, SOUND_STOP);
        out_sound(out, SND_DEATH);
        kill_dave(g);
        break;
    }
    finish_move(g, moved, out);
}

static void jump(struct game *g, const struct resources *r, struct frame_output *out)
{
    struct player *d = &g->dave;

    switch (d->input_dir) {
    case DIR_W:
    case DIR_NW:
        consume_dir(d);
        d->facing = DIR_LEFT;
        if (climbable(tile_at(g, r, -2, -2)) == 1) {
            d->state = (uint16_t)((d->state & 0xEF) | DAVE_CLIMB);   /* grab the ladder */
            break;
        }
        if ((tile_attr_at(g, r, -4, 2) | tile_attr_at(g, r, 0, 15)) == ATTR_SOLID)
            break;
        if ((tile_attr_at(g, r, -2, 2) | tile_attr_at(g, r, 2, 13)) == ATTR_DEADLY) {
            out_sound(out, SOUND_STOP);
            out_sound(out, SND_DEATH);
            kill_dave(g);
        }
        set_pose(g, POSE_JUMP_LEFT, 0);
        d->x -= 2;
        scroll_screen(g, out);
        break;
    case DIR_NE:
    case DIR_E:
        consume_dir(d);
        d->facing = DIR_RIGHT;
        if (climbable(tile_at(g, r, 13, -2)) == 1) {
            d->state = (uint16_t)((d->state & 0xEF) | DAVE_CLIMB);
            break;
        }
        if ((tile_attr_at(g, r, 15, 2) | tile_attr_at(g, r, 13, 15)) == ATTR_SOLID)
            break;
        if ((tile_attr_at(g, r, 13, 2) | tile_attr_at(g, r, 13, 13)) == ATTR_DEADLY) {
            out_sound(out, SOUND_STOP);
            out_sound(out, SND_DEATH);
            kill_dave(g);
        }
        set_pose(g, POSE_JUMP_RIGHT, 0);
        d->x += 2;
        scroll_screen(g, out);
        break;
    }

    /* the vertical step: also runs after a ladder grab or a kill above, so
     * the jump's last step can add the fall bit to the climb bit (U-G9 a) */
    int t = jump_dy[d->jump_pos];
    if (t == JUMP_END) {
        t = 0;
        d->state = (uint16_t)((d->state & 0xEF) | DAVE_FALL);
    }
    if (t > 0) {                                /* descending: land or die */
        int hit = tile_attr_at(g, r, 4, t + 15) | tile_attr_at(g, r, 11, t + 15);
        if (hit == ATTR_DEADLY) {
            out_sound(out, SOUND_STOP);
            out_sound(out, SND_DEATH);
            kill_dave(g);
        }
        if (hit == ATTR_SOLID) {
            out_sound(out, SOUND_STOP);
            d->state = (uint16_t)((d->state & 0xEF) | DAVE_WALK);
            d->y = (int16_t)((d->y + t) & 0xF0);
            t = 0;
            set_pose(g, POSE_WALK_LEFT, 1);
            if (prev_dir_is_right(d))
                set_pose(g, POSE_WALK_RIGHT, 1);
            consume_dir(d);
        }
    }
    if (t < 0) {                                /* rising: bump the head or die */
        int hit = tile_attr_at(g, r, 4, t + 1) | tile_attr_at(g, r, 9, t + 1);
        if (hit == ATTR_DEADLY) {
            out_sound(out, SOUND_STOP);
            out_sound(out, SND_DEATH);
            kill_dave(g);
        }
        if (hit == ATTR_SOLID) {
            d->state = (uint16_t)((d->state & 0xEF) | DAVE_FALL);
            t = 0;
            d->y = (int16_t)((d->y - 1) & 0xFF);
        }
    }
    d->y = (int16_t)((d->y + t) & 0xFF);        /* 8-bit y: through the top it wraps to 240..255 */
    d->jump_pos++;
    redraw_dave_around_retrace(g, out);         /* a jump step always redraws */
}

static void climb(struct game *g, const struct resources *r, struct frame_output *out)
{
    struct player *d = &g->dave;
    int moved = 0;

    switch (d->input_dir) {
    case DIR_NE:
    case DIR_NW:                                /* jump off the ladder sideways */
        d->jump_pos = 0;
        out_sound(out, SND_JUMP);
        d->state = (uint16_t)((d->state & 0xFD) | DAVE_JUMP);
        {
            int right = d->input_dir == DIR_NE;
            consume_dir(d);
            d->x = (int16_t)(d->x + (right ? 2 : -2));
            d->y -= 2;
            scroll_screen(g, out);
            d->facing = right ? DIR_RIGHT : DIR_LEFT;
        }
        moved++;
        break;
    case DIR_N:
        if (climbable(tile_at(g, r, 6, -2)) == 1) {
            consume_dir(d);
            d->y -= 2;
            out_sound(out, SND_STEP);
            animate_climb(g);
        } else {                                /* top of the ladder: a jump */
            d->jump_pos = 0;
            out_sound(out, SND_JUMP);
            d->state = (uint16_t)((d->state & 0xFD) | DAVE_JUMP);
            consume_dir(d);
            d->y -= 2;
        }
        moved++;
        break;
    case DIR_S:
        if (climbable(tile_at(g, r, 6, 16)) == 1) {
            consume_dir(d);
            out_sound(out, SND_STEP);
            d->y += 2;
            out_sound(out, SND_STEP);           /* requested twice, as in the original */
            animate_climb(g);
            moved++;
        } else {
            d->state = (uint16_t)((d->state & 0xFD) | DAVE_FALL);
        }
        break;
    case DIR_W:
        if (climbable(tile_at(g, r, 0, 8)) == 1) {
            consume_dir(d);
            d->x -= 2;
            scroll_screen(g, out);
            out_sound(out, SND_STEP);
            animate_climb(g);
            moved++;
        } else {
            d->state = (uint16_t)((d->state & 0xFD) | DAVE_FALL);
        }
        d->facing = DIR_LEFT;
        break;
    case DIR_E:
        if (climbable(tile_at(g, r, 13, 8)) == 1) {
            consume_dir(d);
            d->x += 2;
            scroll_screen(g, out);
            out_sound(out, SND_STEP);
            animate_climb(g);
            moved++;
        } else {
            d->state = (uint16_t)((d->state & 0xFD) | DAVE_FALL);
        }
        d->facing = DIR_RIGHT;
        break;
    }
    finish_move(g, moved, out);
}

static void fly(struct game *g, const struct resources *r, struct frame_output *out)
{
    struct player *d = &g->dave;
    int moved = 0;
    int t;

    out_sound(out, SND_JETPACK);
    switch (d->input_dir) {
    case DIR_N:
    case DIR_NE:
    case DIR_NW:
        consume_dir(d);
        t = tile_attr_at(g, r, 2, 0) | tile_attr_at(g, r, 11, 0);
        if ((t & 1) == 1) {
            d->state = (uint16_t)((d->state & 0xFE) | DAVE_JETPACK);   /* (no change) */
            break;
        }
        if (t == ATTR_DEADLY) {
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        if (d->y > 0)
            d->y--;
        moved++;
        break;
    case DIR_S:
        consume_dir(d);
        t = tile_attr_at(g, r, 2, 16) | tile_attr_at(g, r, 11, 16);
        if ((t & 1) == 1) {
            d->state = (uint16_t)((d->state & 0xFE) | DAVE_JETPACK);
            break;
        }
        if (t == ATTR_DEADLY) {
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        if (d->y < 0xAA) {
            d->y++;
        } else {                                /* bottom of the screen: drop out */
            d->state = (uint16_t)((d->state & 0xFE) | DAVE_FALL);
            set_pose(g, POSE_FRONT, 0);
        }
        moved++;
        break;
    case DIR_W:
        consume_dir(d);
        d->facing = DIR_LEFT;
        t = tile_attr_at(g, r, -2, 4) | tile_attr_at(g, r, -2, 12);
        if (t == ATTR_SOLID)
            break;
        if (t == ATTR_DEADLY) {
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        d->x--;                                 /* also when t == 3 */
        moved++;
        scroll_screen(g, out);
        d->jet_facing = DIR_LEFT;
        break;
    case DIR_E:
        consume_dir(d);
        d->facing = DIR_RIGHT;
        t = tile_attr_at(g, r, 13, 4) | tile_attr_at(g, r, 13, 12);
        if (t == ATTR_SOLID)
            break;
        if (t == ATTR_DEADLY) {
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        d->x++;
        moved++;
        scroll_screen(g, out);
        d->jet_facing = DIR_RIGHT;
        break;
    }
    if (--d->anim_delay == 0) {
        d->anim_delay = 4;
        d->anim_frame = (int16_t)((d->anim_frame + 1) & 3);
        set_pose(g, d->jet_facing == DIR_LEFT ? POSE_JET_LEFT : POSE_JET_RIGHT, d->anim_frame);
        moved++;
    }
    finish_move(g, moved, out);
}

void player_move(struct game *g, const struct resources *r, struct frame_output *out)
{
    struct player *d = &g->dave;

    if (!(d->state & DAVE_ALIVE)) {
        retrace(out);
        return;
    }
    /* movement throttle (U-G2): walk every 3rd call, jump/climb every 2nd,
     * fall and jetpack every call */
    d->move_throttle--;
    if ((d->move_throttle > 0 && (d->state & DAVE_WALK)) ||
        (d->move_throttle > 3 && (d->state & DAVE_FALL)) ||
        (d->move_throttle > 1 && ((d->state & DAVE_JUMP) || (d->state & DAVE_CLIMB)))) {
        retrace(out);
        return;
    }
    d->move_throttle = 3;

    /* first matching bit wins (U-G9 a) */
    if (d->state & DAVE_WALK)
        walk(g, r, out);
    else if (d->state & DAVE_FALL)
        fall(g, r, out);
    else if (d->state & DAVE_JUMP)
        jump(g, r, out);
    else if (d->state & DAVE_CLIMB)
        climb(g, r, out);
    else if (d->state & DAVE_JETPACK)
        fly(g, r, out);
    else if (d->state & DAVE_KILLED) {
        /* killed on a tile: no retrace on this path */
        d->state = 0;
        erase_dave(out);
        spawn_explosion(g, d->x, d->y + 3, EXPLOSION_DEATH, out);
    }
}

/* ---- update_jetpack ------------------------------------------------------ */

void player_update_jetpack(struct game *g, struct frame_output *out)
{
    struct player *d = &g->dave;

    if (!(d->state & DAVE_JETPACK))
        return;
    if (--g->inv.fuel_tick != 0)
        return;
    g->inv.fuel_tick = 15;
    xor_sprite(out, g->inv.jetpack_fuel * 2 + 0x4A, 0xAE, SPRITES_METER_BAR, 0);   /* erase a bar */
    g->inv.jetpack_fuel--;
    if (g->inv.jetpack_fuel == 0) {
        draw_status_meter(g, out);              /* XOR: erases the meter frame */
        d->state = (uint16_t)((d->state & 0xE0) | DAVE_FALL);
        g->inv.has_jetpack = 0;
        xor_sprite(out, 0, 0xAA, SPRITES_STATUS, 0);                              /* jetpack icon */
        out_sound(out, SND_FALL);
        consume_dir(d);
        set_pose(g, POSE_FRONT, 0);
    }
}

/* ---- handle_death -------------------------------------------------------- */

enum death_result player_handle_death(struct game *g, const struct resources *r,
                                      struct frame_output *out)
{
    struct player *d = &g->dave;

    if (d->state & DAVE_ALIVE)
        return DEATH_NOTHING;
    d->death_timer = (int16_t)(d->death_timer - 1);   /* 16-bit: wraps */
    if (d->death_timer != 0)
        return DEATH_NOTHING;

    if (g->lives > 0)
        xor_sprite(out, (g->lives - 1) * 16 + 0x100, 0, SPRITES_STATUS, 6);   /* life icon */
    g->lives--;
    if (g->lives == -1) {
        if (g->inv.has_jetpack == 1) {
            xor_sprite(out, 0, 0xAA, SPRITES_STATUS, 0);
            draw_status_meter(g, out);
        }
        if (g->inv.has_gun == 1)
            xor_sprite(out, 0xF0, 0xAA, SPRITES_STATUS, 1);
        g->game_over = 1;
        restore_level_map(g, r);
        return DEATH_GAME_OVER;
    }

    /* restart at the level start: monsters back to level coordinates */
    for (int i = 0; i < MONSTER_COUNT; i++)
        if (g->monsters[i].active == 1)
            g->monsters[i].x = (int16_t)(g->monsters[i].x + g->level.scroll_x * 16);
    g->level.scroll_x = 0;
    int lv = g->level.index;
    if (lv >= 0 && lv < LEVEL_COUNT) {          /* level -1: out of contract (D4) */
        d->state = level_start_state[lv];
        d->x = level_start_x[lv];
        d->y = level_start_y[lv];
    }
    d->move_throttle = 3;
    d->anim_delay = 2;
    set_pose(g, POSE_FRONT, 0);
    d->anim_frame = 0;
    d->input_dir = DIR_NONE;
    d->facing = DIR_RIGHT;
    if (g->level.in_warp_zone == 1) {
        int from = g->level.warp_return;
        if (from >= 0 && from < LEVEL_COUNT) {
            g->level.scroll_x = warp_start_scroll_x[from];
            d->x = warp_start_x[from];
        }
        d->y = 0x10;
        d->state = DAVE_ALIVE | DAVE_FALL;
        for (int i = 0; i < MONSTER_COUNT; i++)
            if (g->monsters[i].active)          /* != 0 here, == 1 above */
                g->monsters[i].x = (int16_t)(g->monsters[i].x - g->level.scroll_x * 16);
    }
    draw_dave(g, out);
    for (int i = 0; i < EXPLOSION_COUNT; i++)
        g->explosions[i].active = 0;
    for (int i = 0; i < SHOT_COUNT; i++)
        g->shots[i].active = 0;
    retrace(out);
    out_draw(out, DRAW_LEVEL_VIEW, g->level.scroll_x, g->level.index, 0, 0);
    draw_actors(g, out);
    return DEATH_RESTARTED;                     /* the caller runs wait_for_input */
}

int player_wait_for_input_round(struct game *g, const struct frame_input *in,
                                struct frame_output *out)
{
    erase_dave(out);
    for (int i = 0; i < 10; i++) {
        retrace(out);
        anim_step(&g->anim, g->level.scroll_x, out);
    }
    draw_dave(g, out);
    for (int i = 0; i < 10; i++) {
        retrace(out);
        anim_step(&g->anim, g->level.scroll_x, out);
    }
    if (in->dir == DIR_NONE && in->menu_key == 0)
        return 0;
    if ((g->dave.state & DAVE_FALL) == DAVE_FALL)
        out_sound(out, SND_FALL);
    return 1;
}
