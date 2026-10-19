/*
 * DAVE.C -- Dangerous Dave (Softdisk 1990): the game.
 *
 * Translation unit 1 of the game, reconstructed from the executable: 53
 * functions (main .. init_game_state), cs [0x0239,0x51c3), in their
 * original order. Compiled with Turbo C++ 1.00, tcc -c -ms -1- -f- -N -G.
 *
 * Its object's composition reproduces the original layout:
 *   _TEXT  cs [0x0239,0x51c3)  functions in source order;
 *   _DATA  DS [0x00a8,0x0f02)  the initialised globals below (definition
 *          order, unpadded), then the images of initialised local
 *          aggregates where their functions are compiled (DS 0x07b6..0x08b0),
 *          then every string literal in order of appearance (DS 0x08b0..);
 *   _BSS   DS [0x4c60,0x654c)  the uninitialised globals, which TC++ orders by
 *          a hash of their names -- see the storage names in DAVE.H.
 * tools/verify_sources.py places the object by the directives below and
 * resolves every reference through that placement.
 */
/* @at 0x0239 */
/* @seg _DATA 0x00a8 */
/* @seg _BSS 0x4c60 */
#include <stdlib.h>
#include <bios.h>
#include <ctype.h>
#include <mem.h>
#include <string.h>
#include <time.h>
#include <dos.h>
#include "DAVE.H"

/* ---- initialised data: DS [0x00a8, ...) in definition order */
int g_demo_recording = 0;   /* 1 while a demo is being recorded (F_4A27) */
int g_demo_mode = 0;   /* game state: 0 play, 1 demo, 2 high scores, 3 title */
signed char g_fire_repeat = 30;   /* fire auto-repeat counter */
signed char g_jetpack_repeat = 30;   /* jetpack toggle repeat counter */
char g_hiscore_file[12] = "DSCORES.DAV";   /* "DSCORES.DAV" */
int g_jump_dy[47] = {0, -3, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -1, -1, -1, -1, -1, -1,
    -1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 3, 128, 0};   /* jump y-delta table, 0x80 terminated */
unsigned char g_level_flags[10] = {36, 36, 36, 40, 36, 36, 40, 36, 40, 36};   /* per-level option bits (copied to g_dave_state) */
int g_level_start_x[10] = {32, 16, 32, 16, 32, 32, 16, 32, 96, 32};
int g_level_start_y[10] = {144, 144, 96, 96, 144, 144, 48, 144, 32, 144};
int g_monster_width[8] = {28, 21, 22, 22, 14, 12, 16, 14};   /* monster width, levels 3..10 (indexed level - 2) */
int g_monster_height[8] = {15, 18, 22, 20, 5, 8, 15, 16};   /* monster height, levels 3..10 (indexed level - 2) */
int g_warp_target_level_plus1[10] = {0, 0, 0, 0, 2, 0, 0, 6, 7, 1};   /* warp target level (1-based, 0 = none) */
int g_warp_tube_tile[10] = {0, 0, 0, 0, 5, 0, 0, 17, 18, 29};   /* tile of the warp tube screen per level */
int g_warp_start_scroll_x[10] = {0, 0, 0, 0, 42, 0, 0, 67, 71, 11};   /* warp target view column */
int g_warp_start_x[10] = {0, 0, 0, 0, 144, 0, 0, 64, 144, 144};   /* warp target player x */
int g_spr_warp_left[3] = {219, 379, 139};   /* per gfx mode: sprite drawn left of the warp tube */
int g_spr_warp_right[3] = {220, 380, 140};   /* per gfx mode: sprite drawn right of the warp tube */
int g_spr_shot_b1[3] = {201, 349, 127};   /* per gfx mode: object kind 1 sprite, flag set */
int g_spr_shot_b0[3] = {203, 353, 128};   /* per gfx mode: object kind 1 sprite, flag clear */
int g_spr_jump_left[3] = {83, 113, 68};   /* per gfx mode: Dave jumping, facing left */
int g_spr_jump_right[3] = {81, 109, 67};   /* per gfx mode: Dave jumping, facing right */
int g_mask_jump_left[3] = {87, 121, 70};   /* masks of g_spr_jump_left */
int g_mask_jump_right[3] = {85, 117, 69};   /* masks of g_spr_jump_right */
int g_tile_digit0[3] = {229, 391, 148};   /* per gfx mode: tile id of the digit 0 */
int g_title_anim_tiles[12] = {225, 226, 227, 228, 387, 388, 389, 390, 144, 145, 146, 147};   /* title animation tile ids, 4 per gfx mode */
int g_status_row_len = 8;   /* row length of g_status_tiles (8) */
int g_status_tiles[24] = {213, 214, 215, 216, 217, 218, 224, 0, 373, 374, 375, 376, 377, 378, 386,
    0, 133, 134, 135, 136, 137, 138, 143, 0};   /* status-bar tile ids, g_status_row_len per gfx mode */
int g_pickup_tile_ids[10] = {2, 4, 20, 10, 47, 48, 49, 50, 51, 52};   /* collectible tile ids */
int g_pickup_points[10] = {2000, 0, 0, 1000, 100, 50, 150, 300, 200, 500};   /* their point values */
int g_tile_climbable[53] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0,
    0, 0, 0, 0};   /* per tile: climbable */
int g_tile_attr[53] = {0, 1, 0, 1, 0, 1, 2, 2, 2, 2, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1,
    2, 2, 2, 2, 1, 1, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0};   /* per tile: collision attribute */
int g_spr_dave_front[3] = {59, 65, 56};   /* per gfx mode: Dave standing, facing the player */
int g_mask_dave_front[3] = {73, 93, 63};   /* masks of g_spr_dave_front */
int g_spr_meter_label[3] = {221, 381, 141};   /* per gfx mode: jetpack meter frame */
int g_spr_meter_bar[3] = {222, 382, 142};   /* per gfx mode: jetpack meter bar unit */
int g_animated_tile_ids[4] = {6, 10, 25, 36};   /* animated base tiles */
int g_animated_tile_frames[4] = {4, 5, 4, 5};   /* their frame counts */
int g_sprite_sets[13][3][4] = {
    {{205, 207, 209, 211}, {357, 361, 365, 369}, {129, 130, 131, 132}},
    {{189, 191, 193, 191}, {325, 329, 333, 329}, {121, 122, 123, 122}},
    {{195, 197, 199, 197}, {337, 341, 345, 341}, {124, 125, 126, 125}},
    {{101, 103, 105, 103}, {149, 153, 157, 153}, {77, 78, 79, 78}},
    {{113, 115, 117, 115}, {173, 177, 181, 177}, {83, 84, 85, 84}},
    {{107, 109, 111, 109}, {161, 165, 169, 165}, {80, 81, 82, 81}},
    {{119, 121, 123, 121}, {185, 189, 193, 189}, {86, 87, 88, 87}},
    {{89, 91, 93, 91}, {125, 129, 133, 129}, {71, 72, 73, 72}},
    {{95, 97, 99, 97}, {137, 141, 145, 141}, {74, 75, 76, 75}},
    {{61, 63, 65, 63}, {69, 73, 77, 73}, {57, 58, 59, 58}},
    {{75, 77, 79, 77}, {97, 101, 105, 101}, {64, 65, 66, 65}},
    {{53, 55, 57, 55}, {53, 57, 61, 57}, {53, 54, 55, 54}},
    {{67, 69, 71, 69}, {81, 85, 89, 85}, {60, 61, 62, 61}}
};   /* animated sprite sets [set][gfx mode][frame] */
struct monsters g_level_monster_init[10] = {
    {{0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{1, 1, 0, 0}, {951, 711, 0, 0}, {69, 69, 0, 0}, {0, 0, 0, 0}, {20, 20, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{1, 0, 0, 0}, {515, 0, 0, 0}, {46, 0, 0, 0}, {0, 0, 0, 0}, {1, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{1, 1, 1, 1}, {240, 520, 788, 1472}, {60, 60, 66, 68}, {0, 0, 0, 0}, {10, 10, 10, 10}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{1, 1, 1, 1}, {158, 457, 694, 662}, {142, 144, 142, 44}, {0, 0, 0, 0}, {10, 10, 10, 10}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{1, 1, 1, 1}, {76, 259, 743, 855}, {48, 31, 60, 60}, {0, 0, 0, 0}, {25, 8, 8, 1}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{1, 1, 1, 0}, {846, 1136, 1350, 0}, {100, 50, 40, 0}, {0, 0, 0, 0}, {5, 2, 2, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{1, 1, 1, 1}, {563, 709, 788, 1102}, {143, 143, 143, 143}, {0, 8, 0, 8}, {20, 10, 5, 10}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{1, 1, 1, 1}, {709, 1040, 1323, 819}, {144, 64, 96, 44}, {0, 0, 0, 0}, {20, 20, 10, 10}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}}
};   /* per-level monster init block, copied to g_monsters */
/* initialised data ends at DS 0x07b6; local-aggregate images and the string pool follow */

/* ---- uninitialised data: DS [0x4c60, 0x654c), ordered by the _BSS hash (see DAVE.H) */
unsigned long g_score;
unsigned char g_dave_background[800];   /* screen area saved under Dave */
int g_has_gun;
int g_gfx_index;   /* video mode - 1: 0 CGA, 1 EGA, 2 VGA (table row) */
int g_got_trophy;
int g_has_jetpack;
struct hiscore *g_hiscore_buf;   /* DSCORES.DAV image (5 records) */
struct actor g_actors[6];   /* explosions and other short-lived animated objects */
int g_player_x;
int g_player_y;
int g_lives;
char far *g_tileset;   /* the loaded tile file */
int g_current_level;
struct shot g_shots[5];   /* bullets */
int g_in_warp_zone;
int g_dave_sprite;
int g_dave_facing;   /* 0 left, 1 right */
struct monsters g_monsters;
int g_game_over;
int g_death_pause;
int g_shot_anim_count;   /* bullet animation countdown */
int g_jetpack_fuel;   /* jetpack fuel meter */
int g_jump_pos;   /* position in g_jump_dy */
int g_quit;   /* leave the main loop */
int g_prev_dir;   /* previous direction */
int g_scroll_x;   /* first visible level column */
int g_demo_pos;   /* demo read position */
char far *g_demo_data;
char *g_level;   /* current level record / tile map */
int g_level_visited[10];   /* per-level "warp used" flags */
struct entry g_hiscores[5];   /* in-memory high score entries */
int g_input_dir;   /* requested direction 0..7, 8 = none */
int g_dave_mask;
int g_jet_facing;   /* jetpack facing */
struct anim g_anim_tiles[200];
unsigned long g_next_extra_life;   /* next extra-life score */
char huge *g_level_path;   /* monster movement path */
int g_anim_frame;   /* animation frame 0..3 */
int g_warp_return_level;
int g_fuel_tick;   /* jetpack fuel countdown */
int g_dave_state;   /* Dave state bits */
int g_level_done;
int g_anim_tick_divider;
char g_tiles[1000];   /* working 100x10 tile grid */
char g_demo_repeat;   /* demo run-length counter */
int g_bonus_timer;
int g_anim_delay;   /* animation countdown */
int g_unused_654a;   /* never referenced */

/*
 * main
 * cs [0x0239,0x02d2) / file [0x439,0x4d2), 153 bytes.
 *
 * C main(). Initialises (init_game_once), detects the display adapter (VideoID ->
 * g_adapter_type: 3 = EGA, 4/5 = VGA/MCGA, else CGA) and stores the video mode in
 * g_video_mode (1 CGA, 2 EGA, 3 VGA), loads the graphics (load_graphics), then loops:
 * state 3 (title) -> per-frame pipeline (attract attract_mode, input process_input, the
 * big move_dave, monsters/shots/doors ... handle_death death handling) until
 * g_game_over (game over); then high-score check check_high_score unless quitting
 * (g_quit), and finally exit via quit_game(0).
 * Name evidence: C0S calls it (layout/symbols.json).
 *
switch cases are emitted in source order (4,5 / 3 / default) while the
 * compare chain is sorted ascending (3,4,5).
 */

void main(void)
{
    init_game_once();
    g_adapter_type = VideoID();
    switch (g_adapter_type) {
    case 4:
    case 5:
        g_video_mode = 3;
        break;
    case 3:
        g_video_mode = 2;
        break;
    default:
        g_video_mode = 1;
        break;
    }
    load_graphics();
    do {
        g_demo_mode = 3;
        do {
            attract_mode();
            process_input();
            move_dave();
            update_explosions();
            move_monsters();
            move_bullets();
            animate_tiles();
            check_collisions();
            pick_up_items();
            level_complete();
            check_warp_transition();
            update_jetpack();
            handle_death();
        } while (g_game_over == 0);
        g_game_over = 0;
        if (g_quit == 0)
            check_high_score();
    } while (g_quit == 0);
    quit_game(0);
}

/*
 * quit_game
 * cs [0x02d2,0x02fc) / file [0x4d2,0x4fc), 42 bytes.
 *
 * quit_game(code): restores the hardware state (restore_keyboard_handler, ShutdownSound), returns
 * to text mode (set_video_mode(0)) when exiting normally, then exit(code).
 * Name evidence: ends in exit(); called by main and by the
 * "Quit?" prompt (ask_quit).
 *
exit() is the CS.LIB routine at cs 0x9463.
 */

void quit_game(int code)
{
    restore_keyboard_handler();
    ShutdownSound();
    if (code == 0)
        set_video_mode(0);
    exit(code);
}

/*
 * check_high_score .. update_score -- six consecutive functions of the main game module,
 * compiled together because they share the module's initialised _DATA run
 * DS [0x07B6,0x07D4): the SCOPY initialisers of their local char buffers.
 *
 *   check_high_score  cs [0x02fc,0x05eb)  check_high_score     751 bytes
 *   input_initials  cs [0x05eb,0x068e)  input_initials       163 bytes
 *   show_high_scores  cs [0x068e,0x07de)  show_high_scores     336 bytes
 *   attract_mode  cs [0x07de,0x09b2)  attract_mode         468 bytes
 *   draw_inventory  cs [0x09b2,0x0a34)  draw_status_bar      130 bytes
 *   update_score  cs [0x0a34,0x0bfb)  update_score         455 bytes
 *
 * Why one file: all of these buffers except update_score's "00000" are zero, and
 * TCC emits no LEDATA for an all-zero _DATA, so a single-function file for
 * check_high_score or show_high_scores has a SEGDEF-only _DATA that tools/match_function.py
 * cannot compare (it calls segment_bytes("_DATA") and raises). Compiled as
 * one unit, the _DATA is 30 bytes ending in "00000\0" and is compared in
 * full against DS 0x07B6.
 *
 * The module's string literals are pooled after all its initialised data
 * (DS 0x08B0...), so they are referenced by address ("You got a high score!" ...) rather than
 * written as literals; their text is quoted at each extern.
 *
 * Codegen notes (TCC 1.00, -G needed: 2-byte arg cleanup is inc sp/inc sp):
 * - block-scoped locals are placed below every function-level local AND
 *   below the struct-return temporaries of the whole function (check_high_score: len,
 *   num, digits come after s and the get_player_input temp); within a block the first
 *   declared gets the highest address.
 * - the first two int locals declared are the SI and DI register variables.
 * - `c = toupper(key = wait_key_cursor())` gives `mov di,ax; push ax` (input_initials).
 * - a struct-returning call `s = get_player_input(1)` pushes &s, the args, a far
 *   pointer to a temporary, then SCOPYs temp -> s.
 * - g_title_anim_tiles is indexed as a flat array: `g_title_anim_tiles[g_gfx_index * 4 + (i & 3)]`
 *   (shl,shl,add,shl); a 2-D array gives shl,shl,shl / shl.
 * - the last case of attract_mode's switch has no break (no trailing jmp).
 */

/* in-memory high score entries */

/* DSCORES.DAV image (5 records) */

/* g_score */

/* next extra-life score */

/* g_lives */

/* g_current_level */

/* game state: 0 play, 1 demo, 2 scores, 3 title */

/* gfx index (video mode - 1) */

/* tiles per gfx mode in g_status_tiles */

/* status-bar tile ids, g_status_row_len per mode */

/* digit-0 tile id per mode */

/* title animation tile ids, 4 per mode */

/* has jetpack */

/* has gun */

/* has trophy */

/* text cursor column */

/* text cursor row */

/* demo data */

/* demo read position */

/* "DSCORES.DAV" */

/* "You got a high score!" */

/* "Game Over" */

/* "High Scores\r\n\nScore  Name  Level\r\n-----  ----  -----\r\n" */

/* "\n\n\r" */

/*
 * check_high_score check_high_score: called by main when the game ends. If the score
 * beats an entry, shifts the table down, inserts score/level, converts the
 * score to 5 digits, shows the table, asks for initials (input_initials) and writes
 * DSCORES.DAV (write_file_far). Otherwise shows "Game Over" (levels 1-10) while the
 * monsters keep animating until a key/button or ~1000 frames.
 * Name evidence: strings "You got a high score!", "Game Over", "DSCORES.DAV".
 * Quirk preserved: the in-memory entry keeps only the low word of the score.
 */

void check_high_score(void)
{
    struct input s;
    int j;
    int i;

    for (i = 0; i < 5; i++) {
        if (g_hiscores[i].score < g_score) {
            int len;
            char num[6] = "";
            char digits[6] = "";

            for (j = 4; j > i; j--) {
                g_hiscores[j].score = g_hiscores[j - 1].score;
                g_hiscores[j].level = g_hiscores[j - 1].level;
                movmem(g_hiscores[j - 1].name, g_hiscores[j].name, 3);
                movmem(&g_hiscore_buf[j - 1], &g_hiscore_buf[j], 9);
            }
            g_hiscores[i].score = g_score;
            g_hiscores[i].level = g_current_level + 1;
            setmem(g_hiscores[i].name, 3, 0);
            setmem(g_hiscore_buf[i].name, 3, 0);
            g_hiscore_buf[i].level = g_current_level + 1;
            ultoa(g_score, num, 10);
            len = strlen(num);
            for (j = 0; j < len; j++)
                digits[4 - j] = num[len - 1 - j] - '0';
            movmem(digits, g_hiscore_buf[i].score, 5);
            show_high_scores(1);
            draw_text_window(0, 0x16, 0x27, 0x18);
            g_text_x = 10;
            g_text_y = 0x17;
            print_string("You got a high score!");
            g_text_x = 0x13;
            g_text_y = i * 2 + 10;
            input_initials(g_hiscores[i].name);
            movmem(g_hiscores[i].name, g_hiscore_buf[i].name, 3);
            write_file_far(g_hiscore_file, (void far *)g_hiscore_buf, 0x2dL);
            return;
        }
    }
    if (g_current_level < 10) {
        draw_text_window(0, 0x16, 0x27, 0x18);
        g_text_x = 0xf;
        g_text_y = 0x17;
        print_string("Game Over");
        if (bioskey(1))
            bioskey(0);
        for (i = 0; i < 1000; i++) {
            WaitVBL();
            s = get_player_input(1);
            move_monsters();
            move_bullets();
            animate_tiles();
            update_explosions();
            if (bioskey(1) || s.fire)
                break;
        }
    }
}

/*
 * input_initials input_initials(name): flushes one pending key, then reads keys,
 * accepting up to 3 characters ' '..'Z' (upper-cased) echoed at the text
 * cursor via DrawChar; Left-arrow (scan 0x4B) or Backspace (scan 0x0E) erases
 * one; Enter ends. Name evidence: called with the 3-byte name field of a
 * high score entry right after "You got a high score!".
 */

void input_initials(char *name)
{
    int n;
    int key;
    char c;

    n = 0;
    if (bioskey(1))
        bioskey(0);
    do {
        c = toupper(key = wait_key_cursor());
        if (c >= ' ' && c <= 'Z' && n < 3) {
            name[n++] = c;
            DrawChar(g_text_x++, g_text_y, c);
        }
        if (((key >> 8) == 0x4b || (key >> 8) == 0x0e) && n > 0) {
            DrawChar(--g_text_x, g_text_y, ' ');
            n--;
        }
    } while (c != '\r');
}

/*
 * show_high_scores show_high_scores(with_sound): draws the "High Scores" table from
 * the DSCORES.DAV records: 5 score digits, 3 initials, and the level
 * (10 -> "10", 11 -> "won"). With a non-zero argument it plays sounds
 * (PlaySound 0xB / 6) and waits (WaitSound) between rows.
 */

void show_high_scores(int flag)
{
    int k;
    int i;

    WaitSound();
    if (flag)
        PlaySound(0xb);
    for (i = 4; i < 0x1a; i += 2)
        draw_centered_window(i, i / 2);
    g_text_x = 0x10;
    g_text_y = 6;
    g_text_left = 0xc;
    print_string("High Scores\r\n\nScore  Name  Level\r\n-----  ----  -----\r\n");
    for (i = 0; i < 5; i++) {
        char buf[6] = "";
        char lvl;

        if (flag)
            PlaySound(6);
        for (k = 0; k < 5; k++)
            buf[k] = g_hiscore_buf[i].score[k] + '0';
        print_string(buf);
        for (k = 0; k < 3; k++)
            buf[k] = g_hiscore_buf[i].name[k];
        buf[3] = 0;
        g_text_x = 0x13;
        print_string(buf);
        lvl = g_hiscore_buf[i].level;
        buf[0] = lvl + '0';
        buf[1] = 0;
        g_text_x = 0x1b;
        if (lvl == 10) {
            buf[0] = '1';
            buf[1] = '0';
            buf[2] = 0;
        }
        if (lvl == 11) {
            buf[0] = 'w';
            buf[1] = 'o';
            buf[2] = 'n';
            buf[3] = 0;
            g_text_x--;
        }
        print_string(buf);
        print_string("\n\n\r");
        if (flag)
            WaitSound();
    }
}

/*
 * attract_mode attract_mode: first thing in main's game loop. State 2 shows the
 * high score table for ~1000 frames, state 3 the animated title for 200
 * frames; a key or button starts a game (state 0), otherwise a random demo
 * (srand(time), rand()) is selected from g_demo_data and state 1 (demo) begins.
 * Quirk preserved: the title animation counter j is never initialised.
 */

void attract_mode(void)
{
    int flag;
    struct input s;
    int i;
    int j;

    switch (g_demo_mode) {
    case 2:
        show_high_scores(1);
        for (i = 0; i < 1000; i++) {
            WaitVBL();
            handle_menu_key();
            s = get_player_input(1);
            if (flag = bioskey(1) || s.fire)
                break;
        }
        if (flag) {
            g_demo_mode = 0;
            init_game_state();
            load_level();
            redraw_screen();
            wait_for_input();
            break;
        }
        g_demo_mode++;
    case 3:
        redraw_screen();
        for (i = 0; i < 200; i++) {
            WaitVBL();
            WaitVBL();
            WaitVBL();
            WaitVBL();
            WaitVBL();
            WaitVBL();
            handle_menu_key();
            draw_tile(0x68, 0, g_title_anim_tiles[g_gfx_index * 4 + (i & 3)]);
            j++;
            DrawTile(8, 7, (j & 3) + 6);
            DrawTile(0xd, 9, (j & 3) + 6);
            s = get_player_input(1);
            if (flag = bioskey(1) || s.fire)
                break;
        }
        init_game_state();
        if (flag) {
            g_demo_mode = 0;
            load_level();
            redraw_screen();
            wait_for_input();
            break;
        }
        srand(time(NULL));
        g_demo_pos = *(int far *)(g_demo_data + (int)((long)rand() * *g_demo_data / 32767) * 4 + 4);
        g_demo_mode = 1;
        g_current_level = g_demo_data[g_demo_pos];
        g_demo_pos++;
        load_level();
        redraw_screen();
    }
}

/*
 * draw_inventory draw_status_bar: draws the trophy (after draw_status_meter), jetpack and gun
 * indicators if held, then the score (update_score) and level number (draw_level_number).
 */

void draw_inventory(void)
{
    if (g_has_jetpack) {
        draw_status_meter();
        xor_sprite(0, 0xaa, g_status_tiles[g_gfx_index * g_status_row_len]);
    }
    if (g_has_gun)
        xor_sprite(0xf0, 0xaa, g_status_tiles[g_gfx_index * g_status_row_len + 1]);
    if (g_got_trophy)
        xor_sprite(0x48, 0xb8, g_status_tiles[g_gfx_index * g_status_row_len + 5]);
    update_score();
    draw_level_number();
}

/*
 * update_score update_score: every 20000 points awards an extra life (max 3 shown,
 * drawn at x = 0x100 + 16*lives) and rounds the next-goal down to a
 * multiple of 20000; caps the score at 99999; draws it as 5 zero-padded
 * digit tiles at x = 0x40..0x60. Matches the external RE's score/lives
 * description (constants 0x4E20, 0x1869F).
 */

void update_score(void)
{
    char num[6] = "";
    char digits[6] = "00000";

    if (g_score - g_next_extra_life >= 20000) {
        g_next_extra_life = g_score;
        g_next_extra_life = g_next_extra_life / 20000 * 20000;
        if (g_lives < 3) {
            xor_sprite(g_lives * 16 + 0x100, 0, g_status_tiles[g_status_row_len * g_gfx_index + 6]);
            g_lives++;
            PlaySound(0xc);
        }
    }
    if (g_score > 99999L)
        g_score = 99999L;
    ultoa(g_score, num, 10);
    movmem(num, digits + (5 - strlen(num)), strlen(num));
    draw_tile(0x40, 1, g_tile_digit0[g_gfx_index] + digits[0] - '0');
    draw_tile(0x48, 1, g_tile_digit0[g_gfx_index] + digits[1] - '0');
    draw_tile(0x50, 1, g_tile_digit0[g_gfx_index] + digits[2] - '0');
    draw_tile(0x58, 1, g_tile_digit0[g_gfx_index] + digits[3] - '0');
    draw_tile(0x60, 1, g_tile_digit0[g_gfx_index] + digits[4] - '0');
}

/*
 * draw_level_number
 * cs [0x0bfb,0x0c57) / file [0xdfb,0xe57), 92 bytes.
 *
 * Draws the 1-based level number (g_current_level + 1) as two digit tiles at
 * x = 0xB0 and 0xB8 using the per-mode digit base g_tile_digit0.
 * Name evidence: /10 and %10 of g_current_level+1.
 *
 */

void draw_level_number(void)
{
    draw_tile(0xb0, 1, g_tile_digit0[g_gfx_index] + (g_current_level + 1) / 10);
    draw_tile(0xb8, 1, g_tile_digit0[g_gfx_index] + (g_current_level + 1) % 10);
}

/*
 * ask_restart
 * cs [0x0c57,0x0cdf) / file [0xe57,0xedf), 136 bytes.
 *
 * F3 handler: opens a text window, prints "Restart Game? (Y or N):",
 * waits for Y/N. On Y (and not already on the title, g_demo_mode != 3) it
 * restores the level tiles (movmem g_tiles <- g_level, 1000 bytes), sets the
 * title state and calls StopSound; otherwise it redraws (redraw_screen, ResumeSound).
 * Name evidence: the prompt string.
 *
single literal: _DATA placed at the literal (0x090B).
 */

void ask_restart(void)
{
    int i;
    int c;

    PauseSound();
    for (i = 2; i < 0x19; i += 2)
        draw_centered_window(i, 2);
    g_text_x = 8;
    g_text_y = 0xc;
    print_string("Restart Game? (Y or N):");
    do {
        c = toupper(wait_key_cursor() & 0xff);
    } while (c != 'N' && c != 'Y');
    if (c == 'Y' && g_demo_mode != 3) {
        movmem(g_tiles, g_level, 1000);
        g_demo_mode = 3;
        StopSound();
    } else {
        redraw_screen();
        ResumeSound();
    }
}

/*
 * show_help
 * cs [0x0cdf,0x104b) / file [0xedf,0x124b), 876 bytes.
 *
 * The F1 help screen: three pages of text inside a window opened with
 * draw_centered_window, each headed "dangerous dave" with two pairs of monster/item
 * sprites drawn by draw_masked_sprite from the per-mode sprite table at DS 0x035E.
 * Page 1 lists the function keys, page 2 the goal and controls, page 3 the
 * hazards. SPACE advances, ESC leaves early (redraw_screen redraws the screen).
 * Name evidence: "f1 = help" text, the three text pages.
 *
 * Codegen notes: the literals are pooled in order of appearance starting at
 * DS 0x0923 (identical strings are NOT merged). `g_text_x = g_text_left += 2`
 * style chains reload the stored value (add [x],2; mov ax,[x]).
 */

/* sprite ids [kind][gfx mode][frame] */

void show_help(void)
{
    int i;
    char c;

    for (i = 0; i < 0x1d; i += 7)
        draw_centered_window(i, 0x14);
    g_text_left += 2;
    g_text_x = g_text_left;
    g_text_y = 3;
    print_string("     dangerous dave\r\n\n\n\n\n");
    draw_masked_sprite(0x4c, 0x10, g_sprite_sets[11][g_gfx_index][0], g_sprite_sets[12][g_gfx_index][0]);
    draw_masked_sprite(0xf0, 0x10, g_sprite_sets[9][g_gfx_index][0], g_sprite_sets[10][g_gfx_index][0]);
    for (i = 0; i < 13; i++)
        DrawTile(i + 4, 1, 3);
    print_string("you use the keyboard,\r\n");
    print_string("joystick or a mouse to\r\n");
    print_string("to control dave.\r\n\n");
    print_string("these are the function\r\n");
    print_string("keys that are available\r\n");
    print_string("at any time:\r\n\n");
    print_string("f1 = help\r\n");
    print_string("f2 = control panel\r\n");
    print_string("f3 = restart game\r\n");
    print_string("f9 = pause game\r\n");
    print_string("f10 or esc = quit game\r\n\n");
    print_string("   press space or esc");
    do {
        c = bioskey(0);
    } while (c != ' ' && c != 0x1b);
    if (c == 0x1b) {
        redraw_screen();
        return;
    }

    draw_centered_window(0x1c, 0x14);
    g_text_left++;
    g_text_x = g_text_left;
    g_text_y = 3;
    print_string("       dangerous dave\r\n\n");
    draw_masked_sprite(0x4c, 0x10, g_sprite_sets[3][g_gfx_index][0], g_sprite_sets[4][g_gfx_index][0]);
    draw_masked_sprite(0xf0, 0x10, g_sprite_sets[5][g_gfx_index][0], g_sprite_sets[6][g_gfx_index][0]);
    print_string("the object of the game is\r\n");
    print_string("to guide dave through 10\r\n");
    print_string("perilous areas in clyde's\r\n");
    print_string("hideout. there are guns &\r\n");
    print_string("jetpacks to aid you.\r\n\n");
    print_string("in the control panel (f2),\r\n");
    print_string("you will find the keyboard\r\n");
    print_string("keys used for moving (they\r\n");
    print_string("can be redefined). using\r\n");
    print_string("the joystick or mouse, the\r\n");
    print_string("left button will shoot and\r\n");
    print_string("the right will turn on/off\r\n");
    print_string("the jetpack.\r\n\n\n\n");
    print_string("   press space or esc");
    do {
        c = bioskey(0);
    } while (c != ' ' && c != 0x1b);
    if (c == 0x1b) {
        redraw_screen();
        return;
    }

    draw_centered_window(0x1c, 0x14);
    g_text_left++;
    g_text_x = g_text_left;
    g_text_y = 3;
    print_string("       dangerous dave\r\n\n");
    draw_masked_sprite(0x4c, 0x10, g_sprite_sets[7][g_gfx_index][0], g_sprite_sets[8][g_gfx_index][0]);
    draw_masked_sprite(0xf0, 0x10, g_sprite_sets[7][g_gfx_index][2], g_sprite_sets[8][g_gfx_index][2]);
    print_string("watch out for fire, water\r\n");
    print_string("and weirdweeds! these will\r\n");
    print_string("toast dave very blackly!\r\n\n");
    print_string("merely grab the trophy and\r\n");
    print_string("walk through the door. it's\r\n");
    print_string("that simple! of course, you\r\n");
    print_string("might run into a few (?)\r\n");
    print_string("monsters...\r\n\n");
    print_string("also ... there are a few\r\n");
    print_string("places dave can go by try-\r\n");
    print_string("ing something strange and\r\n");
    print_string("dangerous...\r\n\n\n");
    print_string("        press space");
    do {
        c = bioskey(0);
    } while (c != ' ' && c != 0x1b);
    redraw_screen();
}

/*
 * ask_quit
 * cs [0x104b,0x10b9) / file [0x124b,0x12b9), 110 bytes.
 *
 * F10/ESC handler: "Quit? (Y or N):"; N redraws (redraw_screen), Y exits via
 * quit_game(0); then ResumeSound.
 * Name evidence: the prompt string.
 *
 */

void ask_quit(void)
{
    int i;
    int c;

    PauseSound();
    for (i = 2; i < 0x13; i += 2)
        draw_centered_window(i, 2);
    g_text_x = 0xc;
    g_text_y = 0xc;
    print_string("Quit? (Y or N):");
    do {
        c = toupper(wait_key_cursor() & 0xff);
    } while (c != 'N' && c != 'Y');
    if (c == 'N')
        redraw_screen();
    else
        quit_game(0);
    ResumeSound();
}

/*
 * pause_game
 * cs [0x10b9,0x1121) / file [0x12b9,0x1321), 104 bytes.
 *
 * F9 handler: prints "Press F9 to end pause:", flushes one key, waits for
 * a key with scan code 0x43 (F9), re-sets the video mode and redraws.
 * Name evidence: the prompt string and the F9 scan code.
 *
 */

void pause_game(void)
{
    int i;
    int c;

    PauseSound();
    for (i = 2; i < 0x18; i += 2)
        draw_centered_window(i, 2);
    g_text_x = 9;
    g_text_y = 0xc;
    print_string("Press F9 to end pause:");
    bioskey(0);
    do {
        c = wait_key_cursor();
    } while ((c >> 8) != 0x43);
    set_video_mode(g_video_mode);
    redraw_screen();
    ResumeSound();
}

/*
 * load_graphics()
 * cs [0x1121,0x11ff) / file [0x1321,0x13ff), 222 bytes. EXACT (strict, 30
 * fixups incl. five far-segment references checked against MZ relocations).
 *
 * Per video mode (g_video_mode: 1 CGA, 2 EGA, 3 VGA) passes the mode's
 * config-screen graphics segment to setup_graphics_pointers (setup_graphics_pointers), then
 * loads the tileset into the far graphics buffer g_tileset:
 *   CGA/VGA: RLE-decompresses (RLEExpand) the tileset linked into the EXE
 *            (far segments 0C42 / 11EF; first dword = unpacked length);
 *   EGA:     reads EGADAVE.DAV from disk (read_file_far).
 * Finally g_gfx_index (graphics index) = video mode - 1.
 *
 * Far segments (docs/data-layout.md): 1D58/1E84/20CC CGA/EGA/VGA config
 * graphics, 0C42 CGA tileset, 11EF VGA tileset.
 */

void load_graphics(void)
{
    char huge *p;

    switch (g_video_mode) {
    case 1:
        setup_graphics_pointers(g_picfile_cga, 0);
        p = g_tileset_cga;
        RLEExpand(p + 4, g_tileset, *(long huge *)p);
        break;
    case 2:
        setup_graphics_pointers(g_picfile_ega, 0);
        read_file_far("EGADAVE.DAV", g_tileset);
        break;
    case 3:
        setup_graphics_pointers(g_picfile_vga, 0);
        p = g_tileset_vga;
        RLEExpand(p + 4, g_tileset, *(long huge *)p);
        break;
    }
    g_gfx_index = g_video_mode - 1;
}

/*
 * redraw_screen
 * cs [0x11ff,0x136e) / file [0x13ff,0x156e), 367 bytes.
 *
 * Re-sets the video mode (EGA also CacheEGATiles). In play/demo/score states
 * (g_demo_mode < 3) redraws the level view, status bar (draw_inventory) and Dave's sprite
 * ids, re-positions the active doors/warp markers (g_monsters.sprite from the level
 * number per gfx mode), and in state 2 shows the high scores. In the title
 * state (3) prints the credits and draws the 7x10 "DAVE" tile logo held in
 * an initialised local array.
 * Name evidence: called after every popup (help, pause,
 * quit, restart) and from the attract loop.
 *
the logo initialiser is SCOPY'd from DS 0x07D4 (verified); the three
 * literals live in the module's literal pool and are referenced by address.
 * `(lvl - 2) * 16` compiles to `mov cl,4; shl ax,cl`; the original's four
 * single `shl ax,1` need `(lvl - 2) * 8 * 2`.
 */

/* The module's string literals live in its literal pool, which is not
   contiguous with this function's SCOPY initialiser at DS 0x07D4:
     "     BY JOHN ROMERO\n\r" = "     BY JOHN ROMERO\n\r"
     " (C) 1990 SOFTDISK, INC.\n\r" = " (C) 1990 SOFTDISK, INC.\n\r"
     "PRESS THE F1 KEY FOR HELP" = "PRESS THE F1 KEY FOR HELP"                                   */

void redraw_screen(void)
{
    char tiles[7][10] = {
        {0x12, 0x00, 0x12, 0x12, 0x12, 0x12, 0x00, 0x12, 0x00, 0x12},
        {0x12, 0x00, 0x12, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00, 0x12},
        {0x12, 0x00, 0x12, 0x00, 0x00, 0x12, 0x12, 0x12, 0x00, 0x12},
        {0x12, 0x00, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x32, 0x12},
        {0x12, 0x00, 0x12, 0x06, 0x12, 0x12, 0x12, 0x00, 0x00, 0x12},
        {0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x12},
        {0x12, 0x12, 0x12, 0x12, 0x12, 0x12, 0x12, 0x12, 0x06, 0x12},
    };
    int i;
    int j;

    set_video_mode(g_video_mode);
    if (g_video_mode == 2)
        CacheEGATiles();
    if (g_demo_mode < 3) {
        DrawViewBorders();
        draw_status_bar();
        draw_inventory();
        DrawLevelView();
        g_dave_sprite = g_spr_dave_front[g_gfx_index];
        g_dave_mask = g_mask_dave_front[g_gfx_index];
        for (i = 0; i < 4; i++) {
            if (g_monsters.active[i]) {
                switch (g_gfx_index) {
                case 0: g_monsters.sprite[i] = (g_current_level - 2) * 8 + 0x7d; break;
                case 1: g_monsters.sprite[i] = (g_current_level - 2) * 8 * 2 + 0xc5; break;
                case 2: g_monsters.sprite[i] = (g_current_level - 2) * 4 + 0x59; break;
                }
            }
        }
        draw_actors();
        if (g_demo_mode == 2)
            show_high_scores(0);
    }
    if (g_demo_mode == 3) {
        XorMask = -1;
        g_text_x = 8;
        g_text_left = 8;
        g_text_y = 6;
        print_string("     BY JOHN ROMERO\n\r");
        print_string(" (C) 1990 SOFTDISK, INC.\n\r");
        g_text_y = 0x15;
        print_string("PRESS THE F1 KEY FOR HELP");
        XorMask = 0;
        for (i = 0; i < 10; i++)
            for (j = 0; j < 7; j++)
                DrawTile(i + 5, j + 3, tiles[j][i]);
    }
}

/*
 * show_cga_picture
 * cs [0x136e,0x13a5) / file [0x156e,0x15a5), 55 bytes.
 *
 * Sets CGA mode 4, copies 16 KB to B800:0000 with movedata() from a local
 * far pointer that is never initialised (a bug in the original, kept), then
 * waits for a key.
 * Name evidence: CGA mode + 0x4000-byte copy to B800.
 *
the uninitialised `char far *p` occupies [bp-4]/[bp-2].
 */

void show_cga_picture(void)
{
    char far *p;

    _AX = 4; geninterrupt(0x10);
    movedata(FP_SEG(p), FP_OFF(p), 0xb800, 0, 0x4000);
    bioskey(0);
}

/*
 * handle_death
 * cs [0x13a5,0x1580) / file [0x15a5,0x1780), 475 bytes.
 *
 * Runs while Dave is dying (g_dave_state bit 0x20 clear) once the death timer
 * g_bonus_timer expires: removes a life icon, and either ends the game (lives < 0:
 * clears trophy/jetpack icons, g_game_over = game over, restores the level
 * tiles) or restarts the level: re-applies the scroll offset to the doors,
 * resets Dave's start position/state from the per-level tables (or the warp
 * zone tables when g_in_warp_zone), clears all monsters (6 x 0x13A) and shots
 * (5 x 0xE) and redraws.
 * Name evidence: g_lives decrement, game-over flag.
 *
`if (--x == -1)` compiles to dec [x]; mov ax,[x]; cmp ax,-1.
 */

void handle_death(void)
{
    int i;

    if (g_dave_state & 0x20)
        return;
    if (--g_bonus_timer)
        return;
    if (g_lives > 0)
        xor_sprite((g_lives - 1) * 16 + 0x100, 0, g_status_tiles[g_gfx_index * g_status_row_len + 6]);
    if (--g_lives == -1) {
        if (g_has_jetpack == 1) {
            xor_sprite(0, 0xaa, g_status_tiles[g_status_row_len * g_gfx_index]);
            draw_status_meter();
        }
        if (g_has_gun == 1)
            xor_sprite(0xf0, 0xaa, g_status_tiles[g_status_row_len * g_gfx_index + 1]);
        g_game_over = 1;
        movmem(g_tiles, g_level, 1000);
        return;
    }
    for (i = 0; i < 4; i++)
        if (g_monsters.active[i] == 1)
            g_monsters.x[i] += g_scroll_x * 16;
    g_scroll_x = 0;
    g_dave_state = g_level_flags[g_current_level];
    g_player_x = g_level_start_x[g_current_level];
    g_player_y = g_level_start_y[g_current_level];
    g_death_pause = 3;
    g_anim_delay = 2;
    g_dave_sprite = g_spr_dave_front[g_gfx_index];
    g_dave_mask = g_mask_dave_front[g_gfx_index];
    g_anim_frame = 0;
    g_input_dir = 8;
    g_dave_facing = 1;
    if (g_in_warp_zone == 1) {
        g_scroll_x = g_warp_start_scroll_x[g_warp_return_level];
        g_player_x = g_warp_start_x[g_warp_return_level];
        g_player_y = 0x10;
        g_dave_state = 0x28;
        for (i = 0; i < 4; i++)
            if (g_monsters.active[i])
                g_monsters.x[i] -= g_scroll_x * 16;
    }
    draw_dave();
    for (i = 0; i < 6; i++)
        g_actors[i].active = 0;
    for (i = 0; i < 5; i++)
        g_shots[i].active = 0;
    WaitVBL();
    DrawLevelView();
    draw_actors();
    wait_for_input();
}

/*
 * update_jetpack
 * cs [0x1580,0x1630) / file [0x1780,0x1830), 176 bytes.
 *
 * While the jetpack is on (g_dave_state bit 0) every 15 frames consumes one unit
 * of fuel (g_jetpack_fuel) and erases one segment of the fuel bar; when it runs
 * out, switches Dave back to walking, removes the trophy indicator(?),
 * plays sound 2 and restores Dave's normal sprites.
 * Name evidence: bar drawn at x = 0x4A + 2*g_jetpack_fuel.
 *
 */

void update_jetpack(void)
{
    if (g_dave_state & 1) {
        if (--g_fuel_tick == 0) {
            g_fuel_tick = 0xf;
            xor_sprite(g_jetpack_fuel * 2 + 0x4a, 0xae, g_spr_meter_bar[g_gfx_index]);
            g_jetpack_fuel--;
            if (g_jetpack_fuel == 0) {
                draw_status_meter();
                g_dave_state = g_dave_state & 0xe0 | 8;
                g_has_jetpack = 0;
                xor_sprite(0, 0xaa, g_status_tiles[g_gfx_index * g_status_row_len]);
                PlaySound(2);
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                g_dave_sprite = g_spr_dave_front[g_gfx_index];
                g_dave_mask = g_mask_dave_front[g_gfx_index];
            }
        }
    }
}

/*
 * spawn_explosion
 * cs [0x1630,0x16f6) / file [0x1830,0x18f6), 198 bytes.
 *
 * Finds a free slot among the 6 0x13A-byte objects at g_actors, fills in
 * x, y, kind and the animation counters (0x6E frames, 13-frame step),
 * draws its first frame, and for kind 5 sets g_bonus_timer = 300.
 * Name evidence: short-lived animated object (update_explosions
 * ages and frees it); kind 5 arms the 300-frame death timer.
 *
 */

void spawn_explosion(int x, int y, int type)
{
    int i;

    for (i = 0; i < 6; i++) {
        if (g_actors[i].active == 0) {
            g_actors[i].x = x;
            g_actors[i].y = y;
            g_actors[i].type = type;
            g_actors[i].active = 1;
            g_actors[i].frame = 0;
            g_actors[i].life = 0x6e;
            g_actors[i].anim = 0xd;
            xor_sprite(x, y, g_sprite_sets[0][g_gfx_index][0]);
            if (type == 5)
                g_bonus_timer = 300;
            break;
        }
    }
}

/*
 * update_explosions
 * cs [0x16f6,0x1890) / file [0x18f6,0x1a90), 410 bytes.
 *
 * Ages each active object of spawn_explosion: XOR-erases it, advances its 4-frame
 * animation every 13 frames, lets it fall 2 px when nothing solid is below
 * (tile_attr_at_offset probes at +4 and +14) and y < 0x98, redraws; when its life ends
 * it is erased and freed.
 *
the first two int locals declared get SI and DI; the third (x) stays on
 * the stack.
 */

void update_explosions(void)
{
    int i;
    int y;
    int x;

    for (i = 0; i < 6; i++) {
        if (g_actors[i].active == 1) {
            if (--g_actors[i].life > 0) {
                x = g_actors[i].x;
                y = g_actors[i].y;
                xor_sprite(x, y, g_sprite_sets[0][0][g_gfx_index * 4 + g_actors[i].frame]);
                if (--g_actors[i].anim == 0) {
                    g_actors[i].frame = ++g_actors[i].frame & 3;
                    g_actors[i].anim = 0xd;
                }
                if (g_actors[i].anim == 0xd && tile_attr_at_offset(x, y, 4, 0xe) != 1 &&
                    tile_attr_at_offset(x, y, 0xe, 0xe) != 1 && y < 0x98) {
                    g_actors[i].y += 2;
                    y += 2;
                }
                xor_sprite(x, y, g_sprite_sets[0][0][g_gfx_index * 4 + g_actors[i].frame]);
            } else {
                g_actors[i].active = 0;
                xor_sprite(g_actors[i].x, g_actors[i].y, g_sprite_sets[0][0][g_gfx_index * 4 + g_actors[i].frame]);
            }
        }
    }
}

/*
 * restore_background
 * cs [0x1890,0x18ce) / file [0x1a90,0x1ace), 62 bytes.
 *
 * Per-video-mode dispatch (g_gfx_index: 0 CGA, 1 EGA, 2 VGA) to the assembler
 * routine that restores a saved background buffer.
 *
 */

void restore_background(void *buf)
{
    switch (g_gfx_index) {
    case 0: RestoreUnderCGA(buf); break;
    case 1: RestoreUnderEGA(buf); break;
    case 2: RestoreUnderVGA(buf); break;
    }
}

/*
 * save_background
 * cs [0x18ce,0x1929) / file [0x1ace,0x1b29), 91 bytes.
 *
 * Per-video-mode dispatch of (x, y, sprite, buffer) to the assembler routine
 * that saves the screen area under a sprite (draw_dave passes Dave's
 * position and the buffer g_dave_background).
 *
params 3 and 4 become DI and SI (loaded before the stack check).
 */

void save_background(int x, int y, int mask, void *buf)
{
    switch (g_gfx_index) {
    case 0: SaveUnderCGA(x, y, mask, buf); break;
    case 1: SaveUnderEGA(x, y, mask, buf); break;
    case 2: SaveUnderVGA(x, y, mask, buf); break;
    }
}

/*
 * draw_masked_sprite
 * cs [0x1929,0x1984) / file [0x1b29,0x1b84), 91 bytes.
 *
 * Per-video-mode dispatch of (x, y, sprite, mask) to the masked sprite
 * blitter (used for Dave and the help-screen monsters).
 *
 */

void draw_masked_sprite(int a, int b, int c, int d)
{
    switch (g_gfx_index) {
    case 0: DrawMaskedCGA(a, b, c, d); break;
    case 1: DrawMaskedEGA(a, b, c, d); break;
    case 2: DrawMaskedVGA(a, b, c, d); break;
    }
}

/*
 * draw_tile
 * cs [0x1984,0x19d6) / file [0x1b84,0x1bd6), 82 bytes.
 *
 * Per-video-mode dispatch of (x, y, tile) to the opaque tile blitter (the
 * CGA one writes straight to B800); used for score/level digits.
 *
 */

void draw_tile(int a, int b, int c)
{
    switch (g_gfx_index) {
    case 0: DrawPicCGA(a, b, c); break;
    case 1: DrawPicEGA(a, b, c); break;
    case 2: DrawPicVGA(a, b, c); break;
    }
}

/*
 * xor_sprite
 * cs [0x19d6,0x1a28) / file [0x1bd6,0x1c28), 82 bytes.
 *
 * Per-video-mode dispatch of (x, y, sprite) to the sprite blitter that is
 * used both to draw and to erase (update_explosions draws the same frame twice).
 *
 */

void xor_sprite(int a, int b, int c)
{
    switch (g_gfx_index) {
    case 0: DrawXorCGA(a, b, c); break;
    case 1: DrawXorEGA(a, b, c); break;
    case 2: DrawXorVGA(a, b, c); break;
    }
}

/*
 * erase_dave
 * cs [0x1a28,0x1a6a) / file [0x1c28,0x1c6a), 66 bytes.
 *
 * Per-video-mode restore of the background saved under Dave (buffer
 * g_dave_background).
 *
 */

void erase_dave(void)
{
    switch (g_gfx_index) {
    case 0: RestoreUnderCGA(g_dave_background); break;
    case 1: RestoreUnderEGA(g_dave_background); break;
    case 2: RestoreUnderVGA(g_dave_background); break;
    }
}

/*
 * draw_dave
 * cs [0x1a6a,0x1b16) / file [0x1c6a,0x1d16), 172 bytes.
 *
 * Per-video-mode: saves the background under Dave (x g_player_x, y g_player_y,
 * mask g_dave_mask) into g_dave_background, then draws his masked sprite g_dave_sprite.
 *
 */

void draw_dave(void)
{
    switch (g_gfx_index) {
    case 0:
        SaveUnderCGA(g_player_x, g_player_y, g_dave_mask, g_dave_background);
        DrawMaskedCGA(g_player_x, g_player_y, g_dave_sprite, g_dave_mask);
        break;
    case 1:
        SaveUnderEGA(g_player_x, g_player_y, g_dave_mask, g_dave_background);
        DrawMaskedEGA(g_player_x, g_player_y, g_dave_sprite, g_dave_mask);
        break;
    case 2:
        SaveUnderVGA(g_player_x, g_player_y, g_dave_mask, g_dave_background);
        DrawMaskedVGA(g_player_x, g_player_y, g_dave_sprite, g_dave_mask);
        break;
    }
}

/*
 * move_dave
 * cs [0x1b16,0x2a1f) / file [0x1d16,0x2c1f), 3849 bytes incl. 5 jump tables.
 *
 * Dave's per-frame movement state machine, driven by the requested
 * direction g_input_dir (0 up, 1 up-right, 2 right, 3 down-right, 4 down,
 * 5 down-left, 6 left, 7 up-left, 8 none; consumed by setting it to 8) and
 * the state bits in g_dave_state:
 *   0x20 alive (else only WaitVBL), 0x04 walking, 0x08 falling,
 *   0x10 jumping (y deltas from g_jump_dy[g_jump_pos], 0x80 = apex/end),
 *   0x02 climbing (tile property g_tile_climbable[tile] == 1), 0x01 jetpack,
 *   0x40 killed -> state 0, erase Dave, spawn the death explosion
 *   (spawn_explosion kind 5 arms the death timer handled by handle_death).
 * Collision probes: tile_attr_at(dx, dy) -> 0 free, 1 solid, 2 deadly;
 * tile_at(dx, dy) -> tile index. Movement speed is throttled by g_death_pause.
 * Every branch ends with the same redraw: erase (erase_dave) / draw (draw_dave)
 * Dave around the frame wait WaitVBL, ordered by whether Dave is in the upper
 * or lower part of the screen (y < 100) to avoid flicker.
 * Name evidence: all writes to Dave x/y (g_player_x/g_player_y) and
 * his sprite (g_dave_sprite/g_dave_mask), death on deadly tiles, jump/climb/jetpack.
 *
 * Codegen (-G): sequential `if (state & bit) { ...; return; }` blocks (no
 * else: a `return` jumps straight to the epilogue and no dead jmp follows);
 * `g_death_pause--;` as a statement then `if (g_death_pause > 0 ...)` gives dec/cmp [m],0;
 * `y = ++y & 0xff` gives inc [m]; mov ax,[m]; and; mov [m],ax; the first
 * and last case of a switch-with-table need no particular order: TCC emits
 * case bodies in source order (6,2,0,1/7 here) and the table by value; a
 * missing break on the last case of the small inner switches is required
 * (no trailing jmp). Register vars: moved = SI, t = DI, hit on the stack.
 */

/* Dave state bits */

/* requested direction 0..7, 8 = none */

/* previous direction */

/* facing: 0 left, 1 right */

/* Dave x */

/* Dave y */

/* animation delay */

/* animation frame 0..3 */

/* gfx index */

/* Dave sprite */

/* Dave mask */

/* jump table position */

/* jetpack facing */

/* jump y-delta table, 0x80 terminated */

/* tile is climbable */

void move_dave(void)
{
    int moved;
    int t;
    int hit;

    moved = 0;
    if (g_dave_state & 0x20) {
        g_death_pause--;
        if (g_death_pause > 0 && (g_dave_state & 4) || g_death_pause > 3 && (g_dave_state & 8) ||
            g_death_pause > 1 && ((g_dave_state & 0x10) || (g_dave_state & 2))) {
            WaitVBL();
            return;
        }
        g_death_pause = 3;

        if (g_dave_state & 4) {
            switch (g_input_dir) {
            case 6:
                if (g_prev_dir == 2 && tile_attr_at(-2, 0) == 0) {
                    g_player_x -= 2;
                    g_prev_dir = g_input_dir;
                    moved++;
                }
                g_dave_facing = 0;
                if (tile_attr_at(-2, 0) == 1) {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    PlaySound(1);
                    break;
                }
                if (tile_attr_at(0, 0) == 2) {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                    break;
                }
                if (tile_attr_at(2, 0x10) == 0 && tile_attr_at(8, 0x10) == 0) {
                    PlaySound(2);
                    g_dave_state = g_dave_state & 0xfb | 8;
                    g_player_y = ++g_player_y & 0xff;
                    g_player_x--;
                    moved++;
                }
                if (tile_attr_at(2, 0x10) == 2) {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                    break;
                }
                if (--g_anim_delay == 0) {
                    g_anim_delay = 2;
                    g_anim_frame = ++g_anim_frame & 3;
                }
                t = g_gfx_index * 4 + g_anim_frame;
                g_dave_sprite = g_sprite_sets[9][0][t];
                g_dave_mask = g_sprite_sets[10][0][t];
                g_player_x -= 2;
                scroll_screen();
                PlaySound(4);
                moved++;
                g_input_dir = 8;
                break;
            case 2:
                if (g_prev_dir == 6 && tile_attr_at(0xd, 0) == 0) {
                    g_player_x += 2;
                    moved++;
                    g_prev_dir = g_input_dir;
                }
                g_dave_facing = 1;
                if (tile_attr_at(0xf, 0) == 1) {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    PlaySound(1);
                    break;
                }
                if (tile_attr_at(0xd, 0) == 2) {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                    break;
                }
                if (tile_attr_at(5, 0x10) == 0 && tile_attr_at(0xb, 0x10) == 0) {
                    PlaySound(2);
                    g_dave_state = g_dave_state & 0xfb | 8;
                    g_player_y = ++g_player_y & 0xff;
                    g_player_x++;
                    moved++;
                }
                if (tile_attr_at(9, 0x10) == 2) {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                    break;
                }
                if (--g_anim_delay == 0) {
                    g_anim_delay = 2;
                    g_anim_frame = ++g_anim_frame & 3;
                }
                t = g_gfx_index * 4 + g_anim_frame;
                g_dave_sprite = g_sprite_sets[11][0][t];
                g_dave_mask = g_sprite_sets[12][0][t];
                g_player_x += 2;
                scroll_screen();
                PlaySound(4);
                moved++;
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                break;
            case 0:
                if (g_tile_climbable[tile_at(6, -2)] == 1) {
                    g_dave_state = g_dave_state & 0xfb | 2;
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    g_dave_sprite = g_spr_dave_front[g_gfx_index];
                    g_dave_mask = g_mask_dave_front[g_gfx_index];
                    break;
                }
            case 1:
            case 7:
                g_jump_pos = 0;
                PlaySound(5);
                g_dave_state = g_dave_state & 0xfb | 0x10;
                if (g_input_dir == 0) {
                    switch (g_dave_facing) {
                    case 0:
                        g_dave_sprite = g_spr_jump_left[g_gfx_index];
                        g_dave_mask = g_mask_jump_left[g_gfx_index];
                        break;
                    case 1:
                        g_dave_sprite = g_spr_jump_right[g_gfx_index];
                        g_dave_mask = g_mask_jump_right[g_gfx_index];
                    }
                } else {
                    g_dave_sprite = g_spr_jump_right[g_gfx_index];
                    g_dave_mask = g_mask_jump_right[g_gfx_index];
                    g_dave_facing = 1;
                    if (g_input_dir == 7) {
                        g_dave_sprite = g_spr_jump_left[g_gfx_index];
                        g_dave_mask = g_mask_jump_left[g_gfx_index];
                        g_dave_facing = 0;
                    }
                }
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                break;
            }
            if (moved) {
                if (g_player_y >= 100)
                    WaitVBL();
                erase_dave();
                draw_dave();
                if (g_player_y < 100)
                    WaitVBL();
            } else
                WaitVBL();
            return;
        }

        if (g_dave_state & 8) {
            switch (g_input_dir) {
            case 0:
            case 4:
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                break;
            case 5:
            case 6:
            case 7:
                if (tile_attr_at(-2, 6) != 1 && tile_attr_at(-4, 0xf) != 1) {
                    g_player_x--;
                    g_dave_sprite = g_sprite_sets[9][0][g_gfx_index * 4];
                    g_dave_mask = g_sprite_sets[10][0][g_gfx_index * 4];
                    scroll_screen();
                    moved++;
                } else {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                }
                g_dave_facing = 0;
                break;
            case 1:
            case 2:
            case 3:
                if (tile_attr_at(0xd, 6) != 1 && tile_attr_at(0xf, 0xf) != 1) {
                    g_player_x++;
                    g_dave_sprite = g_sprite_sets[11][0][g_gfx_index * 4];
                    g_dave_mask = g_sprite_sets[12][0][g_gfx_index * 4];
                    scroll_screen();
                    moved++;
                } else {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                }
                g_dave_facing = 1;
                break;
            }
            t = tile_attr_at(5, 0x11) | tile_attr_at(8, 0x11);
            switch (t) {
            case 0:
                g_player_y = ++g_player_y & 0xff;
                moved++;
                break;
            case 1:
                g_dave_sprite = g_sprite_sets[9][0][g_gfx_index * 4 + 1];
                g_dave_mask = g_sprite_sets[10][0][g_gfx_index * 4 + 1];
                if (g_prev_dir == 0 || g_prev_dir == 4 || g_prev_dir == 8) {
                    g_dave_sprite = g_spr_dave_front[g_gfx_index];
                    g_dave_mask = g_mask_dave_front[g_gfx_index];
                }
                if (g_prev_dir == 2 || g_prev_dir == 1 || g_prev_dir == 3) {
                    g_dave_sprite = g_sprite_sets[11][0][g_gfx_index * 4 + 1];
                    g_dave_mask = g_sprite_sets[12][0][g_gfx_index * 4 + 1];
                }
                g_dave_state = g_dave_state & 0xf7 | 4;
                g_player_y = ++g_player_y & 0xf0;
                StopSound();
                moved++;
                break;
            case 2:
                g_input_dir = 8;
                StopSound();
                PlaySound(3);
                g_dave_state = g_dave_state & 0xe0 | 0x40;
            }
            if (moved) {
                if (g_player_y >= 100)
                    WaitVBL();
                erase_dave();
                draw_dave();
                if (g_player_y < 100)
                    WaitVBL();
            } else
                WaitVBL();
            return;
        }

        if (g_dave_state & 0x10) {
            switch (g_input_dir) {
            case 6:
            case 7:
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                g_dave_facing = 0;
                if (g_tile_climbable[tile_at(-2, -2)] == 1) {
                    g_dave_state = g_dave_state & 0xef | 2;
                    break;
                }
                if ((tile_attr_at(-4, 2) | tile_attr_at(0, 0xf)) == 1)
                    break;
                if ((tile_attr_at(-2, 2) | tile_attr_at(2, 0xd)) == 2) {
                    StopSound();
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                }
                g_dave_sprite = g_spr_jump_left[g_gfx_index];
                g_dave_mask = g_mask_jump_left[g_gfx_index];
                g_player_x -= 2;
                scroll_screen();
                break;
            case 1:
            case 2:
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                g_dave_facing = 1;
                if (g_tile_climbable[tile_at(0xd, -2)] == 1) {
                    g_dave_state = g_dave_state & 0xef | 2;
                    break;
                }
                if ((tile_attr_at(0xf, 2) | tile_attr_at(0xd, 0xf)) == 1)
                    break;
                if ((tile_attr_at(0xd, 2) | tile_attr_at(0xd, 0xd)) == 2) {
                    StopSound();
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                }
                g_dave_sprite = g_spr_jump_right[g_gfx_index];
                g_dave_mask = g_mask_jump_right[g_gfx_index];
                g_player_x += 2;
                scroll_screen();
                break;
            }
            t = g_jump_dy[g_jump_pos];
            if (t == 0x80) {
                t = 0;
                g_dave_state = g_dave_state & 0xef | 8;
            }
            if (t > 0) {
                hit = tile_attr_at(4, t + 0xf) | tile_attr_at(0xb, t + 0xf);
                if (hit == 2) {
                    StopSound();
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                }
                if (hit == 1) {
                    StopSound();
                    g_dave_state = g_dave_state & 0xef | 4;
                    g_player_y = (g_player_y + t) & 0xf0;
                    t = 0;
                    g_dave_sprite = g_sprite_sets[9][0][g_gfx_index * 4 + 1];
                    g_dave_mask = g_sprite_sets[10][0][g_gfx_index * 4 + 1];
                    if (g_prev_dir == 2 || g_prev_dir == 1 || g_prev_dir == 3) {
                        g_dave_sprite = g_sprite_sets[11][0][g_gfx_index * 4 + 1];
                        g_dave_mask = g_sprite_sets[12][0][g_gfx_index * 4 + 1];
                    }
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                }
            }
            if (t < 0) {
                hit = tile_attr_at(4, t + 1) | tile_attr_at(9, t + 1);
                if (hit == 2) {
                    StopSound();
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                }
                if (hit == 1) {
                    g_dave_state = g_dave_state & 0xef | 8;
                    t = 0;
                    g_player_y = --g_player_y & 0xff;
                }
            }
            g_player_y = (g_player_y + t) & 0xff;
            g_jump_pos++;
            if (g_player_y >= 100)
                WaitVBL();
            erase_dave();
            draw_dave();
            if (g_player_y < 100)
                WaitVBL();
            return;
        }

        if (g_dave_state & 2) {
            switch (g_input_dir) {
            case 1:
                g_jump_pos = 0;
                PlaySound(5);
                g_dave_state = g_dave_state & 0xfd | 0x10;
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                g_player_x += 2;
                g_player_y -= 2;
                scroll_screen();
                g_dave_facing = 1;
                moved++;
                break;
            case 7:
                g_jump_pos = 0;
                PlaySound(5);
                g_dave_state = g_dave_state & 0xfd | 0x10;
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                g_player_x -= 2;
                g_player_y -= 2;
                scroll_screen();
                g_dave_facing = 0;
                moved++;
                break;
            case 0:
                if (g_tile_climbable[tile_at(6, -2)] == 1) {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    g_player_y -= 2;
                    PlaySound(4);
                    animate_tick();
                } else {
                    g_jump_pos = 0;
                    PlaySound(5);
                    g_dave_state = g_dave_state & 0xfd | 0x10;
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    g_player_y -= 2;
                }
                moved++;
                break;
            case 4:
                if (g_tile_climbable[tile_at(6, 0x10)] == 1) {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    PlaySound(4);
                    g_player_y += 2;
                    PlaySound(4);
                    animate_tick();
                    moved++;
                } else {
                    g_dave_state = g_dave_state & 0xfd | 8;
                }
                break;
            case 6:
                if (g_tile_climbable[tile_at(0, 8)] == 1) {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    g_player_x -= 2;
                    scroll_screen();
                    PlaySound(4);
                    animate_tick();
                    moved++;
                } else {
                    g_dave_state = g_dave_state & 0xfd | 8;
                }
                g_dave_facing = 0;
                break;
            case 2:
                if (g_tile_climbable[tile_at(0xd, 8)] == 1) {
                    g_prev_dir = g_input_dir;
                    g_input_dir = 8;
                    g_player_x += 2;
                    scroll_screen();
                    PlaySound(4);
                    animate_tick();
                    moved++;
                } else {
                    g_dave_state = g_dave_state & 0xfd | 8;
                }
                g_dave_facing = 1;
                break;
            }
            if (moved) {
                if (g_player_y >= 100)
                    WaitVBL();
                erase_dave();
                draw_dave();
                if (g_player_y < 100)
                    WaitVBL();
            } else
                WaitVBL();
            return;
        }

        if (g_dave_state & 1) {
            PlaySound(9);
            switch (g_input_dir) {
            case 0:
            case 1:
            case 7:
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                t = tile_attr_at(2, 0) | tile_attr_at(0xb, 0);
                if ((t & 1) == 1) {
                    g_dave_state = g_dave_state & 0xfe | 1;
                    break;
                }
                if (t == 2) {
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                    break;
                }
                if (g_player_y > 0)
                    g_player_y--;
                moved++;
                break;
            case 4:
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                t = tile_attr_at(2, 0x10) | tile_attr_at(0xb, 0x10);
                if ((t & 1) == 1) {
                    g_dave_state = g_dave_state & 0xfe | 1;
                    break;
                }
                if (t == 2) {
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                    break;
                }
                if (g_player_y < 0xaa)
                    g_player_y++;
                else {
                    g_dave_state = g_dave_state & 0xfe | 8;
                    g_dave_sprite = g_spr_dave_front[g_gfx_index];
                    g_dave_mask = g_mask_dave_front[g_gfx_index];
                }
                moved++;
                break;
            case 6:
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                g_dave_facing = 0;
                t = tile_attr_at(-2, 4) | tile_attr_at(-2, 0xc);
                if (t == 1)
                    break;
                if (t == 2) {
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                    break;
                }
                g_player_x--;
                moved++;
                scroll_screen();
                g_jet_facing = 0;
                break;
            case 2:
                g_prev_dir = g_input_dir;
                g_input_dir = 8;
                g_dave_facing = 1;
                t = tile_attr_at(0xd, 4) | tile_attr_at(0xd, 0xc);
                if (t == 1)
                    break;
                if (t == 2) {
                    PlaySound(3);
                    g_dave_state = g_dave_state & 0xe0 | 0x40;
                    break;
                }
                g_player_x++;
                moved++;
                scroll_screen();
                g_jet_facing = 1;
                break;
            }
            if (--g_anim_delay == 0) {
                g_anim_delay = 4;
                g_anim_frame = ++g_anim_frame & 3;
                if (g_jet_facing == 0) {
                    g_dave_sprite = g_sprite_sets[5][0][g_gfx_index * 4 + g_anim_frame];
                    g_dave_mask = g_sprite_sets[6][0][g_gfx_index * 4 + g_anim_frame];
                } else {
                    g_dave_sprite = g_sprite_sets[3][0][g_gfx_index * 4 + g_anim_frame];
                    g_dave_mask = g_sprite_sets[4][0][g_gfx_index * 4 + g_anim_frame];
                }
                moved++;
            }
            if (moved) {
                if (g_player_y >= 100)
                    WaitVBL();
                erase_dave();
                draw_dave();
                if (g_player_y < 100)
                    WaitVBL();
            } else
                WaitVBL();
            return;
        }

        if (g_dave_state & 0x40) {
            g_dave_state = 0;
            erase_dave();
            spawn_explosion(g_player_x, g_player_y + 3, 5);
        }
    } else
        WaitVBL();
}

/*
 * animate_tick()
 * cs [0x2a1f,0x2a70) / file [0x2c1f,0x2c70), 81 bytes.
 *
Frame-rate divider for a 4-frame animation: the countdown at g_anim_delay is
 * decremented and, when it reaches zero, reloaded with 2 and the frame index
 * g_anim_frame advances modulo 4. The new frame then selects two words from
 * the 2-D int tables [?][4] at DS:0x0406 and DS:0x041E, row g_gfx_index,
 * stored to g_dave_sprite and g_dave_mask (likely the current sprite/tile ids of
 * some animated object; the row is probably a direction/state).
 *
 * Name: tentative: only structure is known.
 *
 * Codegen notes: `x++; x = x & 3;` gives `inc [x]; mov ax,[x]; and ax,3;
 * mov [x],ax` (no register-load suppression). The index is written flat,
 * `t[row * 4 + i]`: that gives `shl bx,1; shl bx,1; add bx,i; shl bx,1`,
 * whereas a true 2-D `t[row][i]` scales row and column separately.
 */

/* animation countdown */

/* animation frame 0..3 */

/* table row (state/direction) */

void animate_tick(void)
{
    if (--g_anim_delay == 0) {
        g_anim_delay = 2;
        g_anim_frame++;
        g_anim_frame = g_anim_frame & 3;
        g_dave_sprite = g_sprite_sets[7][0][g_gfx_index * 4 + g_anim_frame];
        g_dave_mask = g_sprite_sets[8][0][g_gfx_index * 4 + g_anim_frame];
    }
}

/*
 * tile_attr_at(x, y)
 * cs [0x2a70,0x2ad8) / file [0x2c70,0x2cd8), 104 bytes.
 *
Returns the attribute word (table g_tile_attr indexed by tile id) of the
 * level tile under screen pixel (x, y). Pixel y is relative to the playfield
 * offset g_player_y and the first 16 pixels are above the grid; rows > 9 are
 * outside the 10-row playfield; both cases return 0. Column = (x + g_player_x)
 * / 16 + g_scroll_x (the scroll column). The tile byte is read (signed) from
 * the grid at g_level via the row-offset table RowTimes100.
 */

/* horizontal pixel scroll / x offset */

/* vertical pixel offset (g_start_y) */

/* first visible level column */

/* current level tile grid */

/* row -> byte offset into the tile grid */

/* tile id -> tile attribute */

int tile_attr_at(int x, int y)
{
    register int row, col;

    if (g_player_y + y < 16)
        return 0;
    col = (x + g_player_x) / 16 + g_scroll_x;
    row = (g_player_y + y - 16) / 16;
    if (row > 9)
        return 0;
    return g_tile_attr[(g_level + RowTimes100[row])[col]];
}

/*
 * tile_at(x, y)
 * cs [0x2ad8,0x2b38) / file [0x2cd8,0x2d38), 96 bytes.
 *
Same coordinate mapping as tile_attr_at but returns the raw (signed char) tile
 * id under screen pixel (x, y), and accepts rows 0..11 (0 when y is above
 * the grid or the row is > 11).
 *
 * Codegen: first declared register variable gets SI, the second DI.
 */

/* horizontal pixel scroll / x offset */

/* vertical pixel offset (g_start_y) */

/* first visible level column */

/* current level tile grid */

/* row -> byte offset into the tile grid */

int tile_at(int x, int y)
{
    register int row, col;

    if (g_player_y + y < 16)
        return 0;
    col = (x + g_player_x) / 16 + g_scroll_x;
    row = (g_player_y + y - 16) / 16;
    if (row > 11)
        return 0;
    return (g_level + RowTimes100[row])[col];
}

/*
 * tile_attr_at_offset(x, y, dx, dy)
 * cs [0x2b38,0x2b87) / file [0x2d38,0x2d87), 79 bytes.
 *
Attribute word (g_tile_attr[tile]) of the level tile at pixel
 * (x + dx, y + dy), column relative to the scroll column g_scroll_x, row 0
 * starting at pixel 16. No range checks.
 */

/* first visible level column */

/* current level tile grid */

/* row -> byte offset into the tile grid */

/* tile id -> tile attribute */

int tile_attr_at_offset(int x, int y, int dx, int dy)
{
    register int col, row;

    col = (dx + x) / 16 + g_scroll_x;
    row = (y + dy - 16) / 16;
    return g_tile_attr[(g_level + RowTimes100[row])[col]];
}

/*
 * move_monsters()
 * cs [0x2b87,0x2e1b) / file [0x2d87,0x2e1b), 660 bytes.
 *
Steps each of the 4 monster slots (parallel int arrays: active 0x5742,
 * x 0x574A, y 0x5752, path index 0x575A, fire reload 0x5762, sprite
 * 0x576A, anim countdown 0x5772, anim frame 0x577A, fire countdown 0x5782,
 * move countdown 0x578A). Every 5th tick an active monster is erased
 * (redrawn with xor_sprite, XOR-style), moved along the level's movement path
 * (huge char pointer g_level_path, (dx, dy) byte pairs, 0xEA = restart),
 * gets its sprite id recomputed per graphics mode g_gfx_index from the
 * current level g_current_level and anim frame, and is drawn again; the frame
 * advances every 2nd step. A visible monster with no live bullet
 * (object_exists(i + 1)) fires when its countdown expires and bit 5 of g_dave_state
 * is set: spawn_object spawns the bullet left or right of it depending on the
 * player x g_player_x, at y + DS:0x0156[level] / 2 - 2 (right side offset
 * DS:0x0146[level]).
 *
Codegen notes: the path index is unsigned (index extension `xor cx,cx`
 * before N_PADD@ -- the pointer is huge). `p[n]` is one PADD; the y step
 * `*(p + n + 1)` is two PADDs. `a[i] = ++a[i] & 3` keeps BX between the
 * `inc` and the reload. `x * 16` compiles to `mov cl,4; shl dx,cl`; the
 * original's four `shl dx,1` need a split constant (`* 8 * 2`). The last
 * switch case has no `break` (no jmp to the switch end).
 */

/* active */

/* x */

/* y */

/* path index */

/* fire reload time */

/* sprite id */

/* anim countdown */

/* anim frame */

/* fire countdown */

/* move countdown */

/* monster movement path */

/* graphics-mode index */

/* g_current_level */

/* player x */

void move_monsters(void)
{
    int i;
    unsigned idx;

    for (i = 0; i < 4; i++) {
        if (g_monsters.active[i] != 0 && --g_monsters.move_count[i] == 0) {
            g_monsters.move_count[i] = 5;
            xor_sprite(g_monsters.x[i], g_monsters.y[i], g_monsters.sprite[i]);
            idx = g_monsters.path_pos[i];
            if (g_level_path[idx] == -22) {
                g_monsters.path_pos[i] = 0;
                idx = 0;
            }
            g_monsters.x[i] += g_level_path[idx];
            g_monsters.y[i] += *(g_level_path + idx + 1);
            g_monsters.path_pos[i] += 2;
            switch (g_gfx_index) {
            case 0:
                g_monsters.sprite[i] = g_monsters.anim_frame[i] * 2 + (g_current_level - 2) * 8 + 0x7d;
                break;
            case 1:
                g_monsters.sprite[i] = g_monsters.anim_frame[i] * 4 + (g_current_level - 2) * 8 * 2 + 0xc5;
                break;
            case 2:
                g_monsters.sprite[i] = g_monsters.anim_frame[i] + (g_current_level - 2) * 4 + 0x59;
            }
            xor_sprite(g_monsters.x[i], g_monsters.y[i], g_monsters.sprite[i]);
            if (--g_monsters.anim_count[i] == 0) {
                g_monsters.anim_count[i] = 2;
                g_monsters.anim_frame[i] = ++g_monsters.anim_frame[i] & 3;
            }
            if (g_monsters.x[i] < 0x154 && g_monsters.x[i] >= 0 && !object_exists(i + 1) &&
                --g_monsters.fire_count[i] < 1 && (g_dave_state & 0x20)) {
                g_monsters.fire_count[i] = g_monsters.reload[i];
                if (g_monsters.x[i] > g_player_x)
                    spawn_object(g_monsters.x[i] - 16, g_monsters.y[i] + g_monster_height[g_current_level - 2] / 2 - 2, 0, 0, i + 1);
                else
                    spawn_object(g_monsters.x[i] + g_monster_width[g_current_level - 2], g_monsters.y[i] + g_monster_height[g_current_level - 2] / 2 - 2, 1, 0, i + 1);
            }
        }
    }
}

/*
 * move_bullets()
 * cs [0x2e1b,0x3005) / file [0x301b,0x3205), 490 bytes.
 *
Steps each active record of the 5-entry, 14-byte object table at
 * g_shots (bullets): direction flag (+6) 0 moves 2 px left, 1 moves 2 px
 * right. A bullet that hits a solid tile (tile_attr_at_offset attribute 1 at x-2 or
 * x+16, y+1) is deactivated after being erased with draw_object; otherwise it
 * is erased, its frame (+8) advances every 3rd tick (shared countdown
 * g_shot_anim_count), it moves, and kind-1 bullets that leave the screen
 * (x < 0 or x > 320) are dropped; the rest are redrawn (draw_object).
 */

/* bullet animation countdown */

void move_bullets(void)
{
    int x;
    int i;
    int y;

    for (i = 0; i < 5; i++) {
        if (g_shots[i].active == 1) {
            x = g_shots[i].x;
            y = g_shots[i].y;
            switch (g_shots[i].dir) {
            case 0:
                if (tile_attr_at_offset(x, y, -2, 1) == 1) {
                    g_shots[i].active = 0;
                    draw_object(i);
                    break;
                }
                draw_object(i);
                if (--g_shot_anim_count == 0) {
                    g_shot_anim_count = 3;
                    g_shots[i].frame = ++g_shots[i].frame & 3;
                }
                g_shots[i].x -= 2;
                if (g_shots[i].kind == 1 && (g_shots[i].x < 0 || g_shots[i].x > 0x140)) {
                    g_shots[i].active = 0;
                    break;
                }
                draw_object(i);
                break;
            case 1:
                if (tile_attr_at_offset(x, y, 16, 1) == 1) {
                    g_shots[i].active = 0;
                    draw_object(i);
                    break;
                }
                draw_object(i);
                if (--g_shot_anim_count == 0) {
                    g_shot_anim_count = 3;
                    g_shots[i].frame = ++g_shots[i].frame & 3;
                }
                g_shots[i].x += 2;
                if (g_shots[i].kind == 1 && (g_shots[i].x < 0 || g_shots[i].x > 0x140)) {
                    g_shots[i].active = 0;
                    break;
                }
                draw_object(i);
                break;
            }
        }
    }
}

/*
 * draw_object(i)
 * cs [0x3005,0x312c) / file [0x3205,0x332c), 295 bytes.
 *
Draws record i of the 5-entry, 14-byte object table at g_shots at its
 * (x, y) = words +2/+4. Word +0x0A selects the kind: kind 0 is animated
 * (sprite from DS:0x038E or, when word +6 is non-zero, DS:0x0376, indexed
 * g_gfx_index * 4 + frame (word +8)); kind 1 is static (sprite g_spr_shot_b0 or,
 * when word +6 is non-zero, g_spr_shot_b1, indexed g_gfx_index). Other kinds
 * draw nothing.
 */

void draw_object(int i)
{
    switch (g_shots[i].kind) {
    case 0:
        if (g_shots[i].dir == 0)
            xor_sprite(g_shots[i].x, g_shots[i].y, g_sprite_sets[2][0][g_gfx_index * 4 + g_shots[i].frame]);
        else
            xor_sprite(g_shots[i].x, g_shots[i].y, g_sprite_sets[1][0][g_gfx_index * 4 + g_shots[i].frame]);
        break;
    case 1:
        if (g_shots[i].dir == 0)
            xor_sprite(g_shots[i].x, g_shots[i].y, g_spr_shot_b0[g_gfx_index]);
        else
            xor_sprite(g_shots[i].x, g_shots[i].y, g_spr_shot_b1[g_gfx_index]);
        break;
    }
}

/*
 * animate_tiles()
 * cs [0x312c,0x3235) / file [0x332c,0x3435), 265 bytes.
 *
Every 10th call (countdown g_anim_tick_divider, reloaded with 10) steps the list of
 * animated level tiles at g_anim_tiles (12-byte records, terminated by a
 * record whose frame count is <= 0): for each active record the current
 * tile id (+4) advances and wraps from first + count back to first (+2);
 * if its level column (+6) lies within the visible window
 * [g_scroll_x, g_scroll_x + 19], the tile is redrawn via
 * DrawTile(column - g_scroll_x, row (+8), tile).
 *
Codegen notes: the visibility test is a bitwise `&` of two comparisons
 * (both materialised as 0/1, then `test ax,dx`), not `&&`. The countdown
 * here shares g_anim_tick_divider with init_game_state's "levels left = 10".
 */

/* first visible level column */

void animate_tiles(void)
{
    int i;

    if (--g_anim_tick_divider == 0) {
        for (i = 0, g_anim_tick_divider = 10; g_anim_tiles[i].count > 0; i++) {
            if (g_anim_tiles[i].active != 0) {
                if (g_anim_tiles[i].first + g_anim_tiles[i].count <= ++g_anim_tiles[i].cur)
                    g_anim_tiles[i].cur = g_anim_tiles[i].first;
                if ((g_anim_tiles[i].col >= g_scroll_x) & (g_anim_tiles[i].col <= g_scroll_x + 19))
                    DrawTile(g_anim_tiles[i].col - g_scroll_x, g_anim_tiles[i].row, g_anim_tiles[i].cur);
            }
        }
    }
}

/*
 * wait_for_input -- wait_for_input_flashing()
 * cs [0x3235,0x32cb) / file [0x3435,0x34cb), 150 bytes.
 *
Flushes a pending keystroke, then repeatedly runs erase_dave, ten
 * (WaitVBL, animate_tiles) ticks, draw_dave, ten more ticks, and polls the input
 * device through get_player_input(1) (returns a 6-byte input-state struct by value).
 * Keeps looping while the first word of that state is 8 (apparently "no
 * input") and no key is waiting. Afterwards, if bit 3 of g_dave_state (sound
 * options?) is set, plays effect 2 through PlaySound.
 *
 * Name: tentative; erase_dave/draw_dave are a show/hide pair.
 *
 * Codegen notes: a struct-returning call assigned to a local compiles to
 * `push ss; push &dst; <args>; push ss; push &tmp; call; add sp; push ss;
 * push &tmp; mov cx,size; call SCOPY@` -- the hidden return pointer is far.
 */

void wait_for_input(void)
{
    int i;
    struct input in;

    if (bioskey(1))
        bioskey(0);
    do {
        erase_dave();
        for (i = 0; i < 10; i++) {
            WaitVBL();
            animate_tiles();
        }
        draw_dave();
        for (i = 0; i < 10; i++) {
            WaitVBL();
            animate_tiles();
        }
        in = get_player_input(1);
    } while (in.dir == 8 && bioskey(1) == 0);
    if ((g_dave_state & 8) == 8)
        PlaySound(2);
}

/*
 * check_warp_transition -- check_level_exit_warp()
 * cs [0x32cb,0x351f) / file [0x34cb,0x371f), 596 bytes.
 *
Called while playing: if Dave walks off the left edge of the level top
 * row (y offset g_player_y < 16, view column g_scroll_x == 0, x g_player_x
 * < 2) or off the right edge (view column 80, x > 0x132), and this is
 * neither a warp zone (g_in_warp_zone) nor a level whose flag g_level_visited[level]
 * is already set, the player is bounced back (x = 4 or 0x130). Otherwise
 * the warp-zone entry sequence runs: blank the playfield, draw a two-column
 * tube (tile g_warp_tube_tile[level]) with two sprites, let Dave fall from y 0 to
 * 180 with sound 2, blank again, show the extra sprite when g_got_trophy == 1,
 * restore the level grid from g_tiles, mark g_level_visited[level] = 1,
 * remember the level in g_warp_return_level (g_curr_warp_zone_mapping), then load
 * level g_warp_target_level_plus1[level] - 1 (load_level) and place Dave at view column
 * g_warp_start_scroll_x[level], x g_warp_start_x[level], y offset 16; shift the 4 sprite
 * slots by the new view, redraw, wait for input (wait_for_input) and set
 * g_is_warp_zone. The warp-target table at g_warp_target_level_plus1 holds 0 for levels
 * without a warp (1-based levels 5/8/9/10 have one), so a stray warp from
 * any other level loads level -1 -- the known level-6 warp bug, preserved.
 *
 * Evidence: docs/external-re-evidence.md EXT_WARP_TRANSITION_FUNCTION
 * (g_curr_warp_zone_mapping = g_warp_return_level, tables +0x192/+0x1A6/+0x16A,
 * g_current_level -= 1, g_start_y = 0x10).
 */

/* player x */

/* player y offset (g_start_y) */

/* first visible level column */

/* g_is_warp_zone */

/* g_current_level */

/* per-level "warp used" flags */

/* graphics-mode table index */

/* per-level warp tube tile */

/* saved 100x10 tile grid */

/* current level tile grid */

/* g_curr_warp_zone_mapping */

/* warp target level (1-based, 0 = none) */

/* warp target view column */

/* warp target player x */

void check_warp_transition(void)
{
    int col;
    int k;
    int x, y;

    if ((g_player_y < 16 && g_scroll_x == 0 && g_player_x < 2) ||
        (g_scroll_x == 80 && g_player_x > 0x132)) {
        if (g_in_warp_zone == 1 || g_level_visited[g_current_level] == 1) {
            if (g_player_x < 2)
                g_player_x = 4;
            else
                g_player_x = 0x130;
            return;
        }
        erase_dave();
        g_dave_sprite = g_spr_dave_front[g_gfx_index];
        g_dave_mask = g_mask_dave_front[g_gfx_index];
        WaitVBL();
        for (y = 0; y < 10; y++)
            for (x = 0; x < 20; x++)
                DrawTile(x, y, 0);
        WaitVBL();
        for (y = 0; y < 10; y++) {
            DrawTile(8, y, g_warp_tube_tile[g_current_level]);
            DrawTile(10, y, g_warp_tube_tile[g_current_level]);
        }
        xor_sprite(0x20, 0x5a, g_spr_warp_left[g_gfx_index]);
        xor_sprite(0xc8, 0x5a, g_spr_warp_right[g_gfx_index]);
        g_player_y = 0;
        g_player_x = 0x90;
        draw_dave();
        for (k = 0; k < 30; k++)
            WaitVBL();
        PlaySound(2);
        while (g_player_y < 180) {
            WaitVBL();
            erase_dave();
            draw_dave();
            g_player_y++;
        }
        for (k = 0; k < 30; k++)
            WaitVBL();
        WaitVBL();
        for (y = 0; y < 10; y++)
            for (x = 0; x < 20; x++)
                DrawTile(x, y, 0);
        if (g_got_trophy == 1)
            xor_sprite(0x48, 0xb8, g_status_tiles[g_gfx_index * g_status_row_len + 5]);
        movmem(g_tiles, g_level, 1000);
        g_level_visited[g_current_level] = 1;
        g_warp_return_level = g_current_level;
        col = g_warp_start_scroll_x[g_current_level];
        x = g_warp_start_x[g_current_level];
        g_current_level = g_warp_target_level_plus1[g_current_level] - 1;
        load_level();
        g_scroll_x = col;
        g_player_x = x;
        g_player_y = 16;
        for (k = 0; k < 4; k++)
            if (g_monsters.active[k] == 1)
                g_monsters.x[k] -= g_scroll_x * 16;
        WaitVBL();
        DrawLevelView();
        draw_actors();
        g_dave_state = (g_dave_state & 0xe0) | 8;
        wait_for_input();
        g_in_warp_zone = 1;
    }
}

/*
 * draw_status_meter -- draw_inventory_row()
 * cs [0x351f,0x356e) / file [0x371f,0x376e), 79 bytes.
 *
Draws a sprite at (0x48, 0xAA) taken from the per-graphics-mode table
 * g_spr_meter_label[g_gfx_index], then g_jetpack_fuel copies of the per-mode sprite
 * g_spr_meter_bar[g_gfx_index] at x = 0x4C + 2*i, y = 0xAE (a horizontal meter on
 * the bottom status bar). xor_sprite is the draw-sprite(x, y, id) routine.
 */

/* graphics-mode table index */

/* meter length */

void draw_status_meter(void)
{
    int i;

    xor_sprite(0x48, 0xaa, g_spr_meter_label[g_gfx_index]);
    for (i = 0; i < g_jetpack_fuel; i++)
        xor_sprite(i * 2 + 0x4c, 0xae, g_spr_meter_bar[g_gfx_index]);
}

/*
 * draw_status_bar()
 * cs [0x356e,0x35ed) / file [0x376e,0x37ed), 127 bytes.
 *
Draws the top status line: three label sprites at x = 0, 0x78, 0xC8
 * (y = 0) and one life icon per remaining life (g_lives = g_lives) at
 * x = 0x100 + 16*i. Sprite ids come from a per-graphics-mode table at
 * DS:0x020E, row stride g_status_row_len words, row g_gfx_index.
 */

/* graphics-mode table index */

/* row stride of the sprite table (words) */

/* g_lives */

void draw_status_bar(void)
{
    int i;
    int row;

    row = g_gfx_index * g_status_row_len;
    xor_sprite(0, 0, g_status_tiles[row + 4]);
    xor_sprite(0x78, 0, g_status_tiles[row + 3]);
    xor_sprite(0xc8, 0, g_status_tiles[row + 2]);
    for (i = 0; i < g_lives; i++)
        xor_sprite(i * 16 + 0x100, 0, g_status_tiles[row + 6]);
}

/*
 * check_collisions()
 * cs [0x35ed,0x39a3) / file [0x37ed,0x3ba3), 950 bytes.
 *
Three collision passes, all box tests written with unsigned
 * differences (d < w covers 0 <= d < w, -d < w covers -w < d < 0):
 *  1. From level 3 on (g_current_level >= 2) while Dave is alive (bit 5 of
 *     g_dave_state): a visible monster overlapping Dave (box from the
 *     per-level monster size tables DS:0x0146 / DS:0x0156) kills both:
 *     Dave's state bits are cleared to the 0xC0 mask, the monster is
 *     erased and deactivated, erase_dave hides Dave and spawn_explosion spawns
 *     explosions at Dave (id 5) and at the monster (id i + 1); sound 8.
 *  2. If Dave's bullet (object id 5) is alive, a monster it hits is
 *     erased, the bullet is erased and freed, the monster explodes, sound
 *     8, and the score g_score (long) grows by (level + 1) * 100, then
 *     update_score (extra-life check / score cap).
 *  3. A monster bullet (object id i + 1) hitting Dave is erased and freed,
 *     sound 8, Dave explodes and g_dave_state becomes 0x40 (dying).
 * The loops end early with `i = 4`.
 *
 * Codegen notes: `x &= 0xc0` compiles to `and word [x],0xc0`; the
 * original's `mov ax,[x]; and ax,0xc0; mov [x],ax` is `x = x & 0xc0`.
 * Unsigned locals give the jb/ja compares.
 */

/* g_current_level */

/* monster width per level */

/* monster height per level */

/* g_score */

void check_collisions(void)
{
    unsigned a, b, c;
    int i;
    unsigned d;

    if (g_current_level >= 2 && (g_dave_state & 0x20)) {
        for (i = 0; i < 4; i++) {
            if (g_monsters.active[i] != 0 && g_monsters.x[i] < 0x140) {
                a = g_monsters.x[i] - g_player_x;
                d = g_monsters.y[i] - g_player_y;
                if ((a < 13 || g_monster_width[g_current_level - 2] > -a) &&
                    (d < 16 || g_monster_height[g_current_level - 2] > -d)) {
                    g_dave_state = g_dave_state & 0xc0;
                    xor_sprite(g_monsters.x[i], g_monsters.y[i], g_monsters.sprite[i]);
                    g_monsters.active[i] = 0;
                    erase_dave();
                    spawn_explosion(g_player_x, g_player_y + 3, 5);
                    spawn_explosion(g_monsters.x[i], g_monsters.y[i], i + 1);
                    PlaySound(8);
                }
            }
        }
    }
    if (object_exists(5) == 1) {
        for (i = 0; i < 4; i++) {
            if (g_monsters.active[i] == 1 && g_monsters.x[i] < 0x140) {
                d = find_object(5);
                a = g_shots[d].x - g_monsters.x[i];
                b = g_shots[d].y - g_monsters.y[i];
                if ((-a < 6 || g_monster_width[g_current_level - 2] > a) &&
                    (-b < 3 || g_monster_height[g_current_level - 2] > b)) {
                    c = g_shots[d].dir;
                    xor_sprite(g_monsters.x[i], g_monsters.y[i], g_monsters.sprite[i]);
                    if (c == 1)
                        c = g_spr_shot_b1[g_gfx_index];
                    else
                        c = g_spr_shot_b0[g_gfx_index];
                    xor_sprite(g_shots[d].x, g_shots[d].y, c);
                    g_shots[d].active = 0;
                    g_monsters.active[i] = 0;
                    spawn_explosion(g_monsters.x[i], g_monsters.y[i], i + 1);
                    PlaySound(8);
                    i = 4;
                    g_score += (g_current_level + 1) * 100;
                    update_score();
                }
            }
        }
    }
    if (g_dave_state & 0x20) {
        for (i = 0; i < 4; i++) {
            if (object_exists(i + 1) == 1) {
                d = find_object(i + 1);
                b = g_shots[d].x - g_player_x;
                c = g_shots[d].y - g_player_y;
                if ((-b < 16 || b < 13) && (-c < 3 || c < 16)) {
                    a = g_sprite_sets[1][0][g_gfx_index * 4 + g_shots[d].frame];
                    if (g_shots[d].dir == 0)
                        a = g_sprite_sets[2][0][g_gfx_index * 4 + g_shots[d].frame];
                    xor_sprite(g_shots[d].x, g_shots[d].y, a);
                    g_shots[d].active = 0;
                    PlaySound(8);
                    erase_dave();
                    spawn_explosion(g_player_x, g_player_y + 3, 5);
                    g_dave_state = 0x40;
                    i = 4;
                }
            }
        }
    }
}

/*
 * level_complete()
 * cs [0x39a3,0x3dd5) / file [0x3ba3,0x3fd5), 1074 bytes.
 *
 * initialiser verified in _DATA at DS:0x081A).
 *
 * Runs when the level-done flag g_level_done is set. Erases the trophy
 * indicator, restores the level grid, blanks the playfield and draws the
 * "between levels" corridor (rows 3 and 5 of tile 5, the door tile 2 at
 * 0,4); prints "good work! only N more to go!" (N = 9 - level patched into
 * the copied message), "this is the last level!!!" or "yes! you finished
 * the game!" -- unless returning from a warp zone -- and walks Dave across
 * the corridor (sound 10, step sound 4). Then StopSound, the level counter
 * g_current_level advances (draw_level_number is called before and after the warp-zone
 * return fix-up: a warp zone resumes at g_warp_return_level), and either the next
 * level starts (load_level, redraw, wait_for_input) or, after level 10, the ending
 * plays: a tile border, the "congratulations" text (10 strings at
 * DS:0x0DB5..), and a light chasing around the 55-position border path
 * until Space is pressed; then the game-over flag g_game_over is set.
 *
 * The border path tables have an off-by-one overlap: the left column
 * (positions i + 46, i = 1..8) overwrites the last bottom-row entry 47.
 * Preserved as in the original.
 *
 * Evidence: docs/external-re-evidence.md EXT_LEVEL_COMPLETE_FUNCTION
 * (the StopSound, draw_level_number x2, load_level, WaitVBL, DrawLevelView, draw_actors, wait_for_input
 * sequence).
 */

/* level done */

/* text cursor column */

/* text cursor row */

/* g_current_level */

/* g_is_warp_zone */

/* warp return level */

/* video mode */

/* game over */

void level_complete(void)
{
    struct input in;
    int y;
    int frame;
    int pos;
    int msg_no;
    char key;
    int xs[58];
    int ys[58];
    char msg[3][35] = {
        "good work! only 9 more to go!",
        "  this is the last level!!!",
        " yes! you finished the game!"
    };
    int i, x;

    if (g_level_done == 1) {
        xor_sprite(0x48, 0xb8, g_status_tiles[g_gfx_index * g_status_row_len + 5]);
        movmem(g_tiles, g_level, 1000);
        WaitVBL();
        for (y = 0; y < 10; y++)
            for (x = 0; x < 20; x++)
                DrawTile(x, y, 0);
        DrawTile(0, 4, 2);
        for (x = 0; x < 20; x++) {
            DrawTile(x, 3, 5);
            DrawTile(x, 5, 5);
        }
        XorMask = -1;
        g_text_x = 6;
        g_text_y = 7;
        if (g_current_level < 8) {
            msg_no = 0;
            msg[0][16] = 9 - g_current_level + '0';
        }
        if (g_current_level == 8)
            msg_no = 1;
        if (g_current_level == 9)
            msg_no = 2;
        if (g_in_warp_zone == 0)
            print_string(msg[msg_no]);
        XorMask = 0;
        g_player_x = 0x10;
        g_player_y = 0x50;
        g_dave_sprite = g_sprite_sets[11][0][g_gfx_index * 4 + g_anim_frame];
        g_dave_mask = g_sprite_sets[12][0][g_gfx_index * 4 + g_anim_frame];
        draw_dave();
        PlaySound(10);
        for (g_player_x = 0x10; g_player_x < 0x130; g_player_x += 2) {
            WaitVBL();
            WaitVBL();
            WaitVBL();
            erase_dave();
            if (g_player_x % 3 == 2) {
                g_anim_frame++;
                if (g_anim_frame > 3)
                    g_anim_frame = 0;
            }
            g_dave_sprite = g_sprite_sets[11][0][g_gfx_index * 4 + g_anim_frame];
            g_dave_mask = g_sprite_sets[12][0][g_gfx_index * 4 + g_anim_frame];
            draw_dave();
            if (g_player_x % 5 == 4)
                PlaySound(4);
        }
        StopSound();
        g_current_level++;
        draw_level_number();
        if (g_in_warp_zone == 1) {
            g_in_warp_zone = 0;
            g_current_level = g_warp_return_level;
        }
        if (g_current_level < 10) {
            draw_level_number();
            load_level();
            WaitVBL();
            DrawLevelView();
            draw_actors();
            wait_for_input();
        } else {
            set_video_mode(g_video_mode);
            for (i = 0; i < 20; i++) {
                DrawTile(i, 0, 10);
                DrawTile(i, 9, 10);
                if (i >= 1 && i < 9) {
                    DrawTile(0, i, 10);
                    DrawTile(19, i, 10);
                }
            }
            for (i = 0; i < 20; i++) {
                xs[i] = i;
                ys[i] = 0;
            }
            for (i = 1; i < 9; i++) {
                xs[i + 19] = 19;
                ys[i + 19] = i;
            }
            for (i = 0; i < 20; i++) {
                xs[i + 28] = 19 - i;
                ys[i + 28] = 9;
            }
            for (i = 1; i < 9; i++) {
                xs[i + 46] = 0;
                ys[i + 46] = 9 - i;
            }
            XorMask = -1;
            g_text_left = 3;
            g_text_x = g_text_left;
            g_text_y = 5;
            print_string("         congratulations!\r\n\n\n");
            print_string("you made it through all the peril-\r\n");
            print_string("ous areas in clyde's hideout!\r\n\n");
            print_string("very good work! did you find\r\n");
            print_string("the 4 warp zones? they are located\r\n");
            print_string("on levels 5,8,9 and 10. just jump\r\n");
            print_string("off the top of the screen at the\r\n");
            print_string("extreme left or right edge of the\r\n");
            print_string("world and voila! you're there!\r\n\n\n");
            print_string("           press space");
            XorMask = 0;
            frame = 0;
            pos = 0;
            do {
                if (frame % 4 == 0)
                    WaitVBL();
                key = bioskey(1);
                if (++frame > 3)
                    frame = 0;
                DrawTile(xs[pos], ys[pos], frame + 10);
                if (++pos > 54)
                    pos = 0;
                in = get_player_input(1);
            } while (key != ' ');
            bioskey(0);
            g_game_over = 1;
        }
    }
}

/*
 * pick_up_items()
 * cs [0x3dd5,0x44b0) / file [0x3fd5,0x46b0), 1755 bytes.
 *
While Dave is alive (bit 5 of g_dave_state) and inside the playfield
 * (16 < y < 0xA6), looks at the 2x2 tiles under him (grid g_level, row
 * offsets RowTimes100) and, for each, against the 10 collectible tile ids
 * g_pickup_tile_ids[k] (values g_pickup_points[k]): a non-door item adds its value to
 * the score g_score (long; update_score handles extra lives), plays sound 6
 * and is removed from the grid and the screen. Then per item type:
 * 10 = trophy (sets g_got_trophy, sound 7, stops the trophy's animated-tile
 * entries, shows the "go thru the door" sprite), 2 = door (only with the
 * trophy: sets the level-done flag g_level_done and adds the door value),
 * 20 = gun (g_has_gun, sprite, sound 12), 4 = jetpack (fuel meter
 * g_jetpack_fuel = 60, g_fuel_tick = 15, g_has_jetpack, sound 12).
 *
Codegen notes: the per-tile block is written once as a macro and
 * expanded four times (tile offsets 0, 1, 100, 101); the original has
 * four identical copies, so it was either a macro or copy-paste.
 */

/* collectible tile ids */

/* their point values */

/* g_score */

/* has trophy */

/* has gun */

/* has jetpack */

/* level done */

/* jetpack fuel meter */

#define PICK(t, o, dx, dy)                                              \
    if (g_pickup_tile_ids[k] == t) {                                               \
        if (t != 2) {                                                   \
            g_score += g_pickup_points[k];                                        \
            update_score();                                                   \
            StopSound();                                                   \
            PlaySound(6);                                                  \
            *(g_level + pos + o) = 0;                                           \
            erase_dave();                                                   \
            DrawTile(col - g_scroll_x + dx, row + dy, 0);                     \
            draw_dave();                                                   \
        }                                                               \
        switch (t) {                                                    \
        case 10:                                                        \
            if (g_got_trophy == 0) {                                          \
                g_got_trophy = 1;                                             \
                PlaySound(7);                                              \
                for (i = 0; g_anim_tiles[i].count > 0; i++)                   \
                    if (g_anim_tiles[i].first == 10)                          \
                        g_anim_tiles[i].active = 0;                           \
                xor_sprite(0x48, 0xb8, g_status_tiles[g_gfx_index * g_status_row_len + 5]);            \
            }                                                           \
            break;                                                      \
        case 2:                                                         \
            if (g_got_trophy == 1) {                                          \
                g_level_done = 1;                                             \
                g_score += g_pickup_points[k];                                    \
                update_score();                                               \
            }                                                           \
            break;                                                      \
        case 20:                                                        \
            g_has_gun = 1;                                                 \
            xor_sprite(0xf0, 0xaa, g_status_tiles[g_gfx_index * g_status_row_len + 1]);                \
            PlaySound(12);                                                 \
            break;                                                      \
        case 4:                                                         \
            if (g_has_jetpack != 1)                                            \
                xor_sprite(0, 0xaa, g_status_tiles[g_gfx_index * g_status_row_len]);               \
            if (g_has_jetpack == 1)                                            \
                draw_status_meter();                                               \
            g_jetpack_fuel = 60;                                                \
            g_fuel_tick = 15;                                                \
            draw_status_meter();                                                   \
            g_has_jetpack = 1;                                                 \
            PlaySound(12);                                                 \
            break;                                                      \
        }                                                               \
    }

void pick_up_items(void)
{
    int t00, t01, t10, t11;
    int col, row, pos;
    int i, k;

    if ((g_dave_state & 0x20) && g_player_y > 16 && g_player_y < 0xa6) {
        col = g_player_x / 16 + g_scroll_x;
        row = (g_player_y - 16) / 16;
        pos = RowTimes100[row] + col;
        t00 = g_level[pos];
        t01 = *(g_level + pos + 1);
        t10 = *(g_level + pos + 100);
        t11 = *(g_level + pos + 101);
        for (k = 0; k < 10; k++) {
            PICK(t00, 0, 0, 0)
            PICK(t01, 1, 1, 0)
            PICK(t10, 100, 0, 1)
            PICK(t11, 101, 1, 1)
        }
    }
}

/*
 * scroll_screen -- scroll_if_needed()
 * cs [0x44b0,0x45f8) / file [0x46b0,0x47f8), 328 bytes.
 *
Horizontal scrolling. When the player's x (g_player_x) passes 0x118 and
 * the view column g_scroll_x is below 80 (100-column level, 20 visible),
 * scrolls right 15 columns, one per frame: the view column is incremented,
 * every on-screen entity x (DS:0x574A[4], object table g_shots, actor
 * table g_actors) and the player x move 16 pixels left, and the frame is
 * redrawn (WaitVBL, DrawLevelView, draw_actors). Stops early at column 80. When the
 * player x drops below 0x20 and the view column is > 0 it scrolls left the
 * same way. Both directions bracket the work with PauseSound / ResumeSound and, if
 * g_player_y < 16, erase_dave / draw_dave.
 *
Codegen notes: the early exit is `j = 15;` in an else branch (the loop
 * ends with `mov di,0xf; inc di`).
 */

/* player x (pixels, screen-relative) */

/* first visible level column */

void scroll_screen(void)
{
    int i, j;

    if (g_player_x > 0x118 && g_scroll_x < 80) {
        PauseSound();
        if (g_player_y < 16)
            erase_dave();
        for (j = 0; j < 15; j++) {
            if (g_scroll_x < 80) {
                g_scroll_x++;
                for (i = 0; i < 4; i++)
                    g_monsters.x[i] -= 16;
                for (i = 0; i < 5; i++)
                    g_shots[i].x -= 16;
                for (i = 0; i < 6; i++)
                    g_actors[i].x -= 16;
                g_player_x -= 16;
                WaitVBL();
                DrawLevelView();
                draw_actors();
            } else
                j = 15;
        }
        ResumeSound();
        if (g_player_y < 16)
            draw_dave();
    } else if (g_player_x < 0x20 && g_scroll_x > 0) {
        if (g_player_y < 16)
            erase_dave();
        PauseSound();
        for (j = 0; j < 15; j++) {
            if (g_scroll_x > 0) {
                g_scroll_x--;
                for (i = 0; i < 4; i++)
                    g_monsters.x[i] += 16;
                for (i = 0; i < 5; i++)
                    g_shots[i].x += 16;
                for (i = 0; i < 6; i++)
                    g_actors[i].x += 16;
                g_player_x += 16;
                WaitVBL();
                DrawLevelView();
                draw_actors();
            } else
                j = 15;
        }
        ResumeSound();
        if (g_player_y < 16)
            draw_dave();
    }
}

/*
 * find_object(id)
 * cs [0x45f8,0x463f) / file [0x47f8,0x483f), 71 bytes.
 *
Scans the 5-entry table of 14-byte records at g_shots and returns the
 * index of the first record whose word 0 is 1 (active) and whose word at
 * +0x0C equals id; -1 if none.
 */

/* 5 objects, 14 bytes each */

int find_object(int id)
{
    register int i;

    for (i = 0; i < 5; i++)
        if (g_shots[i].active == 1 && g_shots[i].id == id)
            return i;
    return -1;
}

/*
 * object_exists(id)
 * cs [0x463f,0x4686) / file [0x483f,0x4886), 71 bytes.
 *
Like find_object but returns 1 if an active record with word +0x0C == id
 * exists in the 5-entry table at g_shots, else 0.
 */

/* 5 objects, 14 bytes each */

int object_exists(int id)
{
    register int i;

    for (i = 0; i < 5; i++)
        if (g_shots[i].active == 1 && g_shots[i].id == id)
            return 1;
    return 0;
}

/*
 * spawn_object(x, y, flag, kind, id)
 * cs [0x4686,0x4797) / file [0x4886,0x4997), 273 bytes.
 *
Unless the level tile at pixel (x, y + 1) has attribute 1 (solid, via
 * tile_attr_at_offset), takes the first free record of the 5-entry, 14-byte object table
 * at g_shots, fills it (active = 1, x, y, id, flag, frame = 0, kind) and
 * draws it once at (x, y) with the sprite draw_object would use for it.
 */

void spawn_object(int x, int y, int flag, int kind, int id)
{
    int base;
    int i;
    int sprite;

    base = g_gfx_index * 4;
    if (tile_attr_at_offset(x, y, 0, 1) == 1)
        return;
    for (i = 0; i < 5; i++) {
        if (g_shots[i].active == 0) {
            g_shots[i].active = 1;
            g_shots[i].x = x;
            g_shots[i].y = y;
            g_shots[i].id = id;
            g_shots[i].dir = flag;
            g_shots[i].frame = 0;
            g_shots[i].kind = kind;
            sprite = g_sprite_sets[1][0][base];
            if (flag == 0)
                sprite = g_sprite_sets[2][0][base];
            if (kind == 1) {
                sprite = g_spr_shot_b1[g_gfx_index];
                if (flag == 0)
                    sprite = g_spr_shot_b0[g_gfx_index];
            }
            xor_sprite(x, y, sprite);
            return;
        }
    }
}

/*
 * handle_menu_key -- title_handle_key()
 * cs [0x4797,0x4827) / file [0x4997,0x4a27), 144 bytes.
 *
Peeks at the keyboard (bioskey(1)) and dispatches on the scan code:
 * F1 (0x3B) -> show_help, F2 (0x3C) -> control_panel, F3 (0x3D) -> ask_restart,
 * F9 (0x43) -> pause_game, Esc (0x01) / F10 (0x44) -> ask_quit. Any other key
 * while g_demo_mode == 1 (attract/demo mode) restores the 1000-byte (100x10)
 * tile grid from the backup at g_tiles into the current level grid
 * (pointer g_level), clears demo mode and starts a new game: StopSound,
 * init_game_state (init_game_state), load_level, redraw_screen, wait_for_input.
 */

/* demo / attract mode flag */

/* saved 100x10 tile grid */

/* current level tile grid */

void handle_menu_key(void)
{
    int key;

    key = bioskey(1) >> 8;
    switch (key) {
    case 0x3b: show_help(); break;
    case 0x3c: control_panel(); break;
    case 0x3d: ask_restart(); break;
    case 0x43: pause_game(); break;
    case 1:
    case 0x44: ask_quit(); break;
    default:
        if (g_demo_mode == 1 && key != 0) {
            movmem(g_tiles, g_level, 1000);
            g_demo_mode = 0;
            StopSound();
            init_game_state();
            load_level();
            redraw_screen();
            wait_for_input();
        }
    }
}

/*
 * process_input()
 * cs [0x4827,0x4b9c) / file [0x4a27,0x4c9c), 885 bytes incl. the 8-entry
 * switch jump table.
 *
 * Per-frame input handling. Reads the input state (get_player_input(1): direction
 * 0..8, fire, jetpack). In demo playback (g_demo_mode == 1) the state is
 * replaced from the demo stream g_demo_data (far, g_demo_data) at index
 * g_demo_pos: ' ' n = n idle frames (counter g_demo_repeat), '0' = end of demo
 * (restore the level grid, leave playback), otherwise a packed byte
 * (bit 7 fire, bit 6 jetpack, low nibble direction). The direction maps
 * to the movement state g_input_dir. Fire / jetpack auto-repeat counters
 * (signed chars g_fire_repeat / 0x00AD, reload 30) are reset when the button
 * is released. In demo recording (g_demo_recording == 1) the state is appended to
 * the stream run-length encoded. Firing (if Dave has the gun g_has_gun,
 * no own bullet (id 5) alive and 8 < y < 0xAA) spawns a bullet left or
 * right of Dave (facing g_dave_facing). The jetpack button toggles jetpack
 * flight (bit 0 of g_dave_state; needs fuel g_has_jetpack > 0; sounds 11 / 2)
 * and selects the matching player sprites. Finally handle_menu_key handles keys.
 *
Codegen notes: the packed byte is a local of an inner block, so it is
 * allocated after the struct-return temporary (bp-0x0D vs bp-0x0C).
 * `char = a << 7 | b << 6 | c` is computed in byte registers.
 */

/* demo playback */

/* demo recording */

/* demo run-length counter */

/* g_demo_data */

/* g_demo_pos */

/* movement state */

/* fire repeat counter */

/* jetpack repeat counter */

/* has gun */

/* facing */

/* jetpack fuel */

void process_input(void)
{
    struct input in;

    in = get_player_input(1);
    if (g_demo_mode == 1) {
        if (g_demo_repeat == 0) {
            if (g_demo_data[g_demo_pos] == ' ') {
                g_demo_pos++;
                g_demo_repeat = g_demo_data[g_demo_pos];
                g_demo_pos++;
            } else if (g_demo_data[g_demo_pos] == '0') {
                g_demo_mode++;
                movmem(g_tiles, g_level, 1000);
            } else {
                in.dir = g_demo_data[g_demo_pos] & 0xf;
                in.fire = g_demo_data[g_demo_pos] >> 7 & 1;
                in.jump = g_demo_data[g_demo_pos] >> 6;
                g_demo_pos++;
            }
        } else {
            g_demo_repeat--;
            in.dir = 8;
            in.fire = 0;
            in.jump = 0;
        }
    }
    switch (in.dir) {
    case 4: g_input_dir = 4; break;
    case 5:
    case 6: g_input_dir = 6; break;
    case 2:
    case 3: g_input_dir = 2; break;
    case 0: g_input_dir = 0; break;
    case 7: g_input_dir = 7; break;
    case 1: g_input_dir = 1; break;
    }
    if (g_fire_repeat > 0 && in.fire == 1)
        g_fire_repeat--;
    if (g_fire_repeat != 30 && in.fire == 0)
        g_fire_repeat = 0;
    if (g_jetpack_repeat > 0 && in.jump == 1)
        g_jetpack_repeat--;
    if (g_jetpack_repeat != 30 && in.jump == 0)
        g_jetpack_repeat = 0;
    if (g_demo_recording == 1) {
        if (in.dir == 8 && in.fire == 0 && in.jump == 0)
            g_demo_repeat++;
        else {
            char packed;

            packed = in.fire << 7 | in.jump << 6 | in.dir;
            if (g_demo_repeat != 0) {
                g_demo_data[g_demo_pos] = ' ';
                g_demo_pos++;
                g_demo_data[g_demo_pos] = g_demo_repeat - 1;
                g_demo_pos++;
                g_demo_repeat = 0;
            }
            g_demo_data[g_demo_pos] = packed;
            g_demo_pos++;
        }
    }
    if (g_fire_repeat == 0 && (g_dave_state & 0x20)) {
        g_fire_repeat = 30;
        if (g_has_gun > 0 && !object_exists(5) && g_player_y > 8 && g_player_y < 0xaa) {
            if (g_dave_facing == 0)
                spawn_object(g_player_x - 10, g_player_y + 7, 0, 1, 5);
            else
                spawn_object(g_player_x + 20, g_player_y + 7, 1, 1, 5);
        }
    }
    if (g_jetpack_repeat == 0 && (g_dave_state & 0x20)) {
        g_jetpack_repeat = 30;
        if (!(g_dave_state & 1) && g_has_jetpack > 0) {
            PlaySound(11);
            g_dave_state = (g_dave_state & 0xe0) | 1;
            g_jet_facing = 1;
            g_dave_sprite = g_sprite_sets[3][0][g_gfx_index * 4 + g_anim_frame];
            g_dave_mask = g_sprite_sets[4][0][g_gfx_index * 4 + g_anim_frame];
            if (g_input_dir == 6 || g_input_dir == 7 || g_input_dir == 5) {
                g_jet_facing = 0;
                g_dave_sprite = g_sprite_sets[5][0][g_gfx_index * 4 + g_anim_frame];
                g_dave_mask = g_sprite_sets[6][0][g_gfx_index * 4 + g_anim_frame];
            }
        } else if ((g_dave_state & 1) == 1) {
            g_dave_state = (g_dave_state & 0xfe) | 8;
            PlaySound(2);
            g_prev_dir = g_input_dir;
            g_input_dir = 8;
            g_dave_sprite = g_spr_dave_front[g_gfx_index];
            g_dave_mask = g_mask_dave_front[g_gfx_index];
        }
    }
    handle_menu_key();
}

/*
 * draw_actors()
 * cs [0x4b9c,0x4c69) / file [0x4d9c,0x4e69), 205 bytes.
 *
Per-frame sprite pass: if the playfield offset g_player_y > 15 and bit 5
 * of g_dave_state is set, calls draw_dave; draws each of 4 active entries of the
 * parallel arrays at g_monsters (flag) / 0x574A (x) / 0x5752 (y) /
 * 0x576A (sprite); calls draw_object(i) for each active 14-byte record of
 * g_shots (5 entries); then draws each active 314-byte record of
 * g_actors (6 entries) at its (x, y) with sprite
 * g_sprite_sets[g_gfx_index * 4 + frame].
 */

void draw_actors(void)
{
    int i;

    if (g_player_y > 15 && (g_dave_state & 0x20))
        draw_dave();
    for (i = 0; i < 4; i++)
        if (g_monsters.active[i] == 1)
            xor_sprite(g_monsters.x[i], g_monsters.y[i], g_monsters.sprite[i]);
    for (i = 0; i < 5; i++)
        if (g_shots[i].active == 1)
            draw_object(i);
    for (i = 0; i < 6; i++)
        if (g_actors[i].active == 1)
            xor_sprite(g_actors[i].x, g_actors[i].y, g_sprite_sets[0][0][g_gfx_index * 4 + g_actors[i].frame]);
}

/*
 * load_level()
 * cs [0x4c69,0x4f9b) / file [0x4e69,0x519b), 818 bytes.
 *
Sets up level g_current_level (g_current_level, 0-based): reseeds rand with
 * 100, loads the per-level option bits (byte table g_level_flags) into
 * g_dave_state and Dave's start x/y (g_level_start_x/0x0136) into g_player_x/EC,
 * resets the player animation state, and points g_level at the level
 * record g_levels[level] (near pointer at LevelPtr, 0x500-byte records:
 * 256-byte monster path then 100x10 tiles). Clears the actor (6), object
 * (5) and animated-tile (200) tables, then scans the 1000 tiles: every
 * tile equal to one of the 4 animated base tiles g_animated_tile_ids[k] gets an
 * animated-tile record (base, random start frame within the
 * g_animated_tile_frames[k]-frame cycle, column, row, frame count; the next record's
 * count is zeroed as terminator). Copies the level's 80-byte monster
 * block g_level_monster_init[level] into the monster arrays at g_monsters, gives each
 * monster a random start frame and its per-mode sprite base, sets the
 * monster path pointer g_level_path (huge) to the record start, advances
 * g_level to the tile map and copies it to the working grid g_tiles,
 * resets the view column and redraws the status items flagged in
 * g_has_gun / g_has_jetpack.
 *
 * Evidence: data lane (g_levels at DGROUP:0x173A, 10 x 0x500, pointer at
 * LevelPtr; load_level = loader); level index -1 (level-6 warp bug) reads
 * the record before g_levels.
 *
 * Codegen notes: `(long)rand() * n / 32767` compiles to push 0:7FFF,
 * rand, cwd, N_LXMUL@, N_LDIV@. The terminator store
 * `t[n + 1].count = 0` folds into `[bx + 0x57FE]` with bx = n * 12.
 * Here every switch case ends with `break`.
 */

/* per-level option bits */

/* g_current_level */

/* level start x */

/* level start y */

/* current level record / tile map */

/* g_levels */

/* animated base tiles */

/* their frame counts */

/* monster path */

/* working tile grid */

void load_level(void)
{
    int col;
    int row;
    int tile;
    int k;
    int i;
    int n;

    g_level_done = 0;
    srand(100);
    g_dave_state = g_level_flags[g_current_level];
    g_player_x = g_level_start_x[g_current_level];
    g_player_y = g_level_start_y[g_current_level];
    g_death_pause = 3;
    g_anim_delay = 2;
    g_dave_sprite = g_spr_dave_front[g_gfx_index];
    g_dave_mask = g_mask_dave_front[g_gfx_index];
    g_anim_frame = 0;
    g_input_dir = 8;
    g_dave_facing = 1;
    g_level = LevelPtr + g_current_level * 0x500;
    g_shot_anim_count = 3;
    for (i = 0; i < 6; i++)
        g_actors[i].active = 0;
    for (i = 0; i < 5; i++)
        g_shots[i].active = 0;
    for (i = 0; i < 200; i++)
        g_anim_tiles[i].active = 0;
    n = 0;
    col = 0;
    row = 0;
    for (i = 0; i < 1000; i++) {
        tile = g_level[i + 0x100];
        for (k = 0; k < 4; k++) {
            if (g_animated_tile_ids[k] == tile) {
                g_anim_tiles[n].active = 1;
                g_anim_tiles[n].first = tile;
                g_anim_tiles[n].cur = tile + (long)rand() * g_animated_tile_frames[k] / 32767;
                g_anim_tiles[n].col = col;
                g_anim_tiles[n].row = row;
                g_anim_tiles[n].count = g_animated_tile_frames[k];
                g_anim_tiles[n + 1].count = 0;
                n++;
            }
        }
        col++;
        if (col == 100) {
            col = 0;
            row++;
        }
    }
    g_monsters = g_level_monster_init[g_current_level];
    for (i = 0; i < 4; i++) {
        g_monsters.anim_count[i] = 2;
        g_monsters.anim_frame[i] = (long)rand() * 3 / 32767;
        g_monsters.move_count[i] = 5;
        g_monsters.fire_count[i] = g_monsters.reload[i];
        switch (g_gfx_index) {
        case 0:
            g_monsters.sprite[i] = (g_current_level - 2) * 8 + 0x7d;
            break;
        case 1:
            g_monsters.sprite[i] = (g_current_level - 2) * 8 * 2 + 0xc5;
            break;
        case 2:
            g_monsters.sprite[i] = (g_current_level - 2) * 4 + 0x59;
            break;
        }
    }
    g_level_path = g_level;
    g_level += 0x100;
    movmem(g_level, g_tiles, 1000);
    g_scroll_x = 0;
    if (g_has_gun == 1)
        xor_sprite(0xf0, 0xaa, g_status_tiles[g_gfx_index * g_status_row_len + 1]);
    if (g_has_jetpack == 1) {
        draw_status_meter();
        xor_sprite(0, 0xaa, g_status_tiles[g_gfx_index * g_status_row_len]);
    }
    g_has_jetpack = 0;
    g_got_trophy = 0;
    g_has_gun = 0;
}

/*
 * init_game_once()
 * cs [0x4f9b,0x515a) / file [0x519b,0x535a), 447 bytes.
 * EXACT (strict): 43 fixups incl. the far segments 1C2E/0B31 (MZ relocations
 * verified) and the SCOPY'd initialiser in _DATA at DS:0x0883.
 *
 * One-time start-up: allocates the 0x16000-byte far work buffer
 * (farmalloc_aligned, result to g_tileset), calls the asm stub InitLevelPtr (sets the far
 * level pointer LevelPtr), points g_sound_data (SoundData) at the far
 * PC-speaker sound segment 1C2E:0000, runs StartSound and install_keyboard_handler, points
 * g_demo_data (g_demo_data) at the far demo-recording segment 0B31:0000,
 * mallocs the 45-byte high-score file buffer (g_hiscore_buf) and loads
 * "DSCORES.DAV" (g_hiscore_file) into it via read_file_far; if that fails, writes the
 * default table (initialised local copied from DS:0x0883: five entries
 * of level 1, score "00100", initials "JON") with write_file_far and uses it.
 * Then init_game_state (init_game_state), clears g_quit and decodes the five
 * 9-byte file entries (level byte, five score digit bytes, three initials)
 * into the 7-byte high-score records at g_hiscores.
 *
 * Evidence: docs/data-layout.md (g_sound_data = 1C2E:0000, g_demo_data
 * = 0B31:0000 set here; DSCORES.DAV string at g_hiscore_file).
 *
 * Codegen note: the far pointer to `def` is pushed as `lea ax; push ds;
 * push ax`. A plain near->far conversion gives `push ss`/`push ds` first;
 * converting through `long` (`(char far *)(long)def`) reproduces the
 * original order (the same idiom matches draw_text_window's near->far conversions).
 */

/* far work buffer */

/* g_sound_data */

/* g_demo_data */

/* far segment 1C2E: PC-speaker sounds */

/* far segment 0B31: demo recordings */

/* high-score file buffer */

/* "DSCORES.DAV" */

void init_game_once(void)
{
    struct hiscore def[5] = {
        { 1, { 0, 0, 1, 0, 0 }, { 'J', 'O', 'N' } },
        { 1, { 0, 0, 1, 0, 0 }, { 'J', 'O', 'N' } },
        { 1, { 0, 0, 1, 0, 0 }, { 'J', 'O', 'N' } },
        { 1, { 0, 0, 1, 0, 0 }, { 'J', 'O', 'N' } },
        { 1, { 0, 0, 1, 0, 0 }, { 'J', 'O', 'N' } }
    };
    int i;

    g_tileset = farmalloc_aligned(0x16000L);
    InitLevelPtr();
    SoundData = g_sound_bank;
    StartSound();
    install_keyboard_handler();
    g_demo_data = g_demo_bank;
    g_hiscore_buf = malloc(45);
    if (read_file_far(g_hiscore_file, g_hiscore_buf) == 0) {
        write_file_far(g_hiscore_file, (char far *)(long)def, 45L);
        movedata(_DS, (unsigned)def, _DS, (unsigned)g_hiscore_buf, 45);
    }
    init_game_state();
    g_quit = 0;
    for (i = 0; i < 5; i++) {
        g_hiscores[i].score = g_hiscore_buf[i].score[0] * 10000 + g_hiscore_buf[i].score[1] * 1000 +
                          g_hiscore_buf[i].score[2] * 100 + g_hiscore_buf[i].score[3] * 10 +
                          g_hiscore_buf[i].score[4];
        g_hiscores[i].level = g_hiscore_buf[i].level;
        g_hiscores[i].name[0] = g_hiscore_buf[i].name[0];
        g_hiscores[i].name[1] = g_hiscore_buf[i].name[1];
        g_hiscores[i].name[2] = g_hiscore_buf[i].name[2];
    }
}

/*
 * init_game_state()
 * cs [0x515a,0x51c3) / file [0x535a,0x53c3), 105 bytes.
 *
Resets the per-game state at the start of a new game: clears a 10-word
 * table at g_level_visited, sets lives (g_lives) to 3, zeroes the 32-bit score
 * (g_score/62) and the 32-bit next-extra-life goal (g_next_extra_life/4A), clears
 * the game-over flag (g_game_over), the current level (g_current_level), the level
 * reference (g_scroll_x), sets the levels-left counter (g_anim_tick_divider) to 10,
 * clears the warp-zone flag (g_in_warp_zone) and finally re-applies the video
 * mode held in g_video_mode via set_video_mode (set_video_mode).
 *
 * Evidence: docs/external-re-evidence.md EXT_INIT_FUNCTION (g_lives=3,
 * scores/goals zeroed, g_maybe_levels_left=10 ...), verified byte-for-byte.
 *
 * Codegen notes: needs the -G flag (optimise for speed, directive below):
 * without it the 2-byte argument cleanup is `pop cx` instead of
 * `inc sp; inc sp`. `for` with a register int counter compiles to
 * `xor si,si; jmp cond; body; inc si; cond: cmp si,N; jl body`.
 */

/* 10-word per-game table */

/* g_lives */

/* g_score low word */

/* g_score high word */

/* g_next_goal low word */

/* g_next_goal high word */

/* g_is_game_over */

/* g_current_level */

/* g_some_level_reference */

/* g_levels_left */

/* g_is_warp_zone */

/* video mode */

void init_game_state(void)
{
    int i;

    for (i = 0; i < 10; i++)
        g_level_visited[i] = 0;
    g_lives = 3;
    g_score = 0;
    g_next_extra_life = 0;
    g_game_over = 0;
    g_current_level = 0;
    g_scroll_x = 0;
    g_anim_tick_divider = 10;
    g_in_warp_zone = 0;
    set_video_mode(g_video_mode);
}

