"""Curated purpose / status / evidence / subsystem / role of every inventory entry.

Status rules (docs/semantic-inventory.md): `understood` = behaviour AND
representation explained with evidence; otherwise `partial`, one of the two
`*_unclear` forms, or `unresolved`. The source-header evidence of each
function and the definition site of each object are added by the generator.

Common evidence:
  EXACT   the function is byte-exact recovered source (tests/test_matching_sources.py,
          tests/test_matching_asm.py), so reading it is reading the original;
  EXP(x)  tools/semantic_experiments.py check `x`, run on the oracle traces of
          tests/oracle/inv_demos.txt / inv_demos_all.txt (the ORIGINAL game);
  LEDGER  docs/UNDERSTANDING_LEDGER.md item.
"""

EXACT_C = "EXACT: tests/test_matching_sources.py (the recovered source is the original's code)"
EXACT_ASM = "EXACT: tests/test_matching_asm.py (TASM 2.0 reproduces the module byte for byte)"
CALLGRAPH = "call edges cross-checked against the binary call graph (inventory check call_graph_vs_binary)"
DEAD = "unreachable: no caller in the sources and absent from the binary call graph from _main"


def EXP(check):
    return f"oracle: tools/semantic_experiments.py `{check}` (tests/oracle/inv_demos*.txt)"


def F(purpose, status, subsystem, *evidence, **kw):
    d = {"purpose": purpose, "status": status, "subsystem": subsystem, "evidence": list(evidence)}
    d.update(kw)
    return d


def D(purpose, status, subsystem, role, *evidence, **kw):
    d = {"purpose": purpose, "status": status, "subsystem": subsystem, "role": role, "evidence": list(evidence)}
    d.update(kw)
    return d


U = "understood"
P = "partial"
BU = "behaviour_understood_representation_unclear"
RU = "representation_understood_behaviour_unclear"
UR = "unresolved"

# ============================================================== C functions
FUNCTIONS = {
    # ---------------------------------------------------------------- DAVE.C
    "main": F("Program entry: one-time init, adapter -> video mode, graphics, then the outer title/game loop "
              "running the 13-call per-tick pipeline until g_game_over, the high-score check, and exit.",
              U, "main_loop", EXACT_C, CALLGRAPH, "docs/FIDELITY.md section 1 (tick = one pass of the inner loop)"),
    "quit_game": F("Restore INT 9 and INT 8/PIT, return to text mode when the code is 0, exit(code).",
                   U, "main_loop", EXACT_C),
    "check_high_score": F("End of a game: insert the score into the 5-entry table (both the file image and the "
                          "in-memory copy), read initials, write DSCORES.DAV; otherwise show 'Game Over' while "
                          "monsters/shots/explosions keep animating for up to 1000 retraces or a key/fire.",
                          U, "high_scores", EXACT_C,
                          quirks=["the in-memory entry keeps the score as 16-bit unsigned (init_game_once decodes "
                                  "the 5 digits in int arithmetic), so a stored score >= 65536 compares as "
                                  "score - 65536 (U-M1 list item 'high-score width')",
                                  "reached after any g_game_over that is not a quit, so a demo that lost all "
                                  "lives would also be scored (no shipped demo does)"]),
    "input_initials": F("Read up to 3 initials (' '..'Z', upper-cased, echoed) with Backspace/Left editing until "
                        "Enter.", U, "high_scores", EXACT_C),
    "show_high_scores": F("Draw the high-score table from the DSCORES.DAV image: 5 digit score, initials, level "
                          "(10 -> '10', 11 -> 'won'); with sound 11 then sound 6 per row and WaitSound pacing "
                          "when the argument is non-zero.", U, "high_scores", EXACT_C,
                          "sound names from the SPK directory (tools/sounds.py): 11 ToJetpack, 6 Treasure"),
    "attract_mode": F("Head of every tick: in mode 2 show the high scores (<= 1000 retraces), in mode 3 animate "
                      "the title (200 x 6 retraces); a key or fire starts a game (mode 0), a timeout starts a "
                      "demo picked by srand(time); rand() * count / 32767 (mode 1). Modes 0/1: nothing.",
                      P, "attract_demos", EXACT_C, "LEDGER U-S1 (closed), U-T3 (closed)",
                      note="the title animation counter j is an uninitialised stack word: its starting value "
                           "(the phase of the two animated title tiles) is not determined yet (U-R5)",
                      quirks=["the title animation counter j is an uninitialised stack word (presentation only)",
                              "rand() == 32767 selects demo index 5 = offsets[5], i.e. the first two bytes of "
                              "demo 0 (0x2002): a garbage demo outside the segment (U-M1 list)"]),
    "draw_inventory": F("Draw the status-bar inventory: jetpack meter + icon, gun icon, 'go thru the door' note "
                        "when the trophy is held, then score and level number.", U, "status_bar", EXACT_C),
    "update_score": F("Extra life every 20000 points (only while lives < 3; the goal is rounded down to a "
                      "multiple of 20000), cap the score at 99999, draw the 5 score digits. Game logic and "
                      "drawing mixed.", U, "status_bar", EXACT_C, "docs/external-re-evidence.md (0x4E20, 0x1869F)",
                      note="the extra-life rule is gameplay (lives, next goal) and must move to port/game; the "
                           "digit drawing to port/present"),
    "draw_level_number": F("Draw the 1-based level number as two digit tiles.", U, "status_bar", EXACT_C),
    "ask_restart": F("F3: 'Restart Game? (Y or N)'; Y (not on the title) restores the live tile map from the "
                     "backup and returns to the title (mode 3); otherwise redraw and resume the sound.",
                     U, "menus", EXACT_C),
    "show_help": F("F1: three help pages (Space next, Esc leave), then redraw.", U, "menus", EXACT_C),
    "ask_quit": F("F10/Esc: 'Quit? (Y or N)'; Y exits through quit_game(0), N redraws.", U, "menus", EXACT_C),
    "pause_game": F("F9: pause until F9 is pressed again, then re-set the video mode and redraw.", U, "menus",
                    EXACT_C),
    "load_graphics": F("Per video mode: picfile pointers (setup_graphics_pointers) and the tileset into the work "
                       "buffer (RLE-expanded from the EXE for CGA/VGA, EGADAVE.DAV for EGA); g_gfx_index = "
                       "mode - 1.", U, "resources", EXACT_C, "tools/tilesets.py, tools/egadave_decode.py"),
    "redraw_screen": F("Full repaint for the current mode: in modes 0-2 view borders, status bar, inventory, level "
                       "view, Dave's front sprite and the monsters' frame-0 sprite ids, actors (and the score "
                       "table in mode 2); in mode 3 the credits and the DAVE tile logo.", U, "rendering", EXACT_C,
                       note="resets g_dave_sprite/g_dave_mask and g_monsters.sprite: presentation fields that "
                            "the snapshot comparison sees"),
    "show_cga_picture": F("Dead code: set CGA mode 4, copy 16 KB to B800:0 from an uninitialised far pointer, "
                          "wait for a key.", U, "rendering", EXACT_C, DEAD),
    "handle_death": F("While Dave is not alive: count the death timer down (armed to 300 by Dave's explosion); "
                      "then remove a life icon; below 0 lives end the game (restore the live map, g_game_over); "
                      "otherwise respawn at the level start (or the warp-zone start), clear shots and actors, "
                      "redraw and wait for input.", U, "death_restart", EXACT_C, EXP("dave_state transitions"),
                      quirks=["if Dave is 'not alive' without an armed timer (level -1 after a warp, U-M1), "
                              "--g_bonus_timer runs from 0 through -1 and needs 65536 ticks to reach 0",
                              "the gun, the jetpack and its fuel survive a death (only load_level drops them)"]),
    "update_jetpack": F("While flying (state bit 0x01): every 15 ticks burn one fuel unit and erase one meter "
                        "segment; at 0 fuel drop the jetpack, start falling (state & 0xE0 | 0x08), sound 2.",
                        U, "player", EXACT_C, EXP("dave_state transitions")),
    "spawn_explosion": F("Start an explosion actor in the first free of 6 slots (life 110 ticks, 13-tick frames, "
                         "first frame drawn); type 5 (Dave's own explosion) arms the 300-tick death timer.",
                         U, "monsters_shots_explosions", EXACT_C, EXP("actor bytes 14..0x139 never change"),
                         note="the name was tentative (U-G7): sprite set 0 is the explosion animation used for "
                              "both Dave (type 5) and monsters (type i+1); the type is stored but never read"),
    "update_explosions": F("Age the explosion actors: XOR-erase, advance the 4-frame animation every 13 ticks, "
                           "fall 2 px on each frame step while nothing solid is below (probes x+4/x+14 at y+14) "
                           "and y < 0x98, redraw; erase and free at the end of life.",
                           U, "monsters_shots_explosions", EXACT_C),
    "restore_background": F("Dead per-mode dispatch to RestoreUnder*.", U, "rendering", EXACT_C, DEAD),
    "save_background": F("Dead per-mode dispatch to SaveUnder*.", U, "rendering", EXACT_C, DEAD),
    "draw_masked_sprite": F("Per-mode dispatch to DrawMasked* (help-screen sprites).", U, "rendering", EXACT_C),
    "draw_tile": F("Per-mode dispatch to the opaque picture blitters DrawPic* (score/level digits, title tile).",
                   U, "rendering", EXACT_C),
    "xor_sprite": F("Per-mode dispatch to the XOR blitters DrawXor*: draws and, called again, erases monsters, "
                    "shots, explosions and status icons.", U, "rendering", EXACT_C,
                    note="XOR drawing makes the framebuffer itself stateful: frame equivalence needs the same "
                         "draw/erase sequence, not just the same game state (docs/state-model.md)"),
    "erase_dave": F("Restore the screen saved under Dave (g_dave_background).", U, "rendering", EXACT_C),
    "draw_dave": F("Save the screen under Dave's mask into g_dave_background, then masked-draw his sprite.",
                   U, "rendering", EXACT_C),
    "move_dave": F("Dave's per-tick movement state machine: throttle, then by priority walk (0x04) / fall (0x08) "
                   "/ jump (0x10) / climb (0x02) / jetpack (0x01) / killed (0x40) with tile probes, sounds, "
                   "sprite choice, scrolling; ends with the tick's WaitVBL around the erase/redraw of Dave.",
                   U, "player", EXACT_C, CALLGRAPH, EXP("dave_state transitions"),
                   EXP("movement throttle (g_death_pause)"), EXP("jump steps follow g_jump_dy, y kept to 8 bits"),
                   "LEDGER U-G1, U-G2 (closed)",
                   quirks=["several movement bits can be set at once (jump -> climb at the apex step sets 0x02 "
                           "and 0x08); the branch order 0x04, 0x08, 0x10, 0x02, 0x01 then decides",
                           "player y is reduced modulo 256 by every jump/fall step (y = (y + t) & 0xff): "
                           "jumping above the top row wraps y to 240..255 (observed in the level-3 demo)",
                           "the WaitVBL that paces the game is inside this function (every path calls it once)"]),
    "animate_tick": F("Climbing animation: every 2nd call advance g_anim_frame and select the climbing "
                      "sprite/mask (g_sprite_sets[7]/[8]).", U, "player", EXACT_C,
                      note="only caller is move_dave's climbing branch; better name: animate_climb"),
    "tile_attr_at": F("Collision attribute (0 free, 1 solid, 2 deadly) of the level tile under Dave + (x, y); "
                      "0 above the grid or below row 9.", U, "collisions_items_tiles", EXACT_C,
                      quirks=["the column is not range-checked: (x + player_x) / 16 + scroll_x can be 100 at "
                              "the right edge and then reads the next row's first tile (U-M1 list)",
                              "tile bytes are signed char: a byte >= 0x80 indexes g_tile_attr negatively "
                              "(only in the level -1 map)"]),
    "tile_at": F("Tile id under Dave + (x, y); 0 above the grid or below row 11 (rows 10/11 read past the "
                 "1000-byte map).", U, "collisions_items_tiles", EXACT_C, quirks=["rows 10 and 11 (U-M1 list)"]),
    "tile_attr_at_offset": F("Collision attribute of the tile at pixel (x + dx, y + dy) of the view; no range "
                             "checks (shots, explosions, shot spawning).", U, "collisions_items_tiles", EXACT_C,
                             quirks=["off-screen monster shots probe columns < scroll_x or > scroll_x + 19 and "
                                     "may leave the row (U-M1 list)"]),
    "move_monsters": F("Every 5 ticks per active monster: XOR-erase, step along the level path ((dx, dy) bytes, "
                       "0xEA restarts), recompute the sprite id, redraw, animate every 2nd step; fire a shot "
                       "towards Dave when on/near screen (0 <= x < 0x154), no own shot alive, the reload count "
                       "expired and Dave alive.", U, "monsters_shots_explosions", EXACT_C,
                       EXP("monster records step along the level path every 5 ticks"), "LEDGER U-G5 (closed)"),
    "move_bullets": F("Move every active shot 2 px per tick in its direction; a solid tile ahead (x-2 or x+16, "
                      "y+1) erases and frees it; Dave's shot (kind 1) is dropped off-screen, monster shots fly "
                      "on; one countdown shared by all shots advances their frames.",
                      U, "monsters_shots_explosions", EXACT_C, EXP("shot record value sets"),
                      "LEDGER U-G6 (closed)",
                      quirks=["the 3-tick frame countdown g_shot_anim_count is decremented once per active "
                              "shot, so frame timing depends on how many shots are alive",
                              "monster shots that leave the screen keep flying (and keep their owner from "
                              "firing) until they hit a solid tile"]),
    "draw_object": F("XOR-draw shot i: monster shots animated (sets 2 left / 1 right), Dave's shot static "
                     "(g_spr_shot_b0 / _b1).", U, "monsters_shots_explosions", EXACT_C),
    "animate_tiles": F("Every 10 ticks advance each active animated tile (wrap after `count` frames) and redraw "
                       "it when its column is in the view.", U, "collisions_items_tiles", EXACT_C,
                       EXP("g_anim_tick_divider counts 10..1")),
    "wait_for_input": F("Blink Dave (erase, 10 retraces, draw, 10 retraces, tiles animating) until a direction "
                        "or key; sound 2 if he is falling.", U, "levels_warps", EXACT_C,
                        note="20 retraces per blink, all inside one tick of the pipeline"),
    "check_warp_transition": F("Dave above the top row at the far left (view 0, x < 2) or far right (view 80, "
                               "x > 0x132): bounce back inside a warp zone or a level whose warp was used; "
                               "otherwise the tube sequence, restore the live map, mark the level, remember it, "
                               "load the target level (table value - 1) and place Dave there.",
                               U, "levels_warps", EXACT_C, "docs/external-re-evidence.md EXT_WARP_TRANSITION",
                               "LEDGER U-M1 (closed)",
                               quirks=["levels whose warp target is 0 (1-based 1, 2, 3, 4, 6, 7) load level -1: "
                                       "the record before g_levels (DS 0x123A), see U-M1 and U-M3"]),
    "draw_status_meter": F("XOR the jetpack meter frame and g_jetpack_fuel bar segments.", U, "status_bar",
                           EXACT_C),
    "draw_status_bar": F("XOR the three status labels and one icon per remaining life.", U, "status_bar", EXACT_C),
    "check_collisions": F("Three passes: Dave touching a visible monster (from level 3: both explode, state & "
                          "0xC0, sound 8); Dave's shot hitting a monster (monster explodes, +100 x level "
                          "number); a monster shot hitting Dave (state 0x40, explosion). Box tests use unsigned "
                          "differences.", U, "collisions_items_tiles", EXACT_C, EXP("dave_state transitions"),
                          quirks=["`i = 4` ends a pass after its first hit",
                                  "pass 2 is not limited to level >= 3; levels 1-2 simply have no monsters"]),
    "level_complete": F("After the door with the trophy: the corridor interlude (message unless returning from "
                        "a warp zone, Dave walks across), advance (or return from the warp zone), load the next "
                        "level; after level 10 the ending text with a light chasing round the border until "
                        "Space, then game over.", U, "levels_warps", EXACT_C, "LEDGER U-G8 (closed)",
                        quirks=["border path: 55 positions; entry 47 is written twice, so the bottom-left "
                                "corner (0, 9) is never lit"]),
    "pick_up_items": F("For the 2x2 tiles under Dave (alive, 16 < y < 0xA6): collect items (score, sound 6, "
                       "remove from the live map and the screen); trophy (sound 7, stop its animation), door "
                       "(only with the trophy: level done), gun, jetpack (fuel 60).", U, "collisions_items_tiles",
                       EXACT_C, CALLGRAPH, note="the PICK macro is expanded 4 times in the original"),
    "scroll_screen": F("When Dave passes x > 0x118 (view < 80) or x < 0x20 (view > 0) scroll 15 columns, one "
                       "per retrace: view column +-1, every entity x -+16, redraw the view and actors.",
                       U, "player", EXACT_C, note="15 retraces inside one tick"),
    "find_object": F("Index of the active shot with owner id, or -1.", U, "monsters_shots_explosions", EXACT_C),
    "object_exists": F("1 if an active shot with owner id exists.", U, "monsters_shots_explosions", EXACT_C),
    "spawn_object": F("Spawn a shot (owner id, direction, kind) in the first free slot unless the tile at "
                      "(x, y+1) is solid; draw it once.", U, "monsters_shots_explosions", EXACT_C),
    "handle_menu_key": F("Peek the BIOS key: F1 help, F2 control panel, F3 restart, F9 pause, F10/Esc quit; any "
                         "other key during a demo restores the map and starts a new game.", U, "menus", EXACT_C),
    "process_input": F("Per-tick input: in demo mode substitute the recorded stream; map the direction; fire / "
                       "jetpack buttons act on release or every 30 ticks while held; (dead) demo recording; "
                       "fire Dave's shot (gun, none alive, 8 < y < 0xAA); toggle the jetpack; menu keys.",
                       U, "input", EXACT_C, CALLGRAPH, EXP("dave_state transitions"),
                       quirks=["a button triggers when released (counter != 30 and button up -> 0) or after "
                               "30 held ticks; a release while Dave is dead triggers on the first alive tick",
                               "on the tick that reads a ' ' (0x20) run marker or the '0' end marker the live "
                               "device input passes through unchanged",
                               "the recording branch is dead: g_demo_recording is never set"]),
    "draw_actors": F("Redraw all sprites after a full view redraw: Dave (if alive and below row 0), monsters, "
                     "shots, explosions.", U, "rendering", EXACT_C),
    "load_level": F("Set up level g_current_level: srand(100); Dave's start state/position; live map pointer "
                    "into g_levels; clear actors/shots; build the animated-tile list (random phase); copy the "
                    "monster block (random frame); path pointer; backup copy of the map; view 0; drop gun, "
                    "jetpack and trophy.", U, "levels_warps", EXACT_C,
                    EXP("rand seed after load_level == LCG^(anim tiles + 4)(100)"), "tools/levels.py",
                    quirks=["the map is modified IN PLACE in g_levels (pickups) and restored from g_tiles when "
                            "the level is left; returning from a warp zone reloads a restored map"]),
    "init_game_once": F("Start-up: 0x16000-byte work buffer, level pointer, sound driver, keyboard ISR, demo "
                        "bank pointer, load (or create with 5 x 'JON 00100') DSCORES.DAV, init the game state, "
                        "decode the 5 entries.", U, "main_loop", EXACT_C, "docs/data-layout.md"),
    "init_game_state": F("New game: clear warp-used flags, 3 lives, score 0, next extra life 0, not game over, "
                         "level 0, view 0, tile animation divider 10, not in a warp zone; re-set the video mode.",
                         U, "main_loop", EXACT_C, "docs/external-re-evidence.md EXT_INIT_FUNCTION"),
    # -------------------------------------------------------------- CONFIG.C
    "calibrate_joystick": F("Joystick set-up screen: sample the upper-left and lower-right corners on fire, set "
                            "the thresholds a quarter of the range inside; Esc (g_keydown[1]) aborts.",
                            U, "config_panel", EXACT_C),
    "config_mouse": F("Mouse set-up screen: sensitivity 1..9 (Esc = 5) -> g_mouse_deadzone = 15 - n; reset and "
                      "centre the mouse.", U, "config_panel", EXACT_C),
    "print_key_name": F("Print a scan code's name (ESC, F1..F10, F11, 'F12' for 0x59, ...) or its character.",
                        U, "config_panel", EXACT_C),
    "config_keyboard": F("Keyboard set-up screen: choose an action 0..9, press the new key, store its scan code "
                         "in g_key_scans.", U, "config_panel", EXACT_C),
    "detect_hardware": F("Fill the control panel's availability grid: EGA/VGA from the adapter type, joysticks "
                         "by a port-201h probe, a mouse driver by the INT 33h vector.", U, "config_panel", EXACT_C,
                         quirks=["a second joystick sets g_have_joystick = 2, never g_have_joystick2",
                                 "g_panel_avail[0][5..9] are written through row 0 and land in row 1 (sound)"]),
    "draw_control_panel": F("Draw the 'PC-Arcade Control Panel' screen: option icons (greyed when unavailable), "
                            "current-choice markers, help lines.", U, "config_panel", EXACT_C),
    "control_panel": F("F2 control panel: arrow keys move over available options, Enter applies (video mode "
                       "switch reloads the graphics, sound on/off, input device + its set-up screen), Esc stores "
                       "the choices and redraws.", U, "config_panel", EXACT_C,
                       quirks=["player 2's device (g_input_device[2]) is only saved and restored"]),
    "setup_graphics_pointers": F("From a picfile header derive the font/tile/picture/sprite pointers (EGA: VRAM "
                                 "addresses + plane segments) and copy its picture and sprite tables.",
                                 U, "resources", EXACT_C, "tools/picfiles.py"),
    "ega_upload_planes": F("Copy the EGA picfile planes into latched video memory at A200:0000, one plane at a "
                           "time through the sequencer map mask.", P, "video_hardware", EXACT_C,
                           note="not yet observed: the oracle captures VGA only (PORT_ROADMAP M1.4)"),
    # ------------------------------------------------------------ HARDWARE.C
    "install_keyboard_handler": F("Clear the key table, flush the BIOS buffer, hook INT 9 with keyboard_isr "
                                  "(once).", U, "input", EXACT_C),
    "keyboard_isr": F("INT 9: make code sets g_keydown[scan] = 1 and empties the BIOS buffer, break code clears "
                      "it; then chain to the BIOS handler (which buffers the key) and acknowledge the PIC.",
                      U, "input", EXACT_C, note="so bioskey() sees at most the latest key"),
    "restore_keyboard_handler": F("Restore the saved INT 9 vector (the guard tests the variable's address, "
                                  "always true).", U, "input", EXACT_C),
    "read_keyboard_input": F("Input from the key table: direction 0..7 clockwise from north (8 none) from the 8 "
                             "bound keys, diagonal keys overriding; fire and jump from keys 8 and 9.",
                             U, "input", EXACT_C, "tools/demos.py (direction codes)"),
    "read_mouse_input": F("Input from the mouse: direction from the cursor's offset from (320, 100) beyond the "
                          "dead zone, partly re-centred; left button fire, right button jump (jetpack).",
                          U, "input", EXACT_C),
    "read_joystick_axes": F("Time the game-port one-shots of stick 1 or 2 with interrupts off (cap 500).",
                            U, "input", EXACT_C),
    "read_joystick_input": F("Input from a joystick: axis counts against the calibrated thresholds, buttons "
                             "active low.", U, "input", EXACT_C),
    "get_player_input": F("Read the device chosen for the player (keyboard, mouse, joystick 1/2); the "
                          "recording/playback branches of the input recorder are dead (g_demo_state stays 0).",
                          U, "input", EXACT_C, "LEDGER N-1",
                          quirks=["(dead) playback sets both fire and jump from bit 0"]),
    "demo_record_start": F("Dead: start the input recorder (g_demo_state = 2).", U, "attract_demos", EXACT_C, DEAD),
    "demo_play_start": F("Dead: load a recorder file and start playback (g_demo_state = 1).", U, "attract_demos",
                         EXACT_C, DEAD),
    "demo_save": F("Dead: write the recorder buffer to a file, stop recording.", U, "attract_demos", EXACT_C, DEAD),
    "flush_keyboard": F("Drain the BIOS key buffer and clear the key table.", U, "input", EXACT_C),
    "farmalloc_aligned": F("farmalloc(size + 15) rounded up to a paragraph; prints 'Out of memory!' and exits "
                           "on failure.", U, "resources", EXACT_C),
    "read_file_far": F("Read a whole file into a far buffer with DOS calls (0xFFFF-byte chunks); returns its "
                       "size, 0 if it cannot be opened.", U, "resources", EXACT_C),
    "write_file_far": F("Create a file and write len bytes from a far buffer (0x8000-byte chunks).",
                        U, "resources", EXACT_C),
    "load_file": F("Dead: allocate and read a whole file.", U, "resources", EXACT_C, DEAD),
    "load_rle_file": F("Dead: read an RLE file (u32 size + stream) and expand it.", U, "resources", EXACT_C, DEAD),
    "set_video_mode": F("BIOS mode 0 -> text 3, 1 -> CGA 4, 2 -> EGA 0Dh (+ plane upload), 3 -> VGA 13h (+ the "
                        "256-colour DAC palette).", U, "video_hardware", EXACT_C),
    "draw_text_window": F("Draw a framed text window (font chars 1..8), remember it, put the cursor inside.",
                          U, "text_windows", EXACT_C),
    "clear_text_window": F("Fill the remembered window with spaces.", U, "text_windows", EXACT_C),
    "draw_centered_window": F("Draw a w x h window centred on the 40 x 25 text grid.", U, "text_windows", EXACT_C),
    "open_window_anim": F("Dead: zoom a window open.", U, "text_windows", EXACT_C, DEAD),
    "open_window_anim_w": F("Dead: zoom helper (width).", U, "text_windows", EXACT_C, DEAD),
    "open_window_anim_h": F("Dead: zoom helper (height).", U, "text_windows", EXACT_C, DEAD),
    "wait_key_cursor": F("Animate a cursor (chars 9..12, 5 retraces each) until a key; return bioskey(0).",
                         U, "text_windows", EXACT_C),
    "print_string": F("Print a string at the text cursor ('\\n' next line at the left margin, '\\r' to the "
                      "margin).", U, "text_windows", EXACT_C),
    "print_int": F("Dead: print an int.", U, "text_windows", EXACT_C, DEAD),
    "print_long": F("Dead: print a 'long' (passes one word to ltoa).", U, "text_windows", EXACT_C, DEAD),
}

# ======================================================== assembly procedures
_SND = "tools/sounds.py (SPK directory: rates 5..25, priorities 0..20 for sounds 1..12)"
FUNCTIONS.update({
    "StartSound": F("Hook INT 8 once (saving the old vector) and enable the speaker output flag.",
                    U, "sound", EXACT_ASM, "LEDGER U-S2 (closed)"),
    "ShutdownSound": F("PIT channel 0 back to 18.2 Hz, unhook INT 8, speaker off.", U, "sound", EXACT_ASM),
    "PlaySound": F("Request sound n: ignored if its priority is below the playing one; else set the tone "
                   "pointer, the tick multiplier m and PIT channel 0 to 65536/m (18.2*m Hz).",
                   U, "sound", EXACT_ASM, _SND, "LEDGER U-S2 (closed)",
                   quirks=["m <= 1 would leave TimerRate stale (Pause/Resume would restore a stale rate); "
                           "unreachable: every game sound has m >= 5"]),
    "StopSound": F("Silence: tone pointer 0, priority 0, PIT channel 0 at 18.2 Hz, speaker off.",
                   U, "sound", EXACT_ASM),
    "PauseSound": F("Save the driver state (pointer, priority, multiplier, count, rate) and stop.",
                    U, "sound", EXACT_ASM),
    "ResumeSound": F("Restore the saved driver state and the PIT rate.", U, "sound", EXACT_ASM),
    "WaitSound": F("Run one driver tick by hand, then busy-wait until the current sound has ended.",
                   U, "sound", EXACT_ASM, note="waits on the asynchronous PIT clock (real time, not retraces)"),
    "Int8ISR": F("INT 8 handler: EOI, chain the BIOS handler every m-th tick, then output the next tone word "
                 "(divisor on PIT channel 2 + speaker on; 0 = rest; 0xFFFF = end -> StopSound).",
                 U, "sound", EXACT_ASM, "docs/FIDELITY.md (sound is asynchronous)"),
    "InitRnd": F("Dead: seed the additive lagged-Fibonacci generator (fixed or from the DOS time).",
                 U, "rng", EXACT_ASM, DEAD, "LEDGER U-S1 (closed)"),
    "Random": F("Dead: lagged-Fibonacci (lags 17/5) random number 0..max.", U, "rng", EXACT_ASM, DEAD,
                "LEDGER U-S1 (closed)"),
    "WaitVBL": F("Wait for the start of the next vertical retrace (port 3DAh bit 3): the game's clock.",
                 U, "video_hardware", EXACT_ASM, "docs/FIDELITY.md (70.086 Hz in VGA)",
                 note="EGA/CGA refresh rates: U-T2"),
    "EGASelectPlane": F("Dead: EGA write mode 0, one plane for read and write.", U, "video_hardware", EXACT_ASM, DEAD),
    "EGALatchMode": F("Dead: EGA write mode 1 (latch copy), all planes.", U, "video_hardware", EXACT_ASM, DEAD),
    "DrawChar": F("Draw 8x8 font character c at text cell (x, y) in the current mode, XORed with XorMask.",
                  U, "text_windows", EXACT_ASM),
    "DrawCharCGA": F("CGA font character (16 bytes, interleaved banks).", P, "text_windows", EXACT_ASM,
                     note="CGA output not captured by the oracle yet (M1.4)"),
    "DrawCharEGA": F("EGA font character: the 1bpp glyph written to each plane.", P, "text_windows", EXACT_ASM,
                     note="EGA output not captured by the oracle yet (M1.4)"),
    "DrawCharVGA": F("VGA font character (64 bytes, 8bpp).", U, "text_windows", EXACT_ASM),
    "DrawPic": F("Copy control-panel picture n from the picfile to pixel (x, y) through its size table.",
                 U, "config_panel", EXACT_ASM, "tools/picfiles.py"),
    "BlitPicCGA": F("Opaque picture copy, CGA.", P, "config_panel", EXACT_ASM, note="CGA not captured (M1.4)"),
    "BlitPicEGA": F("Picture copy VRAM to VRAM through the EGA latches.", P, "config_panel", EXACT_ASM,
                    note="EGA not captured (M1.4)"),
    "BlitPicVGA": F("Opaque picture copy, VGA.", U, "config_panel", EXACT_ASM),
    "VideoID": F("Richard Wilton's VIDEO_ID: probe PS/2 BIOS, EGA BIOS, CGA and MDA/Hercules CRTCs; return the "
                 "active adapter type (1 MDA, 2 CGA, 3 EGA, 4 MCGA, 5 VGA, 0x80+ Hercules).",
                 U, "video_hardware", EXACT_ASM, "Wilton, Programmer's Guide to PC & PS/2 Video Systems"),
    "FindPS2": F("VIDEO_ID test: INT 10h AX=1A00h display combination.", U, "video_hardware", EXACT_ASM),
    "FindEGA": F("VIDEO_ID test: INT 10h AH=12h EGA information.", U, "video_hardware", EXACT_ASM),
    "FindCGA": F("VIDEO_ID test: a 6845 at 3D4h.", U, "video_hardware", EXACT_ASM),
    "FindMono": F("VIDEO_ID test: a 6845 at 3B4h, MDA vs Hercules variants.", U, "video_hardware", EXACT_ASM),
    "Find6845": F("VIDEO_ID helper: does a CRTC answer at port DX.", U, "video_hardware", EXACT_ASM),
    "FindActive": F("VIDEO_ID helper: make the active subsystem Device0.", U, "video_hardware", EXACT_ASM),
    "FoundDevice": F("VIDEO_ID helper: record a found subsystem.", U, "video_hardware", EXACT_ASM),
    "RLECompress": F("Dead in the game: the RLE compressor that produced the in-EXE tilesets.",
                     U, "resources", EXACT_ASM, DEAD, "tools/rle.py (exact port reproduces both streams)"),
    "RLEExpand": F("Expand an RLE stream (code < 0x80: run of code+3; >= 0x80: code-0x7F literals) into a far "
                   "buffer until len bytes.", U, "resources", EXACT_ASM, "tools/rle.py, tests/test_tilesets_roundtrip.py"),
    "RleSetup": F("RLE helper: reset run/literal/output counters.", U, "resources", EXACT_ASM),
    "WriteRun": F("Dead (compressor): emit the pending run.", U, "resources", EXACT_ASM, DEAD),
    "WriteLiterals": F("Dead (compressor): emit the pending literals.", U, "resources", EXACT_ASM, DEAD),
    "RleExpandCore": F("RLE decoder loop with far-pointer renormalisation at offset 0xFF00.",
                       U, "resources", EXACT_ASM, "tools/rle.py"),
    "RleCompressCore": F("Dead (compressor) main loop; over-reads its source (docs D-1).", U, "resources",
                         EXACT_ASM, DEAD, "tools/rle.py"),
    "FlushRle": F("Dead (compressor): emit whatever is pending.", U, "resources", EXACT_ASM, DEAD),
    "PrintDosString": F("Dead: DOS print of a '$' string (probably for TileErrMsg).", U, "resources", EXACT_ASM, DEAD),
    "InitLevelPtr": F("LevelPtr = DGROUP:g_levels.", U, "levels_warps", EXACT_ASM),
    "DrawMaskedEGA": F("EGA masked sprite: screen = (screen AND mask) OR sprite per plane, pre-shifted copy for "
                       "x & 6, clipped to playfield lines 13..165.", P, "rendering", EXACT_ASM,
                       note="EGA not captured (M1.4)"),
    "RestoreUnderEGA": F("EGA: put back the background saved by SaveUnderEGA under its mask.", P, "rendering",
                         EXACT_ASM, note="EGA not captured (M1.4)"),
    "SaveUnderEGA": F("EGA: save the screen AND NOT mask plus the mask into a buffer {x, y*2, width, height, "
                      "mask size, mask, background}.", P, "rendering", EXACT_ASM, note="EGA not captured (M1.4)"),
    "DrawMaskedVGA": F("VGA masked sprite: screen = (screen AND mask) OR sprite, clipped to lines 13..165.",
                       U, "rendering", EXACT_ASM, "oracle VGA framebuffer per tick (docs/FIDELITY.md)"),
    "RestoreUnderVGA": F("VGA: screen = (screen AND mask) OR saved background.", U, "rendering", EXACT_ASM),
    "SaveUnderVGA": F("VGA: save header, mask and (screen AND NOT mask) into the buffer.", U, "rendering",
                      EXACT_ASM, note="unclipped vertically (Dave above the playfield saves lines < 13)"),
    "DrawMaskedCGA": F("CGA masked sprite (pre-shifted copy for x & 2).", P, "rendering", EXACT_ASM,
                       note="CGA not captured (M1.4); sprite tails U-R3"),
    "RestoreUnderCGA": F("CGA restore-under.", P, "rendering", EXACT_ASM, note="CGA not captured (M1.4)"),
    "SaveUnderCGA": F("CGA save-under.", P, "rendering", EXACT_ASM, note="CGA not captured (M1.4)"),
    "DrawXorEGA": F("EGA XOR blit of any resource, horizontally clipped.", P, "rendering", EXACT_ASM,
                    note="EGA not captured (M1.4)"),
    "DrawPicEGA": F("EGA opaque blit of any resource, unclipped.", P, "rendering", EXACT_ASM,
                    note="EGA not captured (M1.4)"),
    "DrawXorVGA": F("VGA XOR blit of any resource, horizontally clipped; nothing if y >= 200.", U, "rendering",
                    EXACT_ASM),
    "DrawPicVGA": F("VGA opaque blit of any resource.", U, "rendering", EXACT_ASM),
    "DrawXorCGA": F("CGA XOR blit, horizontally clipped.", P, "rendering", EXACT_ASM, note="CGA not captured (M1.4)"),
    "DrawPicCGA": F("CGA opaque blit.", P, "rendering", EXACT_ASM, note="CGA not captured (M1.4)"),
    "DrawLevelView": F("Draw the 20 x 9.5-tile playfield from line 16, reading the tiles of level "
                       "g_current_level directly from g_levels (LevelOfs) at view column g_scroll_x.",
                       U, "rendering", EXACT_ASM, "LEDGER U-M1 (closed)",
                       quirks=["reads g_levels by level number, not through g_level: for level -1 it shows "
                               "LevelOfs[-1] = 0x2421 bytes past g_levels+0x100 (level 8's map from row 2 "
                               "col 89), a different map from the one collisions use"]),
    "DrawViewBorders": F("Draw the lines above (12-13) and below (167-168) the playfield.", U, "rendering",
                         EXACT_ASM),
    "VgaBarLine": F("One 320-pixel VGA border line from BarPattern.", U, "rendering", EXACT_ASM),
    "DrawTile": F("Draw tile t at view cell (x, y) (row 9 = the half row).", U, "rendering", EXACT_ASM),
    "DrawTileAt": F("Tile blit per mode (EGA from the A800 latch cache).", P, "rendering", EXACT_ASM,
                    note="EGA/CGA paths not captured (M1.4); U-R2"),
    "CacheEGATiles": F("Copy the 53 tiles into EGA memory at A800:0000 for latched copies.", P, "rendering",
                       EXACT_ASM, note="U-R2; EGA not captured (M1.4)"),
})

# ============================================================== data objects
_LV = "docs/data-layout.md section 2; tools/levels.py"
DATA = {
    # ---------------------------------------------------------- runtime areas
    "c0s_data": D("C0S _DATA: null-check area, copyright, runtime variables (___brklvl, heap pointers, ...).",
                  U, "runtime", "runtime", "docs/data-layout.md"),
    "cslib_data": D("CS.LIB _DATA (ctype table, streams, heap, TIMECVT, ...) before the rand seed.",
                    U, "runtime", "runtime", "docs/data-layout.md"),
    "rand_seed": D("Borland rand() state: Seed = Seed * 0x015A4E35 + 1, rand() = (Seed >> 16) & 0x7FFF; "
                   "srand(s) sets it to s.", U, "rng", "game_state",
                   EXP("rand seed after load_level == LCG^(anim tiles + 4)(100)"), "LEDGER U-S1 (closed)",
                   width="uint32", note="observable: load_level's random tile phases and monster frames, the "
                                        "attract demo choice"),
    "cslib_data_2": D("CS.LIB _DATA after the rand seed (stack length, TZ, near heap, environ).", U, "runtime",
                      "runtime", "docs/data-layout.md"),
    "cslib_bss_and_stack": D("CS.LIB _BSS (atexit table) and the start of the stack, inside the oracle's "
                             "DGROUP dump.", U, "runtime", "runtime", "docs/bss-map.md"),
    # --------------------------------------------------------- DAVE.C _DATA
    "g_demo_recording": D("Never set: would enable process_input's demo recorder (always 0).", U, "attract_demos",
                          "layout_artifact", "relations: no writer", note="dead feature flag"),
    "g_demo_mode": D("Game mode: 0 playing, 1 demo, 2 high-score screen, 3 title (the name is historical; "
                     "native name: game mode).", U, "main_loop", "game_state", "LEDGER N-1", "oracle FIELDS game_state",
                     width="int16 (values 0..3)"),
    "g_fire_repeat": D("Fire button counter: 30 idle, counts down while held, 0 = trigger now (then 30).",
                       U, "input", "game_state", width="int8 (signed char)"),
    "g_jetpack_repeat": D("Jetpack button counter, same scheme as g_fire_repeat.", U, "input", "game_state",
                          width="int8 (signed char)"),
    "g_hiscore_file": D("File name 'DSCORES.DAV'.", U, "high_scores", "resource_buffer"),
    "g_jump_dy": D("Jump y steps: [0] 0, -3, 11 x -2, 7 x -1, 7 x 0, 7 x +1, 10 x +2, +3, then 0x80 = end "
                   "(fall); rise 32 px (2 tiles), fall 30 px within the jump; [46] never read.",
                   U, "player", "game_constant", EXP("jump steps follow g_jump_dy, y kept to 8 bits"),
                   "LEDGER U-G2 (closed)"),
    "g_level_flags": D("Initial g_dave_state per level: 0x24 alive+walking, 0x28 alive+falling (1-based levels "
                       "4, 7, 9). Was 'DS 0x0118 per-level option byte' (U-G3).", U, "levels_warps",
                       "game_constant", "load_level, handle_death", "LEDGER U-G3 (closed)", width="uint8"),
    "g_level_start_x": D("Dave's start x per level.", U, "levels_warps", "game_constant"),
    "g_level_start_y": D("Dave's start y per level.", U, "levels_warps", "game_constant"),
    "g_monster_width": D("Monster box width per level 3..10 (indexed level - 2): collision box and the right "
                         "side shot spawn offset.", U, "monsters_shots_explosions", "game_constant"),
    "g_monster_height": D("Monster box height per level 3..10: collision box; shots spawn at y + h/2 - 2.",
                          U, "monsters_shots_explosions", "game_constant"),
    "g_warp_target_level_plus1": D("Warp target per level, 1-based (0 = none; 5->2, 8->6, 9->7, 10->1).",
                                   U, "levels_warps", "game_constant", "LEDGER U-M1 (closed)"),
    "g_warp_tube_tile": D("Tile of the warp-tube interlude per level.", U, "levels_warps", "presentation_constant"),
    "g_warp_start_scroll_x": D("View column where Dave arrives in the warp target, per SOURCE level; also the "
                               "respawn column inside the warp zone (indexed by g_warp_return_level).",
                               U, "levels_warps", "game_constant"),
    "g_warp_start_x": D("Dave's x on arrival in the warp target (and respawn there), per source level.",
                        U, "levels_warps", "game_constant"),
    "g_spr_warp_left": D("Sprite left of the warp tube, per gfx mode.", U, "levels_warps", "presentation_constant"),
    "g_spr_warp_right": D("Sprite right of the warp tube, per gfx mode.", U, "levels_warps", "presentation_constant"),
    "g_spr_shot_b1": D("Dave's shot sprite moving right, per gfx mode.", U, "monsters_shots_explosions",
                       "presentation_constant"),
    "g_spr_shot_b0": D("Dave's shot sprite moving left, per gfx mode.", U, "monsters_shots_explosions",
                       "presentation_constant"),
    "g_spr_jump_left": D("Dave jumping left sprite, per gfx mode.", U, "player", "presentation_constant"),
    "g_spr_jump_right": D("Dave jumping right sprite, per gfx mode.", U, "player", "presentation_constant"),
    "g_mask_jump_left": D("Mask of g_spr_jump_left.", U, "player", "presentation_constant"),
    "g_mask_jump_right": D("Mask of g_spr_jump_right.", U, "player", "presentation_constant"),
    "g_tile_digit0": D("Picture id of digit 0, per gfx mode.", U, "status_bar", "presentation_constant"),
    "g_title_anim_tiles": D("Title animation pictures, 4 per gfx mode.", U, "attract_demos", "presentation_constant"),
    "g_status_row_len": D("Row length (8) of g_status_tiles; a variable only because it was not a #define.",
                          U, "status_bar", "presentation_constant"),
    "g_status_tiles": D("Status-bar sprite ids per gfx mode: [0] jetpack icon, [1] gun icon, [2..4] labels, [5] "
                        "'go thru the door', [6] life icon.", U, "status_bar", "presentation_constant"),
    "g_pickup_tile_ids": D("Collectible tile ids: 2 door, 4 jetpack, 20 gun, 10 trophy, 47..52 treasures.",
                           U, "collisions_items_tiles", "game_constant"),
    "g_pickup_points": D("Points per collectible (door 2000 when entered with the trophy, trophy 1000, "
                         "treasures 50..500, jetpack and gun 0).", U, "collisions_items_tiles", "game_constant"),
    "g_tile_climbable": D("Per tile id 0..52: 1 = climbable (tiles 33-35, 41-46).", U, "collisions_items_tiles",
                          "game_constant"),
    "g_tile_attr": D("Per tile id 0..52: 0 free, 1 solid, 2 deadly.", U, "collisions_items_tiles",
                     "game_constant", quirks=["indexed with signed tile bytes; only level -1 leaves 0..52"]),
    "g_spr_dave_front": D("Dave facing the player, per gfx mode.", U, "player", "presentation_constant"),
    "g_mask_dave_front": D("Mask of g_spr_dave_front.", U, "player", "presentation_constant"),
    "g_spr_meter_label": D("Jetpack meter frame sprite, per gfx mode.", U, "status_bar", "presentation_constant"),
    "g_spr_meter_bar": D("One jetpack meter segment, per gfx mode.", U, "status_bar", "presentation_constant"),
    "g_animated_tile_ids": D("Base ids of animated tiles: 10 the trophy (pick_up_items stops it), 6, 25 and "
                             "36 deadly (g_tile_attr 2: the help text's fire, water and weirdweeds).",
                             U, "collisions_items_tiles", "game_constant",
                             note="which deadly id is which hazard is cosmetic and not checked against the art"),
    "g_animated_tile_frames": D("Frame counts of the animated tiles (4, 5, 4, 5).", U, "collisions_items_tiles",
                                "game_constant"),
    "g_sprite_sets": D("Animated sprite ids [set][gfx mode][frame]: 0 explosion, 1/2 monster shot right/left, "
                       "3/4 jetpack right sprite/mask, 5/6 jetpack left, 7/8 climbing, 9/10 walking left, "
                       "11/12 walking right.", U, "rendering", "presentation_constant",
                       "use sites in move_dave, process_input, draw_object, spawn_explosion, animate_tick"),
    "g_level_monster_init": D("Per-level monster block (struct monsters): active, x (level pixels), y, path "
                              "start index, reload; the other fields are overwritten by load_level.",
                              U, "monsters_shots_explosions", "game_constant", "LEDGER U-G5 (closed)"),
    "dave_c_local_buffers_image": D("Images of check_high_score..update_score's initialised char buffers "
                                    "(zeros, \"00000\").", U, "status_bar", "layout_artifact"),
    "redraw_screen_logo_image": D("7 x 10 tile ids of the title 'DAVE' logo.", U, "attract_demos",
                                  "presentation_constant"),
    "level_complete_msg_image": D("The three between-level messages (digit patched at [0][16]).", U,
                                  "levels_warps", "presentation_constant"),
    "init_game_once_default_scores_image": D("Default DSCORES.DAV: 5 x (level 1, 00100, 'JON').", U,
                                             "high_scores", "game_constant"),
    "dave_c_strings": D("DAVE.C string literals (prompts, help pages, credits, ending).", U, "text_windows",
                        "presentation_constant"),
    # -------------------------------------------------------- CONFIG.C _DATA
    "g_panel_rows": D("Control panel: text row of each option row.", U, "config_panel", "presentation_constant"),
    "g_panel_cols": D("Control panel: text column of each option.", U, "config_panel", "presentation_constant"),
    "g_scan_ascii": D("Scan code -> key-name character for the keyboard set-up screen.", U, "config_panel",
                      "presentation_constant"),
    "config_c_strings": D("CONFIG.C string literals (set-up screens, key names).", U, "config_panel",
                          "presentation_constant"),
    "config_c_pad": D("TLINK word-alignment pad.", U, "runtime", "layout_artifact"),
    # ------------------------------------------------------ HARDWARE.C _DATA
    "g_input_device": D("Input device per player 1..2 (index 0 unused): 0 keyboard, 1 mouse, 2/3 joystick 1/2; "
                        "only player 1 is ever read.", U, "input", "config"),
    "g_joy_xmin": D("Joystick x lower threshold per stick 1..2.", U, "input", "config"),
    "g_joy_xmax": D("Joystick x upper threshold per stick.", U, "input", "config"),
    "g_joy_ymin": D("Joystick y lower threshold per stick.", U, "input", "config"),
    "g_joy_ymax": D("Joystick y upper threshold per stick.", U, "input", "config"),
    "g_mouse_deadzone": D("Mouse dead zone = 15 - sensitivity.", U, "input", "config"),
    "g_key_scans": D("Bound scan codes: 8 directions N..NW, fire (Ctrl), jump/jetpack (Alt).", U, "input", "config"),
    "g_old_int9": D("Saved BIOS INT 9 vector.", U, "input", "platform_state"),
    "hardware_c_strings": D("'Out of memory!'.", U, "resources", "presentation_constant"),
    "hardware_c_pad": D("TLINK pad before lowlevel.asm's _DATA.", U, "runtime", "layout_artifact"),
    # ------------------------------------------------------- lowlevel.asm
    "RndIndex1": D("Dead RNG: index of the long lag.", U, "rng", "layout_artifact", DEAD),
    "RndIndex2": D("Dead RNG: index of the short lag.", U, "rng", "layout_artifact", DEAD),
    "RndTable": D("Dead RNG: running sum + 17-word state (zero: InitRnd is never called).", U, "rng",
                  "layout_artifact", DEAD, note="part of the level -1 collision map (U-M1)"),
    "RndInit": D("Dead RNG: Fibonacci-like seed table.", U, "rng", "layout_artifact", DEAD),
    "TimerHooked": D("1 once INT 8 is hooked.", U, "sound", "platform_state"),
    "SoundData": D("Far pointer to the SPK sound bank (set to 1C2E:0000).", U, "sound", "resource_buffer"),
    "SoundEnabled": D("Speaker output on (1) / off (0): the control panel's sound choice.", U, "sound", "config"),
    "OldInt8": D("Saved BIOS INT 8 vector.", U, "sound", "platform_state",
                 note="host-dependent; part of the level -1 collision map (U-M1)"),
    "TickDivide": D("Sound tick multiplier m: chain BIOS INT 8 every m ticks.", U, "sound", "platform_state",
                    note="asynchronous (excluded from the oracle contract)"),
    "TickCount": D("Ticks left until the next BIOS chain.", U, "sound", "platform_state"),
    "TimerRate": D("PIT channel 0 divisor of the playing sound (0 = 65536).", U, "sound", "platform_state"),
    "SoundPtr": D("Offset of the next tone word in the sound bank; 0 = silent.", U, "sound", "platform_state"),
    "SoundPriority": D("Priority of the playing sound.", U, "sound", "platform_state"),
    "SavedPtr": D("PauseSound copy of SoundPtr.", U, "sound", "platform_state"),
    "SavedPriority": D("PauseSound copy of SoundPriority.", U, "sound", "platform_state"),
    "SavedDivide": D("PauseSound copy of TickDivide.", U, "sound", "platform_state"),
    "SavedCount": D("PauseSound copy of TickCount.", U, "sound", "platform_state"),
    "SavedRate": D("PauseSound copy of TimerRate.", U, "sound", "platform_state"),
    "XorMask": D("XORed into every font pixel: -1 for inverse text (title, interlude, ending), else 0.",
                 U, "text_windows", "presentation_state"),
    "RleSegC": D("RLE: compressed buffer segment.", U, "resources", "platform_state"),
    "RleSegU": D("RLE: uncompressed buffer segment.", U, "resources", "platform_state"),
    "RleOffC": D("RLE: compressed buffer offset.", U, "resources", "platform_state"),
    "RleOffU": D("RLE: uncompressed buffer offset.", U, "resources", "platform_state"),
    "RleLength": D("RLE: bytes left.", U, "resources", "platform_state"),
    "RleOutLen": D("RLE (compressor): bytes produced.", U, "resources", "platform_state"),
    "RleRun": D("RLE (compressor): pending run length.", U, "resources", "platform_state"),
    "RleByte": D("RLE (compressor): byte of the pending run.", U, "resources", "platform_state"),
    "RleLiteral": D("RLE (compressor): pending literal count.", U, "resources", "platform_state"),
    "lowlevel_pad": D("Word-alignment pad between the asm modules' _DATA.", U, "runtime", "layout_artifact"),
    "PicWidth": D("DrawPic: bytes per line (CS-resident).", U, "config_panel", "platform_state"),
    "PicX": D("DrawPic: byte column (CS-resident).", U, "config_panel", "platform_state"),
    "PicHeight": D("DrawPic: lines left (CS-resident).", U, "config_panel", "platform_state"),
    "VIDinfo": D("VIDEO_ID result: two (subsystem, display) pairs (CS-resident).", U, "video_hardware",
                 "platform_state"),
    "EGADisplays": D("VIDEO_ID: EGA switch setting -> display type.", U, "video_hardware", "platform_state"),
    "DCCtable": D("VIDEO_ID: INT 10h 1Ah display combination codes -> (subsystem, display).", U,
                  "video_hardware", "platform_state"),
    "TestSequence": D("VIDEO_ID: (enabled, routine) of the PS/2 test.", U, "video_hardware", "platform_state"),
    "EGAflag": D("VIDEO_ID: (enabled, routine) of the EGA test.", U, "video_hardware", "platform_state"),
    "CGAflag": D("VIDEO_ID: (enabled, routine) of the CGA test.", U, "video_hardware", "platform_state"),
    "Monoflag": D("VIDEO_ID: (enabled, routine) of the MDA/Hercules test.", U, "video_hardware", "platform_state"),
    "lowlevel.CgaRowOfs": D("CGA screen line -> byte offset (interleaved banks), lowlevel.asm copy.", U,
                            "rendering", "layout_artifact", note="a multiplication table; native code computes it"),
    "lowlevel.EgaRowOfs": D("EGA line -> line * 40, lowlevel.asm copy.", U, "rendering", "layout_artifact"),
    "lowlevel.VgaRowOfs": D("VGA line -> line * 320, lowlevel.asm copy.", U, "rendering", "layout_artifact"),
    # ---------------------------------------------------------- tiles.asm
    "tiles_anon_13aa": D("Unreferenced word at the start of tiles.asm's _DATA.", U, "runtime", "layout_artifact"),
    "LevelPtr": D("Far pointer to g_levels; load_level uses its offset word.", U, "levels_warps",
                  "layout_artifact", note="native: the level array itself"),
    "TileErrMsg": D("Unreferenced 'Trouble loading tileset!$'.", U, "resources", "layout_artifact",
                    note="its last two bytes are LevelOfs[-1] = 0x2421 for level -1 (U-M1)"),
    "LevelOfs": D("Level n -> n * 0x500 (DrawLevelView).", U, "rendering", "layout_artifact"),
    "RowTimes100": D("Row -> row * 100 (used by C tile lookups).", U, "collisions_items_tiles", "layout_artifact"),
    "TileRowOfs": D("View tile row -> CGA/EGA screen offset.", U, "rendering", "layout_artifact"),
    "VgaTileRowOfs": D("View tile row -> VGA screen offset.", U, "rendering", "layout_artifact"),
    "BarPattern": D("32-byte colour pattern of the VGA playfield border lines.", U, "rendering",
                    "presentation_constant"),
    "tiles_pad": D("Pad before the palette.", U, "runtime", "layout_artifact"),
    "tiles.CgaRowOfs": D("CGA line offsets, tiles.asm copy.", U, "rendering", "layout_artifact"),
    "tiles.EgaRowOfs": D("EGA line offsets, tiles.asm copy.", U, "rendering", "layout_artifact"),
    "tiles.VgaRowOfs": D("VGA line offsets, tiles.asm copy.", U, "rendering", "layout_artifact"),
    "SprY": D("DrawMaskedEGA: sprite y (CS-resident scratch).", U, "rendering", "platform_state"),
    "MaskPtr": D("Save/restore-under: walks the mask copy (CS-resident scratch).", U, "rendering", "platform_state"),
    "tiles_anon_8428": D("Unreferenced CS word after MaskPtr.", U, "rendering", "layout_artifact"),
    "SprX": D("DrawMaskedVGA: sprite x (CS-resident scratch).", U, "rendering", "platform_state"),
    "ClipX": D("EGA blits: first byte column (CS-resident scratch).", U, "rendering", "platform_state"),
    "ClipLeft": D("XOR blits: bytes clipped on the left (CS-resident scratch).", U, "rendering", "platform_state"),
    "ClipRight": D("XOR blits: bytes clipped on the right (CS-resident scratch).", U, "rendering", "platform_state"),
    # ------------------------------------------------------ data-only module
    "g_vga_palette": D("256 x RGB (6-bit) VGA DAC palette loaded by set_video_mode(3).", U, "video_hardware",
                       "presentation_constant", "layout/symbols.json", note="rows 2..9 of the level -1 map"),
    "g_levels": D("The 10 level records (0x500 bytes: 256-byte monster path, 100 x 10 tile map, 24 unread "
                  "bytes). The game edits the CURRENT level's map in place (pickups) and restores it from "
                  "g_tiles when leaving.", U, "levels_warps", "resource_buffer", _LV, "LEDGER U-M1 (closed)",
                  note="mutable: native state needs its own copy of the current map (docs/state-model.md)"),
    # -------------------------------------------------------- DAVE.C _BSS
    "g_score": D("Score (capped at 99999).", U, "status_bar", "game_state", width="uint32"),
    "g_dave_background": D("Save-under buffer of Dave's sprite (SaveUnder* format).", U, "rendering",
                           "presentation_state"),
    "g_has_gun": D("Dave holds the gun (0/1); dropped by load_level.", U, "collisions_items_tiles", "game_state"),
    "g_gfx_index": D("Graphics table row = video mode - 1 (0 CGA, 1 EGA, 2 VGA).", U, "rendering",
                     "presentation_state", note="asm reads it as a byte (VideoType)"),
    "g_got_trophy": D("Trophy collected this level (0/1).", U, "collisions_items_tiles", "game_state"),
    "g_has_jetpack": D("Dave holds the jetpack (0/1).", U, "collisions_items_tiles", "game_state"),
    "g_hiscore_buf": D("Near pointer to the 45-byte malloc'd DSCORES.DAV image.", U, "high_scores",
                       "resource_buffer"),
    "g_actors": D("6 explosion actors {active, x (view px), y, frame 0..3, life (110..1), anim (13..1), type}; "
                  "the remaining 300 bytes of each 314-byte record are never referenced.",
                  P, "monsters_shots_explosions", "game_state", EXP("actor bytes 14..0x139 never change"),
                  "LEDGER U-G6 (closed)",
                  note="fields understood; why each record is 0x13A bytes is not (perhaps a save-under buffer "
                       "that was never used): representation of the tail unknown, behaviour none"),
    "g_player_x": D("Dave's x in view pixels (0..~0x130; level x = x + 16 * g_scroll_x).", U, "player",
                    "game_state", width="int16"),
    "g_player_y": D("Dave's y in pixels; row 0 of the map starts at y 16; jump/fall steps keep it to 8 bits.",
                    U, "player", "game_state", EXP("jump steps follow g_jump_dy, y kept to 8 bits"),
                    width="int16 storage, values 0..255 after any jump/fall step (masked & 0xff)"),
    "g_lives": D("Spare lives (3 at start, max 3 by extra lives); -1 ends the game.", U, "death_restart",
                 "game_state", width="int16"),
    "g_tileset": D("Far pointer to the 0x16000-byte work buffer holding the tile/sprite file.", U, "resources",
                   "resource_buffer"),
    "g_current_level": D("Current level, 0-based (10 after the last level; -1 after a bad warp).", U,
                         "levels_warps", "game_state", width="int16 (signed: -1 is reachable)"),
    "g_shots": D("5 shots {active, x (view px), y, dir 0 left / 1 right, frame 0..3, kind 0 monster / 1 Dave, "
                 "id = owner 1..4 monster i+1, 5 Dave}.", U, "monsters_shots_explosions", "game_state",
                 EXP("shot record value sets"), "LEDGER U-G6 (closed)"),
    "g_in_warp_zone": D("Dave is in a warp zone (level_complete then returns to g_warp_return_level).", U,
                        "levels_warps", "game_state"),
    "g_dave_sprite": D("Dave's current sprite id (per gfx mode), chosen by the game logic.", U, "player",
                       "presentation_state", note="derived from pose + frame + mode; see state-model.md"),
    "g_dave_facing": D("Facing: 0 left, 1 right (shots, jump sprite).", U, "player", "game_state"),
    "g_monsters": D("The 4 monsters, one int array per field: active, x (view px), y, path_pos (byte index, "
                    "unsigned), reload, sprite id, anim_count 2..1, anim_frame 0..3, fire_count, move_count "
                    "5..1.", U, "monsters_shots_explosions", "game_state",
                    EXP("monster records step along the level path every 5 ticks"), "LEDGER U-G5 (closed)"),
    "g_game_over": D("Leave the inner loop (game over, game won, or restart to the title).", U, "main_loop",
                     "game_state"),
    "g_death_pause": D("MISNAMED: Dave's movement throttle (reloaded to 3 after each move; walk moves every 3rd "
                       "tick, jump/climb every 2nd, fall/jetpack every tick). Was 'speed throttle DS 0x5794'.",
                       U, "player", "game_state", EXP("movement throttle (g_death_pause)"),
                       "LEDGER U-G2 (closed)", width="int16 (decremented every alive tick)"),
    "g_shot_anim_count": D("Shared shot frame countdown (3..1, decremented per active shot).", U,
                           "monsters_shots_explosions", "game_state"),
    "g_jetpack_fuel": D("Jetpack fuel units (60 when picked up; one per 15 flying ticks).", U, "player",
                        "game_state"),
    "g_jump_pos": D("Index into g_jump_dy of the next jump step.", U, "player", "game_state"),
    "g_quit": D("Never set after init (0): the quit path exits directly through quit_game.", U, "main_loop",
                "game_state", note="effectively constant 0"),
    "g_prev_dir": D("Direction of the previous move request (turn-around and landing-sprite logic).", U,
                    "player", "game_state"),
    "g_scroll_x": D("First visible level column (0..80).", U, "player", "game_state"),
    "g_demo_pos": D("Read position in the demo bank.", U, "attract_demos", "game_state"),
    "g_demo_data": D("Far pointer to the demo bank (0B31:0000).", U, "attract_demos", "resource_buffer"),
    "g_level": D("Near pointer to the current level's live tile map inside g_levels (record + 0x100).", U,
                 "levels_warps", "layout_artifact", note="native: an index / the map copy itself"),
    "g_level_visited": D("Per level: its warp has been used this game.", U, "levels_warps", "game_state"),
    "g_hiscores": D("In-memory high scores {level, score (16-bit), initials}.", U, "high_scores", "game_state",
                    width="score uint16 (truncated)"),
    "pad_57e1": D("Word-alignment pad.", U, "runtime", "layout_artifact"),
    "g_input_dir": D("Requested direction 0..7 (8 none), consumed (set to 8) by the move that uses it.", U,
                     "input", "game_state"),
    "g_dave_mask": D("Mask id of g_dave_sprite.", U, "player", "presentation_state"),
    "g_jet_facing": D("Facing used for the jetpack sprites (0 left, 1 right).", U, "player", "game_state"),
    "g_anim_tiles": D("Up to 200 animated tile records {active, first, cur, col, row, count}, list ended by "
                      "count 0 (at most 84 used, level 2).", U, "collisions_items_tiles", "game_state"),
    "g_next_extra_life": D("Score of the last extra-life threshold (multiple of 20000).", U, "status_bar",
                           "game_state", width="uint32"),
    "g_level_path": D("Huge pointer to the current level's monster path (record start).", U,
                      "monsters_shots_explosions", "layout_artifact"),
    "g_anim_frame": D("Dave's animation frame 0..3 (walking, climbing, jetpack, interlude walk), stepped every "
                      "g_anim_delay ticks. Was 'DS 0x6150 animation frame?' (U-G4).", U, "player", "game_state",
                      EXP("g_anim_frame in 0..3"), "LEDGER U-G4 (closed)"),
    "g_warp_return_level": D("Level that was left through the warp (respawn and return use it).", U,
                             "levels_warps", "game_state"),
    "g_fuel_tick": D("Ticks (15..1) until the next fuel unit burns.", U, "player", "game_state"),
    "g_dave_state": D("Dave state bits: 0x01 jetpack, 0x02 climbing, 0x04 walking (on ground), 0x08 falling, "
                      "0x10 jumping, 0x20 alive/controllable, 0x40 killed (with 0x20: deferred death next "
                      "move_dave; alone: leftover of a shot death); 0x80 never set.", U, "player", "game_state",
                      EXP("dave_state transitions"), "LEDGER U-G1 (closed)", width="int16, low byte used"),
    "g_level_done": D("Door entered with the trophy: level_complete runs at the end of this tick.", U,
                      "levels_warps", "game_state"),
    "g_anim_tick_divider": D("Animated-tile countdown 10..1 (tiles step every 10 ticks). Was 'DS 0x615A, the "
                             "external RE's levels_left' (U-G4): init_game_state only presets it.", U,
                             "collisions_items_tiles", "game_state", EXP("g_anim_tick_divider counts 10..1"),
                             "LEDGER U-G4 (closed)"),
    "g_tiles": D("Pristine copy of the current level's map, taken by load_level; restores g_levels when the "
                 "level is left (the header's 'working grid' is wrong: g_level is the working copy).",
                 U, "levels_warps", "game_state", "load_level, handle_death, level_complete, check_warp_transition"),
    "g_demo_repeat": D("Demo idle run counter (signed char; wraps like an 8-bit counter).", U, "attract_demos",
                       "game_state", width="int8"),
    "pad_6545": D("Word-alignment pad.", U, "runtime", "layout_artifact"),
    "g_bonus_timer": D("MISNAMED: Dave's death timer (300 ticks from his explosion until handle_death acts).",
                       U, "death_restart", "game_state", EXP("dave_state transitions"), width="int16"),
    "g_anim_delay": D("Countdown to Dave's next animation frame (2 walking/climbing, 4 jetpack).", U, "player",
                      "game_state"),
    "g_unused_654a": D("Never referenced (BSS hole).", BU, "runtime", "layout_artifact",
                       "inventory relations: no reader, no writer; docs/data-layout.json has no reference",
                       "LEDGER U-M2 (closed)", note="unused; its original type is unknowable"),
    # ------------------------------------------------------ CONFIG.C _BSS
    "g_have_ega": D("EGA available (adapter 3 or 5).", U, "config_panel", "platform_state"),
    "g_have_vga": D("VGA available (adapter 4 or 5).", U, "config_panel", "platform_state"),
    "g_have_joystick": D("Joystick found: 0, 1, or 2 (stick 2 also lands here).", U, "config_panel",
                         "platform_state"),
    "g_have_joystick2": D("Never set non-zero (see detect_hardware).", U, "config_panel", "platform_state"),
    "g_panel_col": D("Control panel cursor column.", U, "config_panel", "presentation_state"),
    "g_have_mouse": D("Mouse driver present.", U, "config_panel", "platform_state"),
    "g_unused_6558": D("Never referenced (BSS hole).", BU, "runtime", "layout_artifact", "LEDGER U-M2 (closed)"),
    "g_pic_planes": D("Picfile plane segments (EGA upload source).", U, "resources", "resource_buffer"),
    "g_panel_avail": D("Control panel availability grid [row][col] (rows video, sound, control).", U,
                       "config_panel", "presentation_state"),
    "g_saved_video": D("Video mode on entry to the control panel (written, never read).", U, "config_panel",
                       "presentation_state"),
    "g_unused_65da": D("Never referenced (BSS hole).", BU, "runtime", "layout_artifact", "LEDGER U-M2 (closed)"),
    "g_saved_sound": D("Sound choice on entry to the panel (never read).", U, "config_panel", "presentation_state"),
    "g_pic_sprites": D("Picfile sprite table copy (256 x 32 bytes; written, never read).", U, "resources",
                       "layout_artifact"),
    "g_cur_video": D("Control panel: chosen video mode.", U, "config_panel", "presentation_state"),
    "g_unused_85fe": D("Never referenced (BSS hole).", BU, "runtime", "layout_artifact", "LEDGER U-M2 (closed)"),
    "g_saved_control1": D("Player 1 device on entry to the panel (never read).", U, "config_panel",
                          "presentation_state"),
    "g_saved_control2": D("Player 2 device on entry to the panel (never read).", U, "config_panel",
                          "presentation_state"),
    "g_pic_table": D("Picfile picture table (64 x {width, height, offset, name}).", U, "resources",
                     "resource_buffer"),
    "g_unused_8a04": D("Never referenced (BSS hole).", BU, "runtime", "layout_artifact", "LEDGER U-M2 (closed)"),
    "g_cur_sound": D("Control panel: chosen sound setting.", U, "config_panel", "presentation_state"),
    "g_panel_row": D("Control panel cursor row.", U, "config_panel", "presentation_state"),
    "g_unused_8a0c": D("Never referenced (BSS hole).", BU, "runtime", "layout_artifact", "LEDGER U-M2 (closed)"),
    "g_cur_control1": D("Control panel: chosen device for player 1.", U, "config_panel", "presentation_state"),
    "g_cur_control2": D("Control panel: player 2 device (never changed).", U, "config_panel", "presentation_state"),
    "g_text_x": D("Text cursor column.", U, "text_windows", "presentation_state"),
    "g_text_y": D("Text cursor row.", U, "text_windows", "presentation_state"),
    "g_pic_charptr": D("Picfile 8x8 font pointer (asm uses its segment).", U, "resources", "resource_buffer"),
    "g_pic_spriteptr": D("Picfile sprite pointer (never read).", U, "resources", "layout_artifact"),
    "g_pic_picptr": D("Picfile picture data pointer (asm uses its segment).", U, "resources", "resource_buffer"),
    "g_text_left": D("Left margin of the text window.", U, "text_windows", "presentation_state"),
    # ---------------------------------------------------- HARDWARE.C _BSS
    "g_win_x1": D("Text window left.", U, "text_windows", "presentation_state"),
    "g_win_x2": D("Text window right.", U, "text_windows", "presentation_state"),
    "g_win_y1": D("Text window top.", U, "text_windows", "presentation_state"),
    "g_win_y2": D("Text window bottom.", U, "text_windows", "presentation_state"),
    "g_demo_ptr": D("Dead input recorder: buffer position.", U, "attract_demos", "layout_artifact", DEAD),
    "g_pic_tileptr": D("Picfile tile pointer (never read).", U, "resources", "layout_artifact"),
    "g_keydown": D("Key state per scan code (1 down), maintained by the INT 9 handler.", U, "input",
                   "platform_state", "oracle: the input of every tick (docs/FIDELITY.md section 4)"),
    "g_video_mode": D("Video mode 1 CGA, 2 EGA, 3 VGA (0 = text for set_video_mode).", U, "video_hardware",
                      "config"),
    "g_demo_buffer": D("Dead input recorder: 5004-byte buffer.", U, "attract_demos", "layout_artifact", DEAD),
    "g_adapter_type": D("VideoID result.", U, "video_hardware", "platform_state"),
    "g_demo_state": D("Dead input recorder mode (0 live, 1 playback, 2 record): always 0. NOT the attract "
                      "flag (N-1).", U, "attract_demos", "layout_artifact", "LEDGER N-1"),
    "g_alloc_block": D("Last farmalloc block.", U, "resources", "platform_state"),
    # ------------------------------------------------------- far segments
    "g_demo_bank": D("Attract demos: u32 count 5, u32 offsets, per demo a level byte and the input stream.",
                     U, "attract_demos", "resource_buffer", "tools/demos.py, tests/test_demos_roundtrip.py"),
    "g_tileset_cga": D("CGA tileset, RLE-compressed (u32 length + stream).", U, "resources", "resource_buffer",
                       "tools/tilesets.py"),
    "g_tileset_vga": D("VGA tileset, RLE-compressed.", U, "resources", "resource_buffer", "tools/tilesets.py"),
    "g_sound_bank": D("PC-speaker sound bank (SPK).", U, "sound", "resource_buffer", "tools/sounds.py"),
    "g_picfile_cga": D("Control panel picfile (font + 13 icons), CGA.", U, "config_panel", "resource_buffer",
                       "tools/picfiles.py"),
    "g_picfile_ega": D("Control panel picfile, EGA (4 planes).", U, "config_panel", "resource_buffer",
                       "tools/picfiles.py"),
    "g_picfile_vga": D("Control panel picfile, VGA.", U, "config_panel", "resource_buffer", "tools/picfiles.py"),
}

# ===================================================== resource / record formats
def R(where, purpose, status, subsystem, evidence, objects=(), codec=None, **kw):
    d = {"identity": {"where": where}, "purpose": purpose, "status": status, "subsystem": subsystem,
         "evidence": list(evidence), "objects": list(objects), "codec": codec}
    d.update(kw)
    return d


FORMATS = {
    "level_record": R("g_levels, DS 0x173A, 10 x 0x500",
                      "256-byte monster path ((dx, dy) signed byte pairs, 0xEA restarts), 100 x 10 tile map "
                      "(row-major, tile ids 0..52), 24 unread bytes.", U, "levels_warps",
                      [_LV, "tests/test_levels_roundtrip.py"], ["g_levels"], "tools/levels.py"),
    "monster_path": R("first 256 bytes of a level record",
                      "Signed (dx, dy) pairs applied every 5 ticks; 0xEA in the dx slot restarts at index 0; "
                      "levels 1-2 have no terminator (no monsters).", U, "monsters_shots_explosions",
                      [EXP("monster records step along the level path every 5 ticks")], ["g_levels"], "tools/levels.py"),
    "demo_stream": R("g_demo_bank (far 0B31)",
                     "u32 count, u32 offsets; per demo a start level byte, then per tick: 0x20 n = n idle ticks, "
                     "0x30 end, else bit 7 fire, bit 6 jetpack, low nibble direction 0..8.", U, "attract_demos",
                     ["tools/demos.py", "tests/test_demos_roundtrip.py", "src/DAVE.C process_input"],
                     ["g_demo_bank"], "tools/demos.py"),
    "input_recorder_byte": R("g_demo_buffer (dead)",
                             "Dead input recorder: one byte per call, dir << 2 | jump << 1 | fire.", U,
                             "attract_demos", ["src/HARDWARE.C get_player_input", DEAD], ["g_demo_buffer"]),
    "tileset_container": R("g_tileset work buffer; EGADAVE.DAV; expanded CGA/VGA tilesets",
                           "u32 count, u32 offsets; resources 0..52 are 16 x 16 tiles (CGA 64 B, EGA 128 B planar, "
                           "VGA 256 B), the rest sprites {u16 width, u16 height, pixels}, pre-shifted (EGA 4 "
                           "copies for x & 6, CGA 2 for x & 2) with masks as separate resources.",
                           P, "resources", ["tools/tilesets.py", "tools/egadave_decode.py",
                                            "src/asm/tiles.asm header"],
                           ["g_tileset", "g_tileset_cga", "g_tileset_vga"], "tools/tilesets.py",
                           note="sprite header misreads after the duplicated VGA byte (resources 147-157) and the "
                                "CGA unread tails are not yet shown to be invisible (U-R3)"),
    "rle_stream": R("g_tileset_cga / g_tileset_vga (+4)",
                    "Code byte c < 0x80: c + 3 copies of the next byte; c >= 0x80: c - 0x7F literal bytes.",
                    U, "resources", ["tools/rle.py", "tests/test_tilesets_roundtrip.py"],
                    ["g_tileset_cga", "g_tileset_vga"], "tools/rle.py"),
    "spk_sound_bank": R("g_sound_bank (far 1C2E)",
                        "'SPK\\0', u32 length, 63 x {u16 offset, u8 priority, u8 rate, name[12]}, then u16 PIT "
                        "divisor lists (0 rest, 0xFFFF end) played one word per driver tick.", U, "sound",
                        ["tools/sounds.py", "tests/test_sounds_roundtrip.py", "src/asm/lowlevel.asm Int8ISR"],
                        ["g_sound_bank", "SoundData"], "tools/sounds.py"),
    "picfile": R("g_picfile_cga/_ega/_vga",
                 "0x100-byte header of far pointers and tables, 8x8 font (128 chars), 13 control-panel pictures.",
                 U, "config_panel", ["tools/picfiles.py", "tests/test_picfiles_roundtrip.py"],
                 ["g_picfile_cga", "g_picfile_ega", "g_picfile_vga", "g_pic_table"], "tools/picfiles.py"),
    "vga_palette": R("g_vga_palette, DS 0x143A", "256 x (R, G, B), 6-bit DAC values.", U, "video_hardware",
                     ["src/HARDWARE.C set_video_mode", "tools/pixels.py"], ["g_vga_palette"], "tools/pixels.py"),
    "dscores_dav": R("DSCORES.DAV (45 bytes) / g_hiscore_buf",
                     "5 x {u8 level (1-based, 11 = won), u8 digits[5] 0..9, char initials[3]}.", U, "high_scores",
                     ["src/DAVE.H struct hiscore", "src/DAVE.C init_game_once, check_high_score"],
                     ["g_hiscore_buf", "init_game_once_default_scores_image"]),
    "hiscore_entry": R("g_hiscores", "7-byte {int level, unsigned score, char name[3]} (score truncated to 16 "
                       "bits).", U, "high_scores", ["src/DAVE.H struct entry"], ["g_hiscores"]),
    "save_under_buffer": R("g_dave_background",
                           "{x (bytes), y * 2, width (bytes), height, mask size, mask copy, saved background}; "
                           "planar on EGA.", U, "rendering", ["src/asm/tiles.asm SaveUnder*/RestoreUnder*"],
                           ["g_dave_background"]),
    "input_struct": R("returned by the input readers", "{int dir 0..7 clockwise from north / 8 none, int fire, "
                      "int jump}.", U, "input", ["src/DAVE.H struct input"], []),
    "anim_tile_record": R("g_anim_tiles", "{active, first, cur, col, row, count}; list ended by count <= 0.",
                          U, "collisions_items_tiles", ["src/DAVE.H struct anim", "src/DAVE.C load_level"],
                          ["g_anim_tiles"]),
    "shot_record": R("g_shots", "{active, x, y, dir, frame, kind, id} (7 ints).", U, "monsters_shots_explosions",
                     ["src/DAVE.H struct shot", EXP("shot record value sets")], ["g_shots"]),
    "actor_record": R("g_actors", "{active, x, y, frame, life, anim, type} + 300 unreferenced bytes.",
                      P, "monsters_shots_explosions", ["src/DAVE.H struct actor",
                                                       EXP("actor bytes 14..0x139 never change")], ["g_actors"],
                      note="the 300-byte tail's intended use is unknown"),
    "monster_block": R("g_monsters / g_level_monster_init", "10 arrays of 4 ints (struct-of-arrays).",
                       U, "monsters_shots_explosions", ["src/DAVE.H struct monsters"],
                       ["g_monsters", "g_level_monster_init"]),
}

# ================================================================ subsystems
SUBSYSTEMS = {
    "main_loop": {"purpose": "Program start-up, the game mode machine (title / demo / scores / play) and the "
                             "13-call tick pipeline.", "evidence": ["docs/FIDELITY.md section 1"]},
    "player": {"purpose": "Dave's movement, physics, animation, jetpack and view scrolling.",
               "evidence": ["LEDGER U-G1, U-G2, U-G4 (closed)"]},
    "monsters_shots_explosions": {"purpose": "Monster paths and firing, the shot table, explosion actors.",
                                  "evidence": ["LEDGER U-G5, U-G6, U-G7 (closed)"]},
    "collisions_items_tiles": {"purpose": "Tile attributes and probes, collisions, item pickup, animated tiles.",
                               "evidence": ["src/DAVE.C"]},
    "levels_warps": {"purpose": "Level loading, the live/backup tile maps, level completion and warp zones.",
                     "evidence": ["LEDGER U-M1, U-G8 (closed)"], "open": ["U-M3 level -1 reachability per level"]},
    "death_restart": {"purpose": "Death timer, lives, respawn and game over.", "evidence": ["src/DAVE.C handle_death"]},
    "status_bar": {"purpose": "Score, extra lives, inventory icons, jetpack meter, level number.",
                   "evidence": ["src/DAVE.C"]},
    "input": {"purpose": "Keyboard ISR and key table, device readers, per-tick input processing.",
              "evidence": ["src/HARDWARE.C", "src/DAVE.C process_input"]},
    "attract_demos": {"purpose": "Title animation, attract-mode demo selection and playback, the dead recorder.",
                      "evidence": ["tools/demos.py"]},
    "high_scores": {"purpose": "High-score table, initials entry, DSCORES.DAV.", "evidence": ["src/DAVE.C"]},
    "menus": {"purpose": "Function-key popups: help, restart, pause, quit.", "evidence": ["src/DAVE.C"]},
    "config_panel": {"purpose": "F2 control panel and the device set-up screens.", "evidence": ["src/CONFIG.C"],
                     "open": ["EGA/CGA picture blits not captured (M1.4)"]},
    "text_windows": {"purpose": "Text windows, cursor, font drawing.", "evidence": ["src/HARDWARE.C"]},
    "rendering": {"purpose": "Level view, tiles, masked / XOR sprites, save-under, full redraws.",
                  "evidence": ["src/asm/tiles.asm"], "open": ["U-R1..U-R4", "EGA/CGA capture (M1.4)"]},
    "sound": {"purpose": "PC-speaker driver on INT 8 with priorities and per-sound tick rates.",
              "evidence": ["LEDGER U-S2 (closed)"]},
    "rng": {"purpose": "Random numbers: Borland rand() (used) and the asm lagged-Fibonacci generator (dead).",
            "evidence": ["LEDGER U-S1 (closed)"]},
    "resources": {"purpose": "Allocation, file I/O, RLE, tileset and picfile set-up.",
                  "evidence": ["tools/ codecs"], "open": ["U-R3 sprite header misreads"]},
    "video_hardware": {"purpose": "Adapter detection, video modes, palette, the retrace clock.",
                       "evidence": ["src/asm/lowlevel.asm"], "open": ["U-T2 EGA/CGA refresh rates"]},
    "runtime": {"purpose": "C0S / CS.LIB data, padding and unreferenced holes.", "evidence": ["docs/data-layout.md"]},
}
