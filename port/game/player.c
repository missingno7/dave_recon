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
 *   g_scroll_x    -> level.scroll_x     g_level (live map) -> level_live_map(g) (D8)
 *   g_actors      -> explosions         g_shots       -> shots
 */
#include "player.h"
#include "level_probe.h"
#include "world.h"   /* tile_at/tile_attr_at, spawn_explosion, draw_actors, wait_for_input ... (N3) */

/* ---- constant tables of the original (src/DAVE.C _DATA) ------------------ */

/* g_jump_dy (DS 0x00BA): y step per jump position; 0x80 ends the rise and
 * switches to falling (U-G2). */
#define JUMP_END 0x80
static const int16_t jump_dy[47] = {
    0, -3, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -1, -1, -1, -1, -1, -1,
    -1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 3, JUMP_END, 0
};

enum { ATTR_FREE = 0, ATTR_SOLID = 1, ATTR_DEADLY = 2 };   /* g_tile_attr values (level_probe.c) */

/* Sounds (PlaySound ids, sound bank SPK). */
enum {
    SND_BUMP = 1, SND_FALL = 2, SND_DEATH = 3, SND_STEP = 4, SND_JUMP = 5,
    SND_JETPACK = 9, SND_JETPACK_ON = 11
};

enum { DIR_LEFT = 0, DIR_RIGHT = 1 };   /* dave.facing / jet_facing / shot.dir */

/* ---- output helpers ------------------------------------------------------- */

/* WaitVBL(). Every call is a boundary between two retrace segments (D2). */
static void retrace(struct frame_output *out) { out->retraces++; }

/* DRAW_SET_DAVE_SPRITE's image code of each pose (output.h). */
static int pose_sprite_code(int pose)
{
    switch (pose) {
    case POSE_WALK_LEFT: return 9;
    case POSE_WALK_RIGHT: return 11;
    case POSE_CLIMB: return 7;
    case POSE_JET_RIGHT: return 3;
    case POSE_JET_LEFT: return 5;
    case POSE_JUMP_LEFT: return -2;
    case POSE_JUMP_RIGHT: return -3;
    default: return -1;                 /* POSE_FRONT */
    }
}

void dave_set_pose(struct game *g, int pose, int frame, struct frame_output *out)
{
    g->dave.pose = (uint8_t)pose;
    g->dave.pose_frame = (uint8_t)frame;
    out_draw(out, DRAW_SET_DAVE_SPRITE, pose_sprite_code(pose), frame, 0, 0);
}

/* draw_dave(): save the background under Dave, then draw his current sprite. */
static void draw_dave(const struct game *g, struct frame_output *out)
{
    out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, 0, 0);
}

/* erase_dave(): restore what draw_dave saved. */
static void erase_dave(struct frame_output *out) { out_draw(out, DRAW_ERASE_DAVE, 0, 0, 0, 0); }

static void xor_sprite(struct frame_output *out, int x, int y, int set, int index)
{
    out_draw(out, DRAW_XOR_SPRITE, x, y, set, index);
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

/* ---- level probes ---------------------------------------------------------- */

/* tile_attr_at / tile_at (tiles.c) take 16-bit offsets from Dave. */
static int attr(const struct game *g, const struct resources *r, int dx, int dy)
{
    return tile_attr_at(g, r, (int16_t)dx, (int16_t)dy);
}

/* g_tile_climbable[tile_at(dx, dy)] (tile_at accepts rows 10, 11: N2-1). */
static int climbable_at(const struct game *g, const struct resources *r, int dx, int dy)
{
    return tile_climbable((int8_t)tile_at(g, r, (int16_t)dx, (int16_t)dy));
}

/* ---- shared sub-routines ---------------------------------------------------- */

static void kill_dave(struct game *g)
{
    /* every deadly-tile death: movement bits cleared, killed bit set; Dave
     * stays alive (0x20) until the next move_dave turns it into the explosion */
    g->dave.state = (uint16_t)((g->dave.state & 0xE0) | DAVE_KILLED);
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
        out_draw(out, DRAW_LEVEL_VIEW, g->level.index, g->level.scroll_x, 0, 0);
        draw_actors(g, out);
    }
    out_sound(out, SOUND_RESUME);
    if (g->dave.y < 16)
        draw_dave(g, out);
}

/* animate_tick(): the climbing animation (every 2nd call). */
static void animate_climb(struct game *g, struct frame_output *out)
{
    if (--g->dave.anim_delay == 0) {
        g->dave.anim_delay = 2;
        g->dave.anim_frame = (int16_t)((g->dave.anim_frame + 1) & 3);
        dave_set_pose(g, POSE_CLIMB, g->dave.anim_frame, out);
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
        if (g->inv.has_gun > 0 && !shot_owner_exists(g, SHOT_OWNER_DAVE) && d->y > 8 && d->y < 0xAA) {
            if (d->facing == DIR_LEFT)
                shot_spawn(g, r, (int16_t)(d->x - 10), (int16_t)(d->y + 7), SHOT_LEFT, SHOT_KIND_DAVE, SHOT_OWNER_DAVE, out);
            else
                shot_spawn(g, r, (int16_t)(d->x + 20), (int16_t)(d->y + 7), SHOT_RIGHT, SHOT_KIND_DAVE, SHOT_OWNER_DAVE, out);
        }
    }

    if (g->buttons.jetpack_repeat == 0 && (d->state & DAVE_ALIVE)) {
        g->buttons.jetpack_repeat = 30;
        if (!(d->state & DAVE_JETPACK) && g->inv.has_jetpack > 0) {
            out_sound(out, SND_JETPACK_ON);
            d->state = (uint16_t)((d->state & 0xE0) | DAVE_JETPACK);
            d->jet_facing = DIR_RIGHT;
            dave_set_pose(g, POSE_JET_RIGHT, d->anim_frame, out);
            if (d->input_dir == DIR_W || d->input_dir == DIR_NW || d->input_dir == DIR_SW) {
                d->jet_facing = DIR_LEFT;
                dave_set_pose(g, POSE_JET_LEFT, d->anim_frame, out);
            }
        } else if ((d->state & DAVE_JETPACK) == DAVE_JETPACK) {
            d->state = (uint16_t)((d->state & 0xFE) | DAVE_FALL);
            out_sound(out, SND_FALL);
            consume_dir(d);
            dave_set_pose(g, POSE_FRONT, 0, out);
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
        if (d->prev_dir == DIR_E && attr(g, r, -2, 0) == ATTR_FREE) {
            d->x -= 2;              /* turn-around step */
            d->prev_dir = d->input_dir;
            moved++;
        }
        d->facing = DIR_LEFT;
        if (attr(g, r, -2, 0) == ATTR_SOLID) {
            consume_dir(d);
            out_sound(out, SND_BUMP);
            break;
        }
        if (attr(g, r, 0, 0) == ATTR_DEADLY) {
            consume_dir(d);
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        if (attr(g, r, 2, 16) == ATTR_FREE && attr(g, r, 8, 16) == ATTR_FREE) {
            out_sound(out, SND_FALL);
            d->state = (uint16_t)((d->state & 0xFB) | DAVE_FALL);
            d->y = (int16_t)((d->y + 1) & 0xFF);    /* 8-bit y (U-G2) */
            d->x--;
            moved++;
        }
        if (attr(g, r, 2, 16) == ATTR_DEADLY) {
            consume_dir(d);
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        if (--d->anim_delay == 0) {
            d->anim_delay = 2;
            d->anim_frame = (int16_t)((d->anim_frame + 1) & 3);
        }
        dave_set_pose(g, POSE_WALK_LEFT, d->anim_frame, out);
        d->x -= 2;
        scroll_screen(g, out);
        out_sound(out, SND_STEP);
        moved++;
        d->input_dir = DIR_NONE;    /* quirk: prev_dir not updated (walking right does) */
        break;
    case DIR_E:
        if (d->prev_dir == DIR_W && attr(g, r, 13, 0) == ATTR_FREE) {
            d->x += 2;              /* turn-around step */
            moved++;
            d->prev_dir = d->input_dir;
        }
        d->facing = DIR_RIGHT;
        if (attr(g, r, 15, 0) == ATTR_SOLID) {
            consume_dir(d);
            out_sound(out, SND_BUMP);
            break;
        }
        if (attr(g, r, 13, 0) == ATTR_DEADLY) {
            consume_dir(d);
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        if (attr(g, r, 5, 16) == ATTR_FREE && attr(g, r, 11, 16) == ATTR_FREE) {
            out_sound(out, SND_FALL);
            d->state = (uint16_t)((d->state & 0xFB) | DAVE_FALL);
            d->y = (int16_t)((d->y + 1) & 0xFF);
            d->x++;
            moved++;
        }
        if (attr(g, r, 9, 16) == ATTR_DEADLY) {
            consume_dir(d);
            out_sound(out, SND_DEATH);
            kill_dave(g);
            break;
        }
        if (--d->anim_delay == 0) {
            d->anim_delay = 2;
            d->anim_frame = (int16_t)((d->anim_frame + 1) & 3);
        }
        dave_set_pose(g, POSE_WALK_RIGHT, d->anim_frame, out);
        d->x += 2;
        scroll_screen(g, out);
        out_sound(out, SND_STEP);
        moved++;
        consume_dir(d);
        break;
    case DIR_N:
        if (climbable_at(g, r, 6, -2) == 1) {   /* grab a ladder above */
            d->state = (uint16_t)((d->state & 0xFB) | DAVE_CLIMB);
            consume_dir(d);
            dave_set_pose(g, POSE_FRONT, 0, out);
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
                dave_set_pose(g, POSE_JUMP_LEFT, 0, out);
            else if (d->facing == DIR_RIGHT)
                dave_set_pose(g, POSE_JUMP_RIGHT, 0, out);
        } else {
            dave_set_pose(g, POSE_JUMP_RIGHT, 0, out);
            d->facing = DIR_RIGHT;
            if (d->input_dir == DIR_NW) {
                dave_set_pose(g, POSE_JUMP_LEFT, 0, out);
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
        if (attr(g, r, -2, 6) != ATTR_SOLID && attr(g, r, -4, 15) != ATTR_SOLID) {
            d->x--;
            dave_set_pose(g, POSE_WALK_LEFT, 0, out);
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
        if (attr(g, r, 13, 6) != ATTR_SOLID && attr(g, r, 15, 15) != ATTR_SOLID) {
            d->x++;
            dave_set_pose(g, POSE_WALK_RIGHT, 0, out);
            scroll_screen(g, out);
            moved++;
        } else {
            consume_dir(d);
        }
        d->facing = DIR_RIGHT;
        break;
    }
    /* what is under the feet: the two attributes ORed (3 = do nothing) */
    switch (attr(g, r, 5, 17) | attr(g, r, 8, 17)) {
    case ATTR_FREE:
        d->y = (int16_t)((d->y + 1) & 0xFF);    /* 8-bit y (U-G2) */
        moved++;
        break;
    case ATTR_SOLID:                            /* landed */
        dave_set_pose(g, POSE_WALK_LEFT, 1, out);
        if (d->prev_dir == DIR_N || d->prev_dir == DIR_S || d->prev_dir == DIR_NONE)
            dave_set_pose(g, POSE_FRONT, 0, out);
        if (prev_dir_is_right(d))
            dave_set_pose(g, POSE_WALK_RIGHT, 1, out);
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
        if (climbable_at(g, r, -2, -2) == 1) {
            d->state = (uint16_t)((d->state & 0xEF) | DAVE_CLIMB);   /* grab the ladder */
            break;
        }
        if ((attr(g, r, -4, 2) | attr(g, r, 0, 15)) == ATTR_SOLID)
            break;
        if ((attr(g, r, -2, 2) | attr(g, r, 2, 13)) == ATTR_DEADLY) {
            out_sound(out, SOUND_STOP);
            out_sound(out, SND_DEATH);
            kill_dave(g);
        }
        dave_set_pose(g, POSE_JUMP_LEFT, 0, out);
        d->x -= 2;
        scroll_screen(g, out);
        break;
    case DIR_NE:
    case DIR_E:
        consume_dir(d);
        d->facing = DIR_RIGHT;
        if (climbable_at(g, r, 13, -2) == 1) {
            d->state = (uint16_t)((d->state & 0xEF) | DAVE_CLIMB);
            break;
        }
        if ((attr(g, r, 15, 2) | attr(g, r, 13, 15)) == ATTR_SOLID)
            break;
        if ((attr(g, r, 13, 2) | attr(g, r, 13, 13)) == ATTR_DEADLY) {
            out_sound(out, SOUND_STOP);
            out_sound(out, SND_DEATH);
            kill_dave(g);
        }
        dave_set_pose(g, POSE_JUMP_RIGHT, 0, out);
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
        int hit = attr(g, r, 4, t + 15) | attr(g, r, 11, t + 15);
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
            dave_set_pose(g, POSE_WALK_LEFT, 1, out);
            if (prev_dir_is_right(d))
                dave_set_pose(g, POSE_WALK_RIGHT, 1, out);
            consume_dir(d);
        }
    }
    if (t < 0) {                                /* rising: bump the head or die */
        int hit = attr(g, r, 4, t + 1) | attr(g, r, 9, t + 1);
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
        if (climbable_at(g, r, 6, -2) == 1) {
            consume_dir(d);
            d->y -= 2;
            out_sound(out, SND_STEP);
            animate_climb(g, out);
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
        if (climbable_at(g, r, 6, 16) == 1) {
            consume_dir(d);
            out_sound(out, SND_STEP);
            d->y += 2;
            out_sound(out, SND_STEP);           /* requested twice, as in the original */
            animate_climb(g, out);
            moved++;
        } else {
            d->state = (uint16_t)((d->state & 0xFD) | DAVE_FALL);
        }
        break;
    case DIR_W:
        if (climbable_at(g, r, 0, 8) == 1) {
            consume_dir(d);
            d->x -= 2;
            scroll_screen(g, out);
            out_sound(out, SND_STEP);
            animate_climb(g, out);
            moved++;
        } else {
            d->state = (uint16_t)((d->state & 0xFD) | DAVE_FALL);
        }
        d->facing = DIR_LEFT;
        break;
    case DIR_E:
        if (climbable_at(g, r, 13, 8) == 1) {
            consume_dir(d);
            d->x += 2;
            scroll_screen(g, out);
            out_sound(out, SND_STEP);
            animate_climb(g, out);
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
        t = attr(g, r, 2, 0) | attr(g, r, 11, 0);
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
        t = attr(g, r, 2, 16) | attr(g, r, 11, 16);
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
            dave_set_pose(g, POSE_FRONT, 0, out);
        }
        moved++;
        break;
    case DIR_W:
        consume_dir(d);
        d->facing = DIR_LEFT;
        t = attr(g, r, -2, 4) | attr(g, r, -2, 12);
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
        t = attr(g, r, 13, 4) | attr(g, r, 13, 12);
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
        dave_set_pose(g, d->jet_facing == DIR_LEFT ? POSE_JET_LEFT : POSE_JET_RIGHT, d->anim_frame, out);
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
        spawn_explosion(g, d->x, (int16_t)(d->y + 3), EXPLOSION_DAVE, out);
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
    xor_sprite(out, g->inv.jetpack_fuel * 2 + 0x4A, 0xAE, SPRITE_METER_BAR, 0);   /* erase a bar */
    g->inv.jetpack_fuel--;
    if (g->inv.jetpack_fuel == 0) {
        draw_status_meter(g, out);              /* XOR: erases the meter frame */
        d->state = (uint16_t)((d->state & 0xE0) | DAVE_FALL);
        g->inv.has_jetpack = 0;
        xor_sprite(out, 0, 0xAA, SPRITE_STATUS, 0);                              /* jetpack icon */
        out_sound(out, SND_FALL);
        consume_dir(d);
        dave_set_pose(g, POSE_FRONT, 0, out);
    }
}

/* ---- handle_death -------------------------------------------------------- */

enum death_result player_handle_death(struct game *g, const struct resources *r,
                                      const struct world_io *io, struct frame_output *out)
{
    struct player *d = &g->dave;

    if (d->state & DAVE_ALIVE)
        return DEATH_NOTHING;
    d->death_timer = (int16_t)(d->death_timer - 1);   /* 16-bit: wraps */
    if (d->death_timer != 0)
        return DEATH_NOTHING;

    if (g->lives > 0)
        xor_sprite(out, (g->lives - 1) * 16 + 0x100, 0, SPRITE_STATUS, 6);   /* life icon */
    g->lives--;
    if (g->lives == -1) {
        if (g->inv.has_jetpack == 1) {
            xor_sprite(out, 0, 0xAA, SPRITE_STATUS, 0);
            draw_status_meter(g, out);
        }
        if (g->inv.has_gun == 1)
            xor_sprite(out, 0xF0, 0xAA, SPRITE_STATUS, 1);
        g->game_over = 1;
        restore_level_map(g, r);
        return DEATH_GAME_OVER;
    }

    /* restart at the level start: monsters back to level coordinates */
    for (int i = 0; i < MONSTER_COUNT; i++)
        if (g->monsters[i].active == 1)
            g->monsters[i].x = (int16_t)(g->monsters[i].x + g->level.scroll_x * 16);
    g->level.scroll_x = 0;
    level_start_position(g->level.index, &d->state, &d->x, &d->y);   /* as load_level */
    d->move_throttle = 3;
    d->anim_delay = 2;
    dave_set_pose(g, POSE_FRONT, 0, out);
    d->anim_frame = 0;
    d->input_dir = DIR_NONE;
    d->facing = DIR_RIGHT;
    if (g->level.in_warp_zone == 1) {
        warp_start_position(g->level.warp_return, &g->level.scroll_x, &d->x);
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
    out_draw(out, DRAW_LEVEL_VIEW, g->level.index, g->level.scroll_x, 0, 0);
    draw_actors(g, out);
    wait_for_input(g, io, out);
    return DEATH_RESTARTED;
}

