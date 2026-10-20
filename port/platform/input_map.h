/*
 * Settings-dependent decoding of raw device state into the game's logical
 * input sample (port/game/input.h). Platform layer: the game never sees
 * this. The real-time device reading itself (keyboard ISR, joystick port
 * timing, mouse INT 33h in the original) stays in the platform backends;
 * this file only holds the pure decoding rules, so the platform and the test
 * bridge share one implementation of the original's read_keyboard_input.
 */
#ifndef DAVE_INPUT_MAP_H
#define DAVE_INPUT_MAP_H

#include <stdint.h>
#include "input.h"

enum input_device {      /* g_input_device[player] (DS 0x12F0 + 2 * player) */
    DEVICE_KEYBOARD = 0, DEVICE_MOUSE = 1, DEVICE_JOYSTICK1 = 2, DEVICE_JOYSTICK2 = 3
};

/* Key bindings (g_key_scans, DS 0x1310): scan codes of the 8 direction keys
 * N, NE, E, SE, S, SW, W, NW, then fire and jump/jetpack. Defaults: the
 * cursor/keypad keys 0x48 0x49 0x4D 0x51 0x50 0x4F 0x4B 0x47, Ctrl 0x1D, Alt 0x38. */
enum { BIND_N = 0, BIND_NE, BIND_E, BIND_SE, BIND_S, BIND_SW, BIND_W, BIND_NW, BIND_FIRE, BIND_JUMP,
       BIND_COUNT };

struct input_settings {
    int16_t device;                  /* enum input_device (player 1: the only one read) */
    uint8_t keys[BIND_COUNT];        /* scan codes */
};

/* read_keyboard_input(): dir/fire/jump from a key-state table (1 = down,
 * indexed by scan code 0..127) through the bindings. Straight keys first
 * (N, E, S, W: a later key overrides an earlier one on the same axis), then
 * the diagonal keys NE, NW, SE, SW, each overriding both axes. */
void input_from_keyboard(struct frame_input *in, const uint8_t key_down[128],
                         const struct input_settings *s);

#endif
