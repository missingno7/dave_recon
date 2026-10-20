/*
 * The input model: what one game step consumes from the player.
 *
 * struct frame_input is the LOGICAL input sample, already decoded according
 * to the user's settings (state-model.md D6: input device, key bindings,
 * joystick calibration and mouse dead zone live outside struct game, in the
 * platform/config layer). The game never sees scan codes of movement keys, a
 * key-state table, joystick port timings or mouse coordinates.
 *
 * Correspondence with the original (src/HARDWARE.C, src/DAVE.C):
 *
 *   dir, fire, jump   = struct input returned by get_player_input(1): the
 *                       device chosen in g_input_device[1] (DS 0x12F2) read by
 *                       read_keyboard_input (g_keydown[] at DS 0x8A32 through
 *                       the bindings g_key_scans[10] at DS 0x1310: 8 direction
 *                       keys N..NW, then fire and jump/jetpack),
 *                       read_mouse_input (INT 33h) or read_joystick_input
 *                       (port 201h). The original reads the device afresh at
 *                       each poll; one frame_input is one such poll.
 *   menu_key          = bioskey(1) >> 8: the scan code of the key waiting in
 *                       the BIOS buffer (0 = none). The original's INT 9
 *                       handler empties the BIOS buffer on every make code
 *                       before chaining to the BIOS, so at most ONE key is
 *                       ever waiting: the last one pressed and not consumed.
 *                       Only the menu/function keys act on it in play
 *                       (handle_menu_key: F1 help, F2 control panel, F3
 *                       restart, F9 pause, F10 / Esc quit; any key ends a demo).
 *   dos_seconds       = the DOS time of day in seconds (D7: time is an
 *                       input), read only by srand(time(NULL)) when the title
 *                       times out into a demo.
 *
 * Direction quirks kept by the device decoders (platform), not the game: the
 * keyboard reader tests N, E, S, W, then the diagonal keys NE, NW, SE, SW,
 * each later key overriding the axes it sets (down beats up, left beats
 * right, any diagonal beats the straight keys, SW beats all).
 *
 * The demo stream is NOT an input: during attract demos the original still
 * reads the live device (an idle-run byte's own frame keeps it) and then
 * substitutes bytes from the demo bank, which is game logic in process_input
 * (player.c) driven by game.demo and the demo-bank resource.
 *
 * The test bridge reconstructs a frame_input from an original DGROUP
 * snapshot plus the scenario's key events (port/tests/bridge/world_io.c); the
 * platform layer (later) fills it from the real devices once per retrace.
 */
#ifndef DAVE_INPUT_H
#define DAVE_INPUT_H

#include <stdint.h>

enum input_dir {         /* 0..7 clockwise from north, as the original's readers */
    DIR_N = 0, DIR_NE = 1, DIR_E = 2, DIR_SE = 3, DIR_S = 4, DIR_SW = 5, DIR_W = 6, DIR_NW = 7,
    DIR_NONE = 8
};

/* BIOS scan codes of the keys handle_menu_key acts on (frame_input.menu_key). */
enum menu_scan {
    SCAN_ESC = 0x01, SCAN_F1 = 0x3B, SCAN_F2 = 0x3C, SCAN_F3 = 0x3D, SCAN_F9 = 0x43, SCAN_F10 = 0x44
};

struct frame_input {
    int16_t  dir;          /* enum input_dir */
    int16_t  fire;         /* 0 / 1: the fire button (default binding Ctrl) */
    int16_t  jump;         /* 0 / 1: the jump/jetpack button (default binding Alt) */
    int16_t  menu_key;     /* scan code of the waiting BIOS key, 0 = none */
    uint32_t dos_seconds;  /* DOS time of day, seconds (D7) */
};

#endif
