/*
 * CONFIG.C -- Dangerous Dave: the control panel and hardware set-up screens.
 *
 * Translation unit 2: 9 functions (calibrate_joystick .. ega_upload_planes),
 * cs [0x51c3,0x6093): joystick / mouse / keyboard configuration, hardware
 * detection, the control panel, and the picture-file set-up it draws with.
 *   _DATA  DS [0x0f02,0x12ef)  panel geometry, scan-code names, then the
 *          string literals (DS 0x0f92..); TLINK pads DS 0x12ef to a word;
 *   _BSS   DS [0x654c,0x8a24).
 * Which unit DEFINES a shared variable is not observable in the bytes; the
 * assignment here is the one that minimises cross-unit-only definitions
 * (docs/link-forensics.md).
 */
/* @at 0x51c3 */
/* @seg _DATA 0x0f02 */
/* @seg _BSS 0x654c */
#include <dos.h>
#include <mem.h>
#include "DAVE.H"

/* ---- initialised data: DS [0x0f02, ...) in definition order */
int g_panel_rows[4] = {4, 9, 14, 19};   /* control panel: text row of each option row */
int g_panel_cols[4] = {14, 20, 26, 32};   /* control panel: text column of each option */
char g_scan_ascii[128] = {'?', '?', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '+', '?',
    '?', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '[', ']', '|',
    '?', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ';', '"', '?', '?',
    '?', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '/', '?', '?', '?',
    '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?',
    '?', '\017', '?', '-', '\025', '5', '\021', '+', '?', '\023', '?', '?',
    '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?',
    '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?',
    '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?', '?',
    '?', '?', '?'};   /* scan code -> printable key name character */
/* initialised data ends at DS 0x0f92; local-aggregate images and the string pool follow */

/* ---- uninitialised data: DS [0x654c, 0x8a24), ordered by the _BSS hash (see DAVE.H) */
int g_have_ega;
int g_have_vga;
int g_have_joystick;   /* 0 none, 1 or 2 */
int g_have_joystick2;
int g_panel_col;   /* control panel cursor column */
int g_have_mouse;
int g_unused_6558[40];   /* never referenced */
unsigned g_pic_planes[4];   /* picture file plane segments */
int g_panel_avail[4][5];   /* option available flags [row][col] */
int g_saved_video;   /* settings on entry to the control panel */
int g_unused_65da[16];   /* never referenced */
int g_saved_sound;
struct s32 g_pic_sprites[256];   /* picture file sprite table */
int g_cur_video;   /* control panel choices */
int g_unused_85fe;   /* never referenced */
int g_saved_control1;
int g_saved_control2;
struct s16 g_pic_table[64];   /* picture file picture table */
int g_unused_8a04[2];   /* never referenced */
int g_cur_sound;
int g_panel_row;   /* control panel cursor row */
int g_unused_8a0c;   /* never referenced */
int g_cur_control1;
int g_cur_control2;
int g_text_x;   /* text cursor column */
int g_text_y;   /* text cursor row */
char far *g_pic_charptr;   /* picture file: 8x8 font */
char far *g_pic_spriteptr;
char far *g_pic_picptr;
int g_text_left;   /* left margin of the text window */

/*
 * calibrate_joystick(stick)
 * cs [0x51c3,0x53bc) / file [0x53c3,0x55bc), 505 bytes.
 *
 * Joystick calibration screen. Prints the "Joystick Configuration" prompt
 * (draw_centered_window positions the text cursor at 24, 9; print_string prints), then
 * asks for the upper-left corner: while waiting, a colour-cycling
 * (15..22) marker is drawn through DrawChar at the text cursor (g_text_x, g_text_y),
 * the raw stick position is sampled by read_joystick_axes into (x1, y1) and the input
 * state by read_joystick_input(stick); fire (button word == 1) accepts, then it waits
 * for release. Same for the lower-right corner (x2, y2). The dead-zone
 * thresholds are set a quarter of the range inside each corner:
 * g_joy_xmin/xmax/ymin/ymax[stick] = x1 + dx, x2 - dx, y1 + dy,
 * y2 - dy. If DS:0x8A34 becomes non-zero (abort) the calibration is
 * skipped. Always ends with flush_keyboard, clear_text_window.
 *
 * Codegen notes: every struct-returning call site gets its own 6-byte
 * temporary (bp-0x18, -0x1E, -0x24, -0x2A). The abort is a `goto` to the
 * shared tail (it skips the threshold stores but not flush_keyboard/clear_text_window).
 */

void calibrate_joystick(int stick)
{
    int dx, dy;
    int x1, y1;
    int x2, y2;
    struct input in;
    int color;

    draw_centered_window(0x18, 9);
    print_string(" Joystick Configuration\n\r");
    print_string(" ----------------------\n\r");
    print_string("Hold the joystick in the\n\r");
    print_string("upper left\n\r");
    print_string("corner and hit fire:");
    color = 15;
    do {
        DrawChar(g_text_x, g_text_y, color);
        WaitVBL();
        WaitVBL();
        WaitVBL();
        if (++color == 0x17)
            color = 15;
        read_joystick_axes(stick, &x1, &y1);
        in = read_joystick_input(stick);
        if (g_keydown[1] != 0)
            goto done;
    } while (in.fire != 1);
    DrawChar(g_text_x, g_text_y, 0x20);
    do {
        in = read_joystick_input(stick);
    } while (in.fire != 0);
    WaitVBL();
    WaitVBL();
    print_string("\n\n\rHold the joystick in the\n\r");
    print_string("lower right\n\r");
    print_string("corner and hit fire:");
    do {
        DrawChar(g_text_x, g_text_y, color);
        WaitVBL();
        WaitVBL();
        WaitVBL();
        if (++color == 0x17)
            color = 15;
        read_joystick_axes(stick, &x2, &y2);
        in = read_joystick_input(stick);
        if (g_keydown[1] != 0)
            goto done;
    } while (in.fire != 1);
    DrawChar(g_text_x, g_text_y, 0x20);
    do {
        in = read_joystick_input(stick);
    } while (in.fire != 0);
    dx = (x2 - x1) / 4;
    dy = (y2 - y1) / 4;
    g_joy_xmin[stick] = x1 + dx;
    g_joy_xmax[stick] = x2 - dx;
    g_joy_ymin[stick] = y1 + dy;
    g_joy_ymax[stick] = y2 - dy;
done:
    flush_keyboard();
    clear_text_window();
}

/*
 * config_mouse
 * cs [0x53bc,0x544d) / file [0x55bc,0x564d), 145 bytes.
 *
 * Mouse configuration screen: opens a 24x5 text window, prints the five
 * 'Mouse Configuration' lines, waits (wait_key_cursor) for a digit 1-9 (ESC counts as
 * '5'), sets the mouse dead-zone/sensitivity g_mouse_deadzone = 15 - digit, clears the
 * window (clear_text_window), then resets the mouse driver (INT 33h AX=0) and centres
 * the cursor (AX=4, CX=320, DX=100).
 *
 * Evidence for the name: strings 'Mouse Configuration'/'Choose the
 * sensitivity', INT 33h calls; g_mouse_deadzone is the threshold used by read_mouse_input.
 *
 * Codegen: String literals land in this module's _DATA at DS:0x1044 in
 * source order.
 */

void config_mouse(void)
{
    char c;

    draw_centered_window(24, 5);
    print_string("  Mouse Configuration   \n\r");
    print_string("  -------------------   \n\r");
    print_string("Choose the sensitivity  \n\r");
    print_string("of the mouse, 1 being   \n\r");
    print_string("slow, 9 being fast:");
    do {
        c = wait_key_cursor() % 256;
        if (c == 27)
            c = '5';
    } while (c < '1' || c > '9');
    g_mouse_deadzone = 15 - (c - '0');
    clear_text_window();
    _AX = 0;
    geninterrupt(0x33);
    _AX = 4;
    _CX = 320;
    _DX = 100;
    geninterrupt(0x33);
}

/*
 * print_key_name
 * cs [0x544d,0x5615) / file [0x564d,0x5815), 456 bytes.
 *
 * Prints the name of a keyboard scan code (bit 7 masked) at the text cursor:
 * named keys (ESC, BKSP, TAB, CTRL, ... NUMLK), F1-F10 as 'F' + itoa(n),
 * otherwise the ASCII char from the scan-code table g_scan_ascii via DrawChar at
 * (g_text_x++, g_text_y). Preserves the original quirk that scan code 0x59 (not
 * 0x58) is labelled F12.
 *
 * Evidence for the name: called by config_keyboard for each configured key;
 * string table of key names.
 *
 * Codegen: `key = key & 0x7f` (not `&=`) gives mov ax,si / and / mov si,ax.
 * Long if/else-if chain = compare chain with near jmps to the epilogue.
 */

void print_key_name(register int key)
{
    char buf[4];

    key = key & 0x7f;
    if (key == 1)
        print_string("ESC");
    else if (key == 14)
        print_string("BKSP");
    else if (key == 15)
        print_string("TAB");
    else if (key == 29)
        print_string("CTRL");
    else if (key == 42)
        print_string("LSHIFT");
    else if (key == 57)
        print_string("SPACE");
    else if (key == 58)
        print_string("CAPSLK");
    else if (key >= 59 && key <= 68) {
        print_string("F");
        itoa(key - 58, buf, 10);
        print_string(buf);
    } else if (key == 87)
        print_string("F11");
    else if (key == 89)
        print_string("F12");
    else if (key == 70)
        print_string("SCRLLK");
    else if (key == 28)
        print_string("ENTER");
    else if (key == 54)
        print_string("RSHIFT");
    else if (key == 55)
        print_string("PRTSC");
    else if (key == 56)
        print_string("ALT");
    else if (key == 71)
        print_string("HOME");
    else if (key == 73)
        print_string("PGUP");
    else if (key == 79)
        print_string("END");
    else if (key == 81)
        print_string("PGDN");
    else if (key == 82)
        print_string("INS");
    else if (key == 83)
        print_string("DEL");
    else if (key == 69)
        print_string("NUMLK");
    else
        DrawChar(g_text_x++, g_text_y, g_scan_ascii[key]);
}

/*
 * config_keyboard
 * cs [0x5615,0x57ec) / file [0x5815,0x59ec), 471 bytes.
 *
 * Keyboard configuration screen: prints the 10 action labels, the currently
 * bound key of each (g_key_scans[0..9]) via print_key_name, then loops: read a
 * digit 0-9 selecting an action, prompt 'Press the new key:', wait for any
 * key in the key-state table g_keydown (scanning 0..127 repeatedly), store its
 * scan code into g_key_scans[action], redraw. Any non-digit leaves the screen.
 *
 * Evidence for the name: strings 'Keyboard Configuration', 'Modify which
 * action:', 'Press the new key:'.
 *
 * Codegen: `if (c < '0' || c > '9') continue;` inside do/while (continue
 * jumps to the loop test). `while (!g_keydown[++key]) if (key == 127) key =
 * -1;`. Redundant `action = c - '0'` kept twice as in the original.
 */

void config_keyboard(void)
{
    char c;
    int savex, savey, key;
    register int action, i;

    draw_centered_window(22, 14);
    print_string("Keyboard Configuration\n\r");
    print_string("----------------------");
    print_string("\n\r0 north    :");
    print_string("\n\r1 northeast:");
    print_string("\n\r2 east     :");
    print_string("\n\r3 southeast:");
    print_string("\n\r4 south    :");
    print_string("\n\r5 southwest:");
    print_string("\n\r6 west     :");
    print_string("\n\r7 northwest:");
    print_string("\n\r8 button1  :");
    print_string("\n\r9 button2  :");
    print_string("\n\n\rModify which action:");
    savex = g_text_x;
    savey = g_text_y;
    for (i = 0; i < 8; i++) {
        g_text_x = 22;
        g_text_y = i + 7;
        print_key_name(g_key_scans[i]);
    }
    g_text_x = 22;
    g_text_y = 15;
    print_key_name(g_key_scans[8]);
    g_text_x = 22;
    g_text_y = 16;
    print_key_name(g_key_scans[9]);
    do {
        g_text_x = savex;
        g_text_y = savey;
        c = wait_key_cursor() % 256;
        if (c < '0' || c > '9')
            continue;
        action = c - '0';
        DrawChar(g_text_x, g_text_y, c);
        action = c - '0';
        print_string("\n\rPress the new key:");
        flush_keyboard();
        key = -1;
        while (!g_keydown[++key])
            if (key == 127)
                key = -1;
        flush_keyboard();
        print_string("\r                  ");
        if (action < 8)
            g_key_scans[action] = key;
        if (action == 8)
            g_key_scans[8] = key;
        if (action == 9)
            g_key_scans[9] = key;
        g_text_y = action + 7;
        g_text_x = 22;
        print_string("        ");
        g_text_x = 22;
        print_key_name(key);
        c = '0';
    } while (c >= '0' && c <= '9');
    clear_text_window();
}

/*
 * detect_hardware
 * cs [0x57ec,0x5910) / file [0x59ec,0x5b10), 292 bytes.
 *
 * Builds the control-panel availability tables: EGA/VGA flags from adapter
 * type g_adapter_type (3/5 => EGA, 5/4 => VGA), fills video/sound row g_panel_avail[0][0..9],
 * probes joysticks 1 and 2 with read_joystick_axes (x < 500 => present), and
 * detects a mouse driver (INT 33h vector non-NULL and its first byte not
 * IRET 0xCF); fills control row g_panel_avail[2][0..4].
 *
 * Evidence for the name: INT 33h vector check, joystick probe, consumer
 * draw_control_panel/control_panel (option grid g_panel_avail[0][3][5]).
 *
 * Codegen: `(*(int far *)v & 0xff) == 0xcf` gives les bx / mov ax,es:[bx] /
 * and ax,0xff.
 */

void detect_hardware(void)
{
    int x, y;
    void interrupt (far *v)();

    g_have_ega = 0;
    g_have_vga = 0;
    if (g_adapter_type == 3 || g_adapter_type == 5)
        g_have_ega = 1;
    if (g_adapter_type == 5 || g_adapter_type == 4)
        g_have_vga = 1;
    g_panel_avail[0][0] = 1;
    g_panel_avail[0][1] = g_have_ega;
    g_panel_avail[0][2] = g_have_vga;
    g_panel_avail[0][3] = 0;
    g_panel_avail[0][4] = 0;
    g_panel_avail[0][5] = 1;
    g_panel_avail[0][6] = 1;
    g_panel_avail[0][7] = 0;
    g_panel_avail[0][8] = 0;
    g_panel_avail[0][9] = 0;
    g_have_joystick = 0;
    g_have_joystick2 = 0;
    read_joystick_axes(1, &x, &y);
    if (x < 500)
        g_have_joystick = 1;
    read_joystick_axes(2, &x, &y);
    if (x < 500)
        g_have_joystick = 2;
    g_have_mouse = 1;
    v = getvect(0x33);
    if (v == 0)
        g_have_mouse = 0;
    else if ((*(int far *)v & 0xff) == 0xcf)
        g_have_mouse = 0;
    g_panel_avail[2][0] = 1;
    g_panel_avail[2][1] = g_have_mouse;
    g_panel_avail[2][2] = g_have_joystick;
    g_panel_avail[2][3] = g_have_joystick2;
    g_panel_avail[2][4] = 0;
}

/*
 * draw_control_panel
 * cs [0x5910,0x5bd5) / file [0x5b10,0x5dd5), 709 bytes.
 *
 * Draws the 'PC-Arcade Control Panel' screen: VIDEO/SOUND/CONTROL rows of
 * option icons via DrawPic(col*8, row*8, icon) (greyed variants when hardware
 * is unavailable), a marker char 15 next to the current video
 * mode/sound/control choice, and the three help lines.
 *
 * Evidence for the name: strings 'PC-Arcade Control Panel', 'VIDEO:',
 * 'SOUND:', 'CONTROL:'.
 *
 * Codegen: Rows g_panel_rows[0..2] and columns g_panel_cols[0..3]; `g_panel_cols[g_cur_video - 1]`
 * folds to [bx+0xf08].
 */

void draw_control_panel(void)
{
    g_text_left = 1;
    XorMask = 0;
    g_text_x = 8;
    g_text_y = 2;
    print_string("PC-Arcade Control Panel\n\r");
    detect_hardware();

    g_text_y = g_panel_rows[0] + 2;
    g_text_x = 2;
    print_string("VIDEO:");
    DrawPic(g_panel_cols[0] * 8, g_panel_rows[0] * 8, 0);
    if (g_have_ega)
        DrawPic(g_panel_cols[1] * 8, g_panel_rows[0] * 8, 1);
    else
        DrawPic(g_panel_cols[1] * 8, g_panel_rows[0] * 8, 3);
    if (g_have_vga)
        DrawPic(g_panel_cols[2] * 8, g_panel_rows[0] * 8, 2);
    else
        DrawPic(g_panel_cols[2] * 8, g_panel_rows[0] * 8, 4);

    g_text_y = g_panel_rows[1] + 2;
    g_text_x = 2;
    print_string("SOUND:");
    DrawPic(g_panel_cols[0] * 8, g_panel_rows[1] * 8, 5);
    DrawPic(g_panel_cols[1] * 8, g_panel_rows[1] * 8, 6);

    g_text_y = g_panel_rows[2] + 2;
    g_text_x = 2;
    print_string("CONTROL:");
    DrawPic(g_panel_cols[0] * 8, g_panel_rows[2] * 8, 7);
    if (g_have_mouse)
        DrawPic(g_panel_cols[1] * 8, g_panel_rows[2] * 8, 10);
    else
        DrawPic(g_panel_cols[1] * 8, g_panel_rows[2] * 8, 12);
    if (g_have_joystick)
        DrawPic(g_panel_cols[2] * 8, g_panel_rows[2] * 8, 8);
    else
        DrawPic(g_panel_cols[2] * 8, g_panel_rows[2] * 8, 11);
    if (g_have_joystick2)
        DrawPic(g_panel_cols[3] * 8, g_panel_rows[2] * 8, 9);
    else
        DrawPic(g_panel_cols[3] * 8, g_panel_rows[2] * 8, 11);

    DrawChar(g_panel_cols[g_cur_video - 1] + 1, g_panel_rows[0] + 3, 15);
    DrawChar(g_panel_cols[g_cur_sound] + 1, g_panel_rows[1] + 3, 15);
    DrawChar(g_panel_cols[g_cur_control1] + 1, g_panel_rows[2] + 3, 15);
    g_text_y = 21;
    g_text_x = 1;
    print_string("  Move the cursor with the arrow keys \n\r");
    print_string("   Make decisions with the ENTER key  \n\r");
    print_string("       ESC to return to your game     \n\r");
}

/*
 * control_panel
 * cs [0x5bd5,0x5e99) / file [0x5dd5,0x6099), 708 bytes.
 *
 * Control-panel main loop (F2 menu): saves current settings, sets the video
 * mode, draws the panel, then moves a cursor over the option grid with the
 * arrow keys (skipping unavailable options), ENTER applies the option (video
 * mode switch incl. EGA plane upload, sound choice, control choice which
 * runs the keyboard/mouse/joystick configuration screens), ESC writes the
 * choices back (g_input_device[1] control, g_video_mode video, SoundEnabled sound) and returns.
 *
 * Evidence for the name: arrow scan codes 0x48/0x50/0x4B/0x4D, calls
 * config_keyboard/config_mouse/calibrate_joystick(joystick), draw_control_panel.
 *
 * Codegen: Chained assignments `g_cur_video = g_saved_video = g_video_mode` store the inner
 * target first. `while (!g_panel_avail[r][--c]);` gives the empty-body while (eb
 * 00). `if (--g_panel_row < 0)` uses the dec flags directly, `if (++g_panel_row > 2)`
 * reloads.
 */

void control_panel(void)
{
    char ascii, scan;
    register int key;

    flush_keyboard();
    PauseSound();
    g_cur_video = g_saved_video = g_video_mode;
    g_cur_sound = g_saved_sound = SoundEnabled;
    g_cur_control1 = g_saved_control1 = g_input_device[1];
    g_cur_control2 = g_saved_control2 = g_input_device[2];
    set_video_mode(g_video_mode);
    draw_text_window(0, 0, 39, 24);
    draw_control_panel();
    g_panel_row = 0;
    g_panel_col = g_video_mode - 1;
    do {
        g_text_x = g_panel_cols[g_panel_col] + 2;
        g_text_y = g_panel_rows[g_panel_row] + 3;
        key = wait_key_cursor();
        ascii = key % 256;
        scan = key / 256;
        if (scan == 0x48) {
            if (--g_panel_row < 0)
                g_panel_row = 2;
        }
        if (scan == 0x50) {
            if (++g_panel_row > 2)
                g_panel_row = 0;
        }
        while (!g_panel_avail[g_panel_row][g_panel_col])
            g_panel_col--;
        if (scan == 0x4b) {
            if (g_panel_col == 0)
                g_panel_col = 4;
            while (!g_panel_avail[g_panel_row][--g_panel_col])
                ;
        }
        if (scan == 0x4d) {
            while (!g_panel_avail[g_panel_row][++g_panel_col] || g_panel_col > 3)
                if (g_panel_col == 4)
                    g_panel_col = -1;
        }
        if (ascii == 13) {
            switch (g_panel_row) {
            case 0:
                if (g_panel_col + 1 == g_cur_video)
                    break;
                DrawChar(g_panel_cols[g_cur_video - 1] + 1, g_panel_rows[g_panel_row] + 3, ' ');
                g_video_mode = g_cur_video = g_panel_col + 1;
                load_graphics();
                set_video_mode(g_video_mode);
                if (g_video_mode == 2)
                    ega_upload_planes();
                draw_text_window(0, 0, 39, 24);
                draw_control_panel();
                break;
            case 1:
                DrawChar(g_panel_cols[g_cur_sound] + 1, g_panel_rows[g_panel_row] + 3, ' ');
                g_cur_sound = g_panel_col;
                break;
            case 2:
                DrawChar(g_panel_cols[g_cur_control1] + 1, g_panel_rows[g_panel_row] + 3, ' ');
                g_cur_control1 = g_panel_col;
                if (g_cur_control1 == 0)
                    config_keyboard();
                else if (g_cur_control1 == 1)
                    config_mouse();
                else if (g_cur_control1 == 2)
                    calibrate_joystick(1);
                else if (g_cur_control1 == 3)
                    calibrate_joystick(2);
                draw_control_panel();
                break;
            }
            DrawChar(g_panel_cols[g_panel_col] + 1, g_panel_rows[g_panel_row] + 3, 15);
        }
    } while (ascii != 27);
    g_input_device[1] = g_cur_control1;
    g_input_device[2] = g_cur_control2;
    g_video_mode = g_cur_video;
    SoundEnabled = g_cur_sound;
    redraw_screen();
    ResumeSound();
}

/*
 * setup_graphics_pointers
 * cs [0x5e99,0x6013) / file [0x6099,0x6213), 378 bytes.
 *
 * Takes a loaded graphics file (header of far pointers relative to the file)
 * and derives runtime pointers: on EGA copies the four tile pointers and
 * computes the 4 plane segments g_pic_planes[i]; otherwise relocates the four
 * pointers to MK_FP(seg(file)+seg(ptr), 0). Then copies 64 16-byte and 256
 * 32-byte records (huge pointers into the file) to g_pic_table and g_pic_sprites.
 *
 * Evidence for the name: EGA plane segments g_pic_planes are consumed by ega_upload_planes;
 * huge-pointer struct copies via N_PADD@/N_SCOPY@.
 *
 * Codegen: Huge pointers give N_LXLSH@ + N_PADD@ for indexing. MK_FP(seg,
 * off) evaluates seg first.
 */

void setup_graphics_pointers(char far *data, int unused)
{
    struct gfxhdr far *hdr;
    struct s32 huge *p32;
    struct s16 huge *p16;
    register int i;

    hdr = (struct gfxhdr far *)data;
    if (g_video_mode == 2) {
        g_pic_charptr = hdr->p0;
        g_pic_tileptr = hdr->p1;
        g_pic_picptr = hdr->p2;
        g_pic_spriteptr = hdr->p3;
        for (i = 0; i < 4; i++)
            g_pic_planes[i] = FP_SEG(hdr->plane[i]) + FP_SEG(hdr);
    } else {
        g_pic_charptr = MK_FP(FP_SEG(hdr) + FP_SEG(hdr->p0), 0);
        g_pic_tileptr = MK_FP(FP_SEG(hdr) + FP_SEG(hdr->p1), 0);
        g_pic_picptr = MK_FP(FP_SEG(hdr) + FP_SEG(hdr->p2), 0);
        g_pic_spriteptr = MK_FP(FP_SEG(hdr) + FP_SEG(hdr->p3), 0);
    }
    p16 = MK_FP(FP_SEG(hdr->s16) + FP_SEG(hdr), FP_OFF(hdr->s16) + FP_OFF(hdr));
    p32 = MK_FP(FP_SEG(hdr->s32) + FP_SEG(hdr), FP_OFF(hdr->s32) + FP_OFF(hdr));
    for (i = 0; i < 64; i++)
        g_pic_table[i] = p16[i];
    for (i = 0; i < 256; i++)
        g_pic_sprites[i] = p32[i];
}

/*
 * ega_upload_planes
 * cs [0x6013,0x6093) / file [0x6213,0x6293), 128 bytes.
 *
 * Copies the four EGA tile planes (segments g_pic_planes[0..3], size (g_pic_planes[1] -
 * g_pic_planes[0]) paragraphs) into video memory at A200:0000, selecting each
 * plane with sequencer map mask (3C4h index 2), then re-enables all four
 * planes.
 *
 * Evidence for the name: outportb 0x3C4/0x3C5 map mask, movedata to segment
 * 0xA200; called after setting EGA mode.
 *
 * Codegen: `int i` stays on the stack (no auto register allocation here).
 */

void ega_upload_planes(void)
{
    int i;

    for (i = 0; i < 4; i++) {
        outportb(0x3c4, 2);
        outportb(0x3c5, 1 << i);
        movedata(g_pic_planes[i], 0, 0xa200, 0, (g_pic_planes[1] - g_pic_planes[0]) << 4);
    }
    outportb(0x3c4, 2);
    outportb(0x3c5, 0xf);
}

