/*
 * DAVE.H -- shared declarations of the Dangerous Dave C units
 * (DAVE.C, CONFIG.C, HARDWARE.C), the assembly modules and the data.
 *
 * _BSS storage names. Turbo C++ 1.00 lays out a unit's uninitialised
 * globals sorted by a hash of their names (docs/compiler-behaviors.md), so
 * the original layout follows from the original names, which are lost.
 * Code uses the readable names; where a readable name would hash into the
 * wrong slot, the #define below binds it to a storage name chosen to hash
 * into the right one (tools/bss_names.py, from layout/bss-map.json).
 * Ties are broken by first appearance, so the extern declarations below
 * list every unit's _BSS variables in address order and must stay that
 * way (tools/bss_names.py --check).
 */

struct input {                  /* returned by the input readers */
    int dir;                    /* 0..7 clockwise from north, 8 = none */
    int fire;
    int jump;
};

struct hiscore {                /* 9-byte DSCORES.DAV record */
    char level;
    char score[5];              /* decimal digits 0..9 */
    char name[3];
};

struct entry {                  /* 7-byte in-memory high score entry */
    int level;
    unsigned score;
    char name[3];
};

struct actor {                  /* 0x13A-byte animated object (explosions ...) */
    int active;
    int x;
    int y;
    int frame;
    int life;
    int anim;
    int type;
    char rest[0x13a - 14];
};

struct shot {                   /* 14-byte bullet */
    int active;
    int x;
    int y;
    int dir;
    int frame;
    int kind;
    int id;
};

struct anim {                   /* 12-byte animated tile */
    int active;
    int first;
    int cur;
    int col;
    int row;
    int count;
};

struct monsters {               /* the level's 4 monsters, one array per field */
    int active[4];
    int x[4];
    int y[4];
    unsigned path_pos[4];
    int reload[4];
    int sprite[4];
    int anim_count[4];
    int anim_frame[4];
    int fire_count[4];
    int move_count[4];
};

struct s16 { char b[16]; };     /* picture file picture-table entry */
struct s32 { char b[32]; };     /* picture file sprite-table entry */

struct gfxhdr {                 /* picture file header (setup_graphics_pointers) */
    char far *p0;               /* 8x8 font */
    char far *p1;               /* tiles */
    char far *p2;               /* pictures */
    char far *p3;               /* sprites */
    char far *s16;              /* picture table */
    char far *s32;              /* sprite table */
    char far *plane[4];         /* plane segments */
};

/* ---- _BSS storage names (tools/bss_names.py, layout/bss-map.json) */
#define g_dave_background g_dave_background___zh
#define g_has_gun g_has_gun_Jh
#define g_gfx_index g_gfx_index__2h
#define g_got_trophy g_got_trophy_2h
#define g_has_jetpack g_has_jetpack_______zh
#define g_hiscore_buf g_hiscore_buf_______zh
#define g_actors g_actors_Rh
#define g_lives g_lives_ah
#define g_tileset g_tileset_Qh
#define g_current_level g_current_level______yh
#define g_shots g_shots_ah
#define g_in_warp_zone g_in_warp_zone_0h
#define g_dave_sprite g_dave_sprite_8h
#define g_dave_facing g_dave_facing_8h
#define g_monsters g_monsters_Ph
#define g_death_pause g_death_pause__5h
#define g_shot_anim_count g_shot_anim_count______uh
#define g_jetpack_fuel g_jetpack_fuel_5h
#define g_quit g_quit_wh
#define g_prev_dir g_prev_dir_Wh
#define g_scroll_x g_scroll_x_Wh
#define g_demo_data g_demo_data_Oh
#define g_level g_level_oh
#define g_level_visited g_level_visited_0h
#define g_hiscores g_hiscores_Xh
#define g_anim_tiles g_anim_tiles_Vh
#define g_next_extra_life g_next_extra_life_0h
#define g_anim_frame g_anim_frame__Th
#define g_warp_return_level g_warp_return_level_______th
#define g_fuel_tick g_fuel_tick_dh
#define g_level_done g_level_done_ah
#define g_tiles g_tiles_0h
#define g_demo_repeat g_demo_repeat__xh
#define g_bonus_timer g_bonus_timer__xh
#define g_anim_delay g_anim_delay___xh
#define g_unused_654a g_unused_654a__xh
#define g_have_joystick g_have_joystick_______wh
#define g_have_joystick2 g_have_joystick2______wh
#define g_panel_col g_panel_col_Gh
#define g_have_mouse g_have_mouse_Ah
#define g_unused_6558 g_unused_6558_9h
#define g_pic_planes g_pic_planes_Ah
#define g_panel_avail g_panel_avail_9h
#define g_saved_video g_saved_video_9h
#define g_unused_65da g_unused_65da_9h
#define g_saved_sound g_saved_sound_9h
#define g_pic_sprites g_pic_sprites_9h
#define g_unused_85fe g_unused_85fe_Ah
#define g_saved_control1 g_saved_control1_______yh
#define g_saved_control2 g_saved_control2_______yh
#define g_unused_8a04 g_unused_8a04_Dh
#define g_unused_8a0c g_unused_8a0c_Gh
#define g_text_x g_text_x___th
#define g_text_y g_text_y___th
#define g_pic_picptr g_pic_picptr_th
#define g_text_left g_text_left__th
#define g_demo_ptr g_demo_ptr_Qh
#define g_pic_tileptr g_pic_tileptr_9h
#define g_adapter_type g_adapter_type_Eh
#define g_alloc_block g_alloc_block_Th

/* ---- DAVE.C data */
extern int g_demo_recording;
extern int g_demo_mode;
extern signed char g_fire_repeat;
extern signed char g_jetpack_repeat;
extern char g_hiscore_file[];
extern int g_jump_dy[];
extern unsigned char g_level_flags[];
extern int g_level_start_x[];
extern int g_level_start_y[];
extern int g_monster_width[];
extern int g_monster_height[];
extern int g_warp_target_level_plus1[];
extern int g_warp_tube_tile[];
extern int g_warp_start_scroll_x[];
extern int g_warp_start_x[];
extern int g_spr_warp_left[];
extern int g_spr_warp_right[];
extern int g_spr_shot_b1[];
extern int g_spr_shot_b0[];
extern int g_spr_jump_left[];
extern int g_spr_jump_right[];
extern int g_mask_jump_left[];
extern int g_mask_jump_right[];
extern int g_tile_digit0[];
extern int g_title_anim_tiles[];
extern int g_status_row_len;
extern int g_status_tiles[];
extern int g_pickup_tile_ids[];
extern int g_pickup_points[];
extern int g_tile_climbable[];
extern int g_tile_attr[];
extern int g_spr_dave_front[];
extern int g_mask_dave_front[];
extern int g_spr_meter_label[];
extern int g_spr_meter_bar[];
extern int g_animated_tile_ids[];
extern int g_animated_tile_frames[];
extern int g_sprite_sets[][3][4];
extern struct monsters g_level_monster_init[];
extern unsigned long g_score;
extern unsigned char g_dave_background[];
extern int g_has_gun;
extern int g_gfx_index;
extern int g_got_trophy;
extern int g_has_jetpack;
extern struct hiscore *g_hiscore_buf;
extern struct actor g_actors[];
extern int g_player_x;
extern int g_player_y;
extern int g_lives;
extern char far *g_tileset;
extern int g_current_level;
extern struct shot g_shots[];
extern int g_in_warp_zone;
extern int g_dave_sprite;
extern int g_dave_facing;
extern struct monsters g_monsters;
extern int g_game_over;
extern int g_death_pause;
extern int g_shot_anim_count;
extern int g_jetpack_fuel;
extern int g_jump_pos;
extern int g_quit;
extern int g_prev_dir;
extern int g_scroll_x;
extern int g_demo_pos;
extern char far *g_demo_data;
extern char *g_level;
extern int g_level_visited[];
extern struct entry g_hiscores[];
extern int g_input_dir;
extern int g_dave_mask;
extern int g_jet_facing;
extern struct anim g_anim_tiles[];
extern unsigned long g_next_extra_life;
extern char huge *g_level_path;
extern int g_anim_frame;
extern int g_warp_return_level;
extern int g_fuel_tick;
extern int g_dave_state;
extern int g_level_done;
extern int g_anim_tick_divider;
extern char g_tiles[];
extern char g_demo_repeat;
extern int g_bonus_timer;
extern int g_anim_delay;
extern int g_unused_654a;

/* ---- CONFIG.C data */
extern int g_panel_rows[];
extern int g_panel_cols[];
extern char g_scan_ascii[];
extern int g_have_ega;
extern int g_have_vga;
extern int g_have_joystick;
extern int g_have_joystick2;
extern int g_panel_col;
extern int g_have_mouse;
extern int g_unused_6558[];
extern unsigned g_pic_planes[];
extern int g_panel_avail[][5];
extern int g_saved_video;
extern int g_unused_65da[];
extern int g_saved_sound;
extern struct s32 g_pic_sprites[];
extern int g_cur_video;
extern int g_unused_85fe;
extern int g_saved_control1;
extern int g_saved_control2;
extern struct s16 g_pic_table[];
extern int g_unused_8a04[];
extern int g_cur_sound;
extern int g_panel_row;
extern int g_unused_8a0c;
extern int g_cur_control1;
extern int g_cur_control2;
extern int g_text_x;
extern int g_text_y;
extern char far *g_pic_charptr;
extern char far *g_pic_spriteptr;
extern char far *g_pic_picptr;
extern int g_text_left;

/* ---- HARDWARE.C data */
extern int g_input_device[];
extern int g_joy_xmin[];
extern int g_joy_xmax[];
extern int g_joy_ymin[];
extern int g_joy_ymax[];
extern int g_mouse_deadzone;
extern char g_key_scans[];
extern void interrupt (far *g_old_int9)();
extern int g_win_x1;
extern int g_win_x2;
extern int g_win_y1;
extern int g_win_y2;
extern char *g_demo_ptr;
extern char far *g_pic_tileptr;
extern int g_keydown[];
extern int g_video_mode;
extern char g_demo_buffer[];
extern int g_adapter_type;
extern int g_demo_state;
extern void far *g_alloc_block;

/* ---- data of the hand-written assembly modules (src/asm) */
extern char far *SoundData;     /* lowlevel.asm: far table of sound headers */
extern int SoundEnabled;        /* lowlevel.asm: low byte 0 = speaker muted */
extern int XorMask;             /* lowlevel.asm: XORed into every font pixel */
extern char *LevelPtr;          /* tiles.asm: far pointer to g_levels (offset word) */
extern int RowTimes100[];       /* tiles.asm: row -> row * 100 */

/* ---- the data-only module after the assembly (DS 0x143A..0x493A) */
extern unsigned char g_vga_palette[];   /* 256 x RGB */

/* ---- far data segments (class FAR_DATA, one paragraph-aligned segment each) */
extern char far g_demo_bank[];          /* 0B31: attract-mode demo recordings */
extern char far g_tileset_cga[];        /* 0C42: CGA tileset, RLE-compressed */
extern char far g_tileset_vga[];        /* 11EF: VGA tileset, RLE-compressed */
extern char far g_sound_bank[];         /* 1C2E: PC-speaker sounds (SPK) */
extern char far g_picfile_cga[];        /* 1D58: control-panel picture file, CGA */
extern char far g_picfile_ega[];        /* 1E84: ... EGA */
extern char far g_picfile_vga[];        /* 20CC: ... VGA */

/* ---- assembly routines (src/asm), C calling convention */
void StartSound(void);
void ShutdownSound(void);
void PlaySound(int snd);
void StopSound(void);
void PauseSound(void);
void ResumeSound(void);
void WaitSound(void);
void WaitVBL(void);
void DrawChar(int x, int y, int c);
void DrawPic(int x, int y, int pic);
int VideoID(void);
void RLEExpand(char huge *src, char far *dst, long size);
void InitLevelPtr(void);
void DrawMaskedEGA(int x, int y, int sprite, int mask);
void DrawMaskedVGA(int x, int y, int sprite, int mask);
void DrawMaskedCGA(int x, int y, int sprite, int mask);
void RestoreUnderEGA(void *buf);
void RestoreUnderVGA(void *buf);
void RestoreUnderCGA(void *buf);
void SaveUnderEGA(int x, int y, int mask, void *buf);
void SaveUnderVGA(int x, int y, int mask, void *buf);
void SaveUnderCGA(int x, int y, int mask, void *buf);
void DrawXorEGA(int x, int y, int sprite);
void DrawXorVGA(int x, int y, int sprite);
void DrawXorCGA(int x, int y, int sprite);
void DrawPicEGA(int x, int y, int tile);
void DrawPicVGA(int x, int y, int tile);
void DrawPicCGA(int x, int y, int tile);
void DrawLevelView(void);
void DrawViewBorders(void);
void DrawTile(int x, int y, int tile);
void CacheEGATiles(void);

/* ---- functions */
void main(void);
void quit_game(int code);
void check_high_score(void);
void input_initials(char *name);
void show_high_scores(int flag);
void attract_mode(void);
void draw_inventory(void);
void update_score(void);
void draw_level_number(void);
void ask_restart(void);
void show_help(void);
void ask_quit(void);
void pause_game(void);
void load_graphics(void);
void redraw_screen(void);
void show_cga_picture(void);
void handle_death(void);
void update_jetpack(void);
void spawn_explosion(int x, int y, int type);
void update_explosions(void);
void restore_background(void *buf);
void save_background(int x, int y, int mask, void *buf);
void draw_masked_sprite(int a, int b, int c, int d);
void draw_tile(int a, int b, int c);
void xor_sprite(int a, int b, int c);
void erase_dave(void);
void draw_dave(void);
void move_dave(void);
void animate_tick(void);
int tile_attr_at(int x, int y);
int tile_at(int x, int y);
int tile_attr_at_offset(int x, int y, int dx, int dy);
void move_monsters(void);
void move_bullets(void);
void draw_object(int i);
void animate_tiles(void);
void wait_for_input(void);
void check_warp_transition(void);
void draw_status_meter(void);
void draw_status_bar(void);
void check_collisions(void);
void level_complete(void);
void pick_up_items(void);
void scroll_screen(void);
int find_object(int id);
int object_exists(int id);
void spawn_object(int x, int y, int flag, int kind, int id);
void handle_menu_key(void);
void process_input(void);
void draw_actors(void);
void load_level(void);
void init_game_once(void);
void init_game_state(void);
void calibrate_joystick(int stick);
void config_mouse(void);
void print_key_name(register int key);
void config_keyboard(void);
void detect_hardware(void);
void draw_control_panel(void);
void control_panel(void);
void setup_graphics_pointers(char far *data, int unused);
void ega_upload_planes(void);
void install_keyboard_handler(void);
void interrupt keyboard_isr(void);
void restore_keyboard_handler(void);
struct input read_keyboard_input(void);
struct input read_mouse_input(void);
void read_joystick_axes(int stick, register int *px, register int *py);
struct input read_joystick_input(register int stick);
struct input get_player_input(int player);
void demo_record_start(void);
void demo_play_start(char *name);
void demo_save(char *name);
void flush_keyboard(void);
void far *farmalloc_aligned(unsigned long size);
long read_file_far(char *name, char far *buf);
void write_file_far(char *name, char far *buf, long len);
void far *load_file(char *name);
char far *load_rle_file(char *name);
void set_video_mode(int mode);
void draw_text_window(int x1, int y1, int x2, int y2);
void clear_text_window(void);
void draw_centered_window(int w, int h);
void open_window_anim(register int w, register int h);
void open_window_anim_w(register int w, int h);
void open_window_anim_h(int w, register int h);
int wait_key_cursor(void);
void print_string(char *s);
void print_int(int n);
void print_long(int n);
