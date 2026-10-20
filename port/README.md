# port/ -- the native Dangerous Dave

Plain C11, built with CMake; no DOS, no original machine code, no emulated
memory. Plan: `docs/PORT_ROADMAP.md`; state design: `docs/state-model.md`
(decisions D1-D7); verification: `docs/FIDELITY.md`.

## Layout

| path | layer | may depend on |
|---|---|---|
| `game/` | pure simulation: `struct game` (state.h), immutable `struct resources` (resources.h), per-step `struct frame_output` (output.h: ordered draw commands, sound requests, retrace count) | nothing outside game/ |
| `present/` (later) | original logical presentation: framebuffer per video mode, draw-command interpreter, sound scheduler | game/ |
| `platform/` (later) | SDL3 and headless backends | game/, present/ |
| `tests/bridge/` | TEST-ONLY bridge to original DGROUP snapshots | everything; nothing depends on it |

## Rules for native code

1. **One state model.** All gameplay state lives in `struct game`. Don't add
   parallel globals. A missing field gets added to `state.h` with its
   inventory id, and the bridge mapping (`tests/bridge/dgroup_map.c`) gets a
   row for it.
2. **No original addresses outside `tests/bridge/`.** Game code never sees a
   DS offset, a segment or a far pointer.
3. **Widths are the original's** where observable (int16_t for int, int8_t
   for char ...). Every arithmetic quirk (8-bit wrap, unsigned compare,
   truncating division, 16-bit overflow) is written out at its site with a
   comment naming the ledger item.
4. **Drawing and sound are output, not side effects.** A subsystem that
   draws appends draw commands in the original's call order, with logical
   arguments (sprite = (set, index) into the original tables, D3). It
   requests sounds with `out_sound`. When the original waits for retraces
   inside a call, add the count to `out->retraces`. A new draw op is added to
   `output.h` with the original routine it mirrors.
5. **Readable, not transliterated.** Name things by what they mean; keep the
   original's algorithm and order of effects. Where the order is
   counter-intuitive but observable, keep it and say why.
6. **Verified or it doesn't count.** Every native subsystem is registered in
   `tests/bridge/bridge.c` under the original pipeline name and must pass
   `python tools/native_check.py <name>` on the oracle corpus: the whole
   game-state view after the call is byte-equal to the original's. Add a
   mutation check (a deliberate small change must be caught) and a test in
   `tests/test_native.py`.
7. Every quirk reproduced on purpose is listed in the subsystem's header
   comment with its ledger reference.

## Build

```
python tools/native_check.py identity      # builds build/port with CMake + MinGW gcc
```

## Input model

A step consumes a `struct frame_input` (`game/input.h`): the LOGICAL
input sample -- direction 0..7 / 8 none, fire, jump/jetpack, the waiting
menu key's scan code, and the DOS time of day (D7). It is already decoded
through the user's settings (device, key bindings, calibration), which live
outside `struct game` (D6). Layers:

| layer | role |
|---|---|
| `game/` | consumes `frame_input` only; the attract-demo stream is game logic (process_input reads the demo-bank resource through `game.demo`), not an input |
| `platform/input_map.c` | pure settings decoding: `input_from_keyboard()` = the original `read_keyboard_input` (key table + bindings -> dir/fire/jump) |
| `platform/` backends (later) | real-time device reading (key events, gamepad, mouse) and the one-key BIOS-buffer semantics of `menu_key` |
| `tests/bridge/` | `dgroup_import_input()` rebuilds the sample from an original snapshot: `g_keydown[]` (DS 0x8A32) through `g_key_scans` (DS 0x1310) for the device in `g_input_device[1]` (DS 0x12F2); mouse/joystick state and the BIOS buffer are not in the snapshot |

One `frame_input` is one poll of the original's `get_player_input`. A call
that polls repeatedly (wait_for_input inside handle_death) takes one sample
per poll; until D2 the bridge feeds every poll the call's starting input.
