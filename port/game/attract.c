/*
 * attract_mode (DAVE.C cs 0x07DE, census F_09DE): the first call of every
 * pipeline pass. In the high-score state it shows the table for up to 1000
 * retraces, in the title state the title for up to 200 x 6 retraces; a key
 * or the fire button starts a game, otherwise a demo chosen with
 * srand(time(NULL)); rand() starts (game mode 1). In the play and demo
 * states it does nothing.
 *
 * Quirks reproduced on purpose:
 *  - the high-score state falls through into the title state when it times
 *    out (mode 2 -> 3 inside the same call);
 *  - init_game_state runs on BOTH title outcomes, before the key test;
 *  - the demo choice is `(long)rand() * count / 32767`: it is `count` (one
 *    past the table) when rand() returns 32767, i.e. for time() & 0xFFFF in
 *    {3501, 7002} (U-M1 item 4); the original then reads offsets[5] = the
 *    first word of demo 0 (0x2002) as the stream position, and the level
 *    byte at 0x2002 lies in the far segment after the bank (the CGA tileset):
 *    it is 2, kept as the named constant below;
 *  - `time(NULL)` is an input (state-model D7): io->clock, Borland time_t;
 *    srand takes its low 16 bits;
 *  - the title animation counter j is an uninitialised stack word in the
 *    original (U-R5, open); it only selects which of the two animated title
 *    tiles' 4 frames is drawn. Its start value is TITLE_J_START here.
 *  - handle_menu_key is polled every 6 retraces; its popups (F1 help, F2
 *    control panel, F3 restart, F9 pause, Esc/F10 quit) are not part of
 *    this lane and are not modelled: a waiting F-key is treated as any key.
 */
#include "rng.h"
#include "world.h"

#define SCORES_RETRACES 1000
#define TITLE_STEPS 200
#define TITLE_RETRACES_PER_STEP 6
#define TITLE_J_START 0              /* U-R5: unknown in the original */
#define DEMO_GARBAGE_POS 0x2002      /* offsets[5] read past the table (U-M1 item 4) */
#define DEMO_GARBAGE_START_LEVEL 2   /* byte 0x2002 after the bank start (CGA tileset data) */

/* *(char far *)(g_demo_data + pos): signed bytes of the bank */
static int8_t demo_byte(const struct resources *r, int32_t pos)
{
    if (pos >= 0 && pos < DEMO_BANK_BYTES)
        return (int8_t)r->demos[pos];
    if (pos == DEMO_GARBAGE_POS)
        return DEMO_GARBAGE_START_LEVEL;
    return 0;   /* never reached: the only out-of-bank start is DEMO_GARBAGE_POS */
}

/* *(int far *)(g_demo_data + pos) */
static int16_t demo_word(const struct resources *r, int32_t pos)
{
    return (int16_t)((uint8_t)demo_byte(r, pos) | (uint8_t)demo_byte(r, pos + 1) << 8);
}

static int any_input(const struct world_io *io, uint32_t retrace)
{
    struct wait_input s = io->player(io->ctx, retrace);
    return io->key_peek(io->ctx, retrace) != 0 || s.fire;
}

static void start_game(struct game *g, const struct resources *r, const struct world_io *io,
                       struct frame_output *out)
{
    g->mode = MODE_PLAY;
    load_level(g, r, out);
    redraw_screen(g, out);
    wait_for_input(g, io, out);
}

void attract_mode(struct game *g, const struct resources *r, const struct world_io *io,
                  struct frame_output *out)
{
    int pressed = 0;

    if (g->mode == MODE_SCORES) {
        show_high_scores(1, out);
        for (int i = 0; i < SCORES_RETRACES; i++) {
            out->retraces++;
            /* handle_menu_key: popups not modelled (see header) */
            if ((pressed = any_input(io, out->retraces)) != 0)
                break;
        }
        if (pressed) {
            init_game_state(g, out);
            start_game(g, r, io, out);
            return;
        }
        g->mode++;                      /* falls through into the title */
    }
    if (g->mode != MODE_TITLE)
        return;

    redraw_screen(g, out);
    int j = TITLE_J_START;
    for (int i = 0; i < TITLE_STEPS; i++) {
        for (int k = 0; k < TITLE_RETRACES_PER_STEP; k++)
            out->retraces++;
        out_draw(out, DRAW_PIC, 0x68, 0, PIC_TITLE_ANIM, i & 3);
        j++;
        out_draw(out, DRAW_TILE, 8, 7, (j & 3) + 6, 0);
        out_draw(out, DRAW_TILE, 0xD, 9, (j & 3) + 6, 0);
        if ((pressed = any_input(io, out->retraces)) != 0)
            break;
    }
    init_game_state(g, out);
    if (pressed) {
        start_game(g, r, io, out);
        return;
    }

    /* no input: a random demo */
    rng_srand(g, (uint16_t)io->clock(io->ctx, out->retraces));
    int16_t count = demo_byte(r, 0);
    int16_t pick = rng_scaled(g, count);
    g->demo.pos = demo_word(r, (int32_t)pick * 4 + 4);
    g->mode = MODE_DEMO;
    g->level.index = demo_byte(r, (uint16_t)g->demo.pos);
    g->demo.pos++;
    load_level(g, r, out);
    redraw_screen(g, out);
}
