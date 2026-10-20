/*
 * pick_up_items (DAVE.C cs 0x3DD5, census F_3FD5): what Dave collects from
 * the 2x2 tiles under his top-left corner.
 *
 * Order of effects kept from the original (its four expanded copies of one
 * macro): the four tiles are read FIRST, then for each pickup kind k in
 * table order the tiles are tested in the order top-left, top-right,
 * bottom-left, bottom-right. So two items under Dave are collected in the
 * same tick, and the score/sound/draw sequence follows table order, not
 * screen order.
 *
 * Quirks kept:
 *  - every item except the door is scored, sounded (StopSound, PlaySound 6)
 *    and removed immediately, even the 0-point gun and jetpack;
 *  - the door is never removed; it scores (2000) and ends the level only
 *    while the trophy is held, every tick Dave touches it until
 *    level_complete runs (it runs later in the same tick);
 *  - picking up a jetpack while holding one erases the old fuel meter
 *    (XOR) and draws the full one; the status icon is not redrawn;
 *  - the tile column is not range-checked (U-M1 item 2): a tile right of
 *    column 99 is the next row's column 0. A cleared tile outside the live
 *    map (only from row 9, whose tiles are solid in every level) is not
 *    stored: the native resources are immutable (D4 stand-in).
 */
#include "world.h"

#define PICKUP_KINDS 10
#define PICKUP_SOUND 6

enum { TILE_DOOR = 2, TILE_JETPACK = 4, TILE_TROPHY = 10, TILE_GUN = 20 };
enum { STATUS_JETPACK = 0, STATUS_GUN = 1, STATUS_TROPHY = 5 };

static const int16_t pickup_tile[PICKUP_KINDS] = {2, 4, 20, 10, 47, 48, 49, 50, 51, 52};
static const int16_t pickup_points[PICKUP_KINDS] = {2000, 0, 0, 1000, 100, 50, 150, 300, 200, 500};

static void clear_tile(struct game *g, int32_t offset)
{
    if (offset >= 0 && offset < LEVEL_ROWS * LEVEL_COLS)
        level_live_map(g)[offset / LEVEL_COLS][offset % LEVEL_COLS] = 0;
}

static void collect(struct game *g, int k, int16_t tile, int32_t offset,
                    int16_t view_col, int16_t row, struct frame_output *out)
{
    if (tile != TILE_DOOR) {
        g->score += (uint32_t)(int32_t)pickup_points[k];
        update_score(g, out);
        out_sound(out, SOUND_STOP);
        out_sound(out, PICKUP_SOUND);
        clear_tile(g, offset);
        out_draw(out, DRAW_ERASE_DAVE, 0, 0, 0, 0);
        out_draw(out, DRAW_TILE, view_col, row, 0, 0);
        out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, 0, 0);
    }
    switch (tile) {
    case TILE_TROPHY:
        if (g->inv.got_trophy == 0) {
            g->inv.got_trophy = 1;
            out_sound(out, 7);
            /* the trophy stops glittering: its animated-tile entries go inactive */
            for (int i = 0; i < ANIM_MAX_TILES && g->anim.tiles[i].count > 0; i++)
                if (g->anim.tiles[i].first == TILE_TROPHY)
                    g->anim.tiles[i].active = 0;
            out_draw(out, DRAW_XOR_SPRITE, 0x48, 0xB8, SPRITE_STATUS, STATUS_TROPHY);
        }
        break;
    case TILE_DOOR:
        if (g->inv.got_trophy == 1) {
            g->level.done = 1;
            g->score += (uint32_t)(int32_t)pickup_points[k];
            update_score(g, out);
        }
        break;
    case TILE_GUN:
        g->inv.has_gun = 1;
        out_draw(out, DRAW_XOR_SPRITE, 0xF0, 0xAA, SPRITE_STATUS, STATUS_GUN);
        out_sound(out, 12);
        break;
    case TILE_JETPACK:
        if (g->inv.has_jetpack != 1)
            out_draw(out, DRAW_XOR_SPRITE, 0, 0xAA, SPRITE_STATUS, STATUS_JETPACK);
        if (g->inv.has_jetpack == 1)
            draw_status_meter(g, out);     /* XOR-erases the old meter */
        g->inv.jetpack_fuel = 60;
        g->inv.fuel_tick = 15;
        draw_status_meter(g, out);
        g->inv.has_jetpack = 1;
        out_sound(out, 12);
        break;
    }
}

void pick_up_items(struct game *g, const struct resources *r, struct frame_output *out)
{
    if (!(g->dave.state & DAVE_ALIVE) || g->dave.y <= 16 || g->dave.y >= 0xA6)
        return;
    int16_t col = (int16_t)(g->dave.x / 16 + g->level.scroll_x);
    int16_t row = (int16_t)((g->dave.y - 16) / 16);    /* 0..9 here */
    int32_t pos = row_offset(row) + col;
    static const struct { int32_t offset; int16_t dx, dy; } corner[4] = {
        {0, 0, 0}, {1, 1, 0}, {LEVEL_COLS, 0, 1}, {LEVEL_COLS + 1, 1, 1}};
    int16_t tile[4];
    for (int c = 0; c < 4; c++)
        tile[c] = map_byte(g, r, pos + corner[c].offset);
    for (int k = 0; k < PICKUP_KINDS; k++)
        for (int c = 0; c < 4; c++)
            if (pickup_tile[k] == tile[c])
                collect(g, k, tile[c], pos + corner[c].offset,
                        (int16_t)(col - g->level.scroll_x + corner[c].dx),
                        (int16_t)(row + corner[c].dy), out);
}
