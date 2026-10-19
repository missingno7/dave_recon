"""Curated half of the semantic inventory (tools/semantic_inventory.py).

Identities and relations are parsed mechanically from the sources; this
module holds what reading the code (and the oracle) established: a one-line
purpose, a status, the evidence, the subsystem and, for data, its role.
The FUNCTIONS / DATA / FORMATS / SUBSYSTEMS tables live in
tools/semantic_annotations_tables.py (they are long); this file holds the
structural inputs the generator needs.
"""

ROLE_DOC = {
    "game_state": "true gameplay state: part of the native `struct game` (docs/state-model.md)",
    "game_constant": "immutable gameplay table (level setup, physics, collision attributes); native: const data",
    "presentation_state": "drawing / text / menu state; native: presentation layer, not `struct game`",
    "presentation_constant": "per-video-mode sprite / tile ids, screen geometry, palette; native: presentation tables",
    "platform_state": "hardware, interrupt, device and allocation state; native: platform layer (or nothing)",
    "config": "user settings (input device, key bindings, calibration, sound / video choice); native: settings",
    "resource_buffer": "loaded resource data or a pointer to it; native: resource objects built by the codecs",
    "layout_artifact": "exists only because of the original memory layout / toolchain (holes, padding, "
                       "unreferenced data, helper pointers and multiplication tables); eliminate",
    "runtime": "C0S / CS.LIB runtime data (only the rand() seed is observable to the game)",
}

# objects not defined by the C units or the assembly modules (data-only module,
# far segments, runtime areas, initialised-local images and string pools)
EXTRA_DATA = {
    "c0s_data": {"unit": "C0S.OBJ", "type": "runtime _DATA", "size": 0xA8, "segment": "_DATA", "ds": 0x0000,
                 "source": "docs/data-layout.md (DGROUP internal layout)"},
    "dave_c_local_buffers_image": {"unit": "DAVE.C", "type": "char[30]", "size": 30, "segment": "_DATA",
                                   "ds": 0x07B6, "source": "src/DAVE.C (comment before check_high_score)"},
    "redraw_screen_logo_image": {"unit": "DAVE.C", "type": "char[7][10]", "size": 70, "segment": "_DATA",
                                 "ds": 0x07D4, "source": "src/DAVE.C redraw_screen"},
    "level_complete_msg_image": {"unit": "DAVE.C", "type": "char[3][35]", "size": 105, "segment": "_DATA",
                                 "ds": 0x081A, "source": "src/DAVE.C level_complete"},
    "init_game_once_default_scores_image": {"unit": "DAVE.C", "type": "struct hiscore[5]", "size": 45,
                                            "segment": "_DATA", "ds": 0x0883, "source": "src/DAVE.C init_game_once"},
    "dave_c_strings": {"unit": "DAVE.C", "type": "string pool", "size": 0x0F02 - 0x08B0, "segment": "_DATA",
                       "ds": 0x08B0, "source": "src/DAVE.C (unit header: string pool DS 0x08b0..)"},
    "config_c_strings": {"unit": "CONFIG.C", "type": "string pool", "size": 0x12EF - 0x0F92, "segment": "_DATA",
                         "ds": 0x0F92, "source": "src/CONFIG.C (unit header)"},
    "config_c_pad": {"unit": "CONFIG.C", "type": "padding", "size": 1, "segment": "_DATA", "ds": 0x12EF,
                     "source": "src/CONFIG.C (TLINK word pad)"},
    "hardware_c_strings": {"unit": "HARDWARE.C", "type": "string pool", "size": 0x132D - 0x131E,
                           "segment": "_DATA", "ds": 0x131E, "source": "src/HARDWARE.C (\"Out of memory!\")"},
    "hardware_c_pad": {"unit": "HARDWARE.C", "type": "padding", "size": 1, "segment": "_DATA", "ds": 0x132D,
                       "source": "src/HARDWARE.C (TLINK pads before lowlevel.asm's _DATA)"},
    "lowlevel_pad": {"unit": "asm/lowlevel.asm", "type": "padding", "size": 1, "segment": "_DATA", "ds": 0x13A9,
                     "source": "src/asm/tiles.asm header (word alignment before tiles.asm _DATA)"},
    "tiles_pad": {"unit": "asm/tiles.asm", "type": "padding", "size": 1, "segment": "_DATA", "ds": 0x1439,
                  "source": "src/asm/tiles.asm header (one pad byte before the palette)"},
    "g_vga_palette": {"unit": "data-only module", "type": "unsigned char[768]", "size": 768, "segment": "_DATA",
                      "ds": 0x143A, "source": "layout/symbols.json _g_vga_palette; src/DAVE.H"},
    "g_levels": {"unit": "data-only module", "type": "char[10][0x500]", "size": 12800, "segment": "_DATA",
                 "ds": 0x173A, "source": "docs/data-layout.md section 2; tools/levels.py; tiles.asm `Levels` (_D_173A)"},
    "cslib_data": {"unit": "CS.LIB", "type": "runtime _DATA", "size": 0x4BB6 - 0x493A, "segment": "_DATA",
                   "ds": 0x493A, "source": "docs/data-layout.md (CS.LIB _DATA in link order)"},
    "rand_seed": {"unit": "CS.LIB (RAND)", "type": "unsigned long", "size": 4, "segment": "_DATA", "ds": 0x4BB6,
                  "source": "docs/data-layout.md (`rand` seed 0x4BB6)"},
    "cslib_data_2": {"unit": "CS.LIB", "type": "runtime _DATA", "size": 0x4C60 - 0x4BBA, "segment": "_DATA",
                     "ds": 0x4BBA, "source": "docs/data-layout.md (CS.LIB _DATA in link order)"},
    "cslib_bss_and_stack": {"unit": "CS.LIB / C0S", "type": "runtime _BSS + _STACK", "size": 0x9F20 - 0x9EC8,
                            "segment": "_BSS", "ds": 0x9EC8, "source": "docs/bss-map.md (CS.LIB _BSS from 0x9EC8)"},
    "g_demo_bank": {"kind": "far_data", "unit": "far segment", "type": "char far[]", "size": 4368,
                    "segment": "FAR_DATA", "para": 0x0B31, "source": "layout/symbols.json; tools/demos.py"},
    "g_tileset_cga": {"kind": "far_data", "unit": "far segment", "type": "char far[]", "size": 23248,
                      "segment": "FAR_DATA", "para": 0x0C42, "source": "layout/symbols.json; tools/tilesets.py"},
    "g_tileset_vga": {"kind": "far_data", "unit": "far segment", "type": "char far[]", "size": 41968,
                      "segment": "FAR_DATA", "para": 0x11EF, "source": "layout/symbols.json; tools/tilesets.py"},
    "g_sound_bank": {"kind": "far_data", "unit": "far segment", "type": "char far[]", "size": 4768,
                     "segment": "FAR_DATA", "para": 0x1C2E, "source": "layout/symbols.json; tools/sounds.py"},
    "g_picfile_cga": {"kind": "far_data", "unit": "far segment", "type": "char far[]", "size": 4800,
                      "segment": "FAR_DATA", "para": 0x1D58, "source": "layout/symbols.json; tools/picfiles.py"},
    "g_picfile_ega": {"kind": "far_data", "unit": "far segment", "type": "char far[]", "size": 9344,
                      "segment": "FAR_DATA", "para": 0x1E84, "source": "layout/symbols.json; tools/picfiles.py"},
    "g_picfile_vga": {"kind": "far_data", "unit": "far segment", "type": "char far[]", "size": 18432,
                      "segment": "FAR_DATA", "para": 0x20CC, "source": "layout/symbols.json; tools/picfiles.py"},
}

# procedures whose source carries no census id: start (FILE offset) from the
# binary. FindPS2/FindEGA/FindCGA/FindMono are the four routine words of
# VideoID's TestSequence table (file 0x7C4D + 1 + 3k, read from
# build/DAVE_unpacked.exe); Find6845 follows FindMono (B0 0F EE 42 EC = its
# first instructions); FindActive is census F_7D87 (VideoID calls it);
# FoundDevice is the 13 bytes between FindActive's end (census size 49) and
# RLECompress (file 0x7DC5).
ASM_ADDRESSES = {"FindPS2": 0x7C9F, "FindEGA": 0x7CEF, "FindCGA": 0x7D1B, "FindMono": 0x7D2B,
                 "Find6845": 0x7D6D, "FindActive": 0x7D87, "FoundDevice": 0x7DB8}

# table -> (procedure that dispatches through it, procedures it holds)
DISPATCH_TABLES = {"TestSequence": ("VideoID", ["FindPS2", "FindEGA", "FindCGA", "FindMono"])}

# interrupt handlers -> the procedure that installs them
INTERRUPT_HANDLERS = {"Int8ISR": "StartSound", "keyboard_isr": "install_keyboard_handler"}

# CS.LIB routines -> the runtime data they read / write (Borland rand: LCG on a long seed)
LIBRARY_DATA = {"rand": {"reads": ["rand_seed"], "writes": ["rand_seed"]}, "srand": {"writes": ["rand_seed"]}}

# functions the binary call-graph walk reaches although no source path does
BINARY_WALK_ARTIFACTS = {
    "Random": "the binary walk (docs/function-census-callgraph-v2.json) does not stop at IRET, so it runs "
              "on from Int8ISR into InitRnd and records InitRnd's two `call Random` as Int8ISR's; no code "
              "calls InitRnd or Random",
}

from semantic_annotations_tables import FUNCTIONS, DATA, FORMATS, SUBSYSTEMS  # noqa: E402,F401
