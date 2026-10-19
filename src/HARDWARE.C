/*
 * HARDWARE.C -- Dangerous Dave: keyboard, input devices, demo recording,
 * files and text windows.
 *
 * Translation unit 3: 28 functions (install_keyboard_handler .. print_long),
 * cs [0x6093,0x6f25). Three functions contain inline `asm`, so TCC compiles
 * the whole unit through TASM ("Restarting compile using assembly"); the
 * original went the same way, and the C parts come out identical.
 *   _DATA  DS [0x12f0,0x132d)  input-device defaults and calibration, key
 *          scan codes, the saved INT 9 vector, then "Out of memory!";
 *          TLINK pads DS 0x132d before lowlevel.asm's _DATA;
 *   _BSS   DS [0x8a24,0x9ec8), the last game _BSS before CS.LIB's.
 */
/* @at 0x6093 */
/* @seg _DATA 0x12f0 */
/* @seg _BSS 0x8a24 */
#include <dos.h>
#include <bios.h>
#include <stdio.h>
#include <alloc.h>
#include <io.h>
#include <fcntl.h>
#include "DAVE.H"

/* ---- initialised data: DS [0x12f0, ...) in definition order */
int g_input_device[3] = {0, 0, 2};   /* per player 1..2: 0 keyboard, 1 mouse, 2/3 joystick 1/2 */
int g_joy_xmin[3] = {20, 20, 0};   /* per stick 1..2: calibrated dead-zone limits */
int g_joy_xmax[3] = {60, 60, 0};
int g_joy_ymin[3] = {20, 20, 0};
int g_joy_ymax[3] = {50, 50, 0};
int g_mouse_deadzone = 5;   /* mouse threshold (15 - sensitivity) */
char g_key_scans[10] = {0x48, 0x49, 0x4d, 0x51, 0x50, 0x4f, 0x4b, 0x47, 0x1d, 0x38};   /* scan codes: 8 directions N..NW, then fire, jump */
void interrupt (far *g_old_int9)() = 0;   /* BIOS keyboard handler saved by install_keyboard_handler */
/* initialised data ends at DS 0x131e; local-aggregate images and the string pool follow */

/* ---- uninitialised data: DS [0x8a24, 0x9ec8), ordered by the _BSS hash (see DAVE.H) */
int g_win_x1;   /* text window rectangle */
int g_win_x2;
int g_win_y1;
int g_win_y2;
char *g_demo_ptr;   /* demo buffer read/write pointer */
char far *g_pic_tileptr;
int g_keydown[128];   /* key state per scan code */
int g_video_mode;   /* 1 CGA, 2 EGA, 3 VGA */
char g_demo_buffer[5004];
int g_adapter_type;   /* VideoID result */
int g_demo_state;   /* 0 live, 1 playback, 2 record */
void far *g_alloc_block;   /* last farmalloc block */

/*
 * install_keyboard_handler
 * cs [0x6093,0x610b) / file [0x6293,0x630b), 120 bytes.
 *
 * Reads the INT 9 vector, clears the key-state table g_keydown[128], flushes
 * the BIOS keyboard buffer (head = tail at 0040:001A/1C) and, unless the
 * handler is already ours, saves the old vector in g_old_int9 and installs
 * keyboard_isr.
 *
 * Evidence for the name: getvect/setvect(9); far pointer to keyboard_isr uses MZ
 * relocations at load-module 0x60DC/0x60F5.
 *
 * Codegen: Comparing a far function pointer with keyboard_isr gives cmp [bp-2],SEG
 * / cmp [bp-4],OFF.
 */

void install_keyboard_handler(void)
{
    void interrupt (far *v)();
    register int i;

    v = getvect(9);
    for (i = 0; i < 128; i++)
        g_keydown[i] = 0;
    poke(0x40, 0x1c, peek(0x40, 0x1a));
    if (v != keyboard_isr) {
        g_old_int9 = v;
        setvect(9, keyboard_isr);
    }
}

/*
 * keyboard_isr (INT 9 handler)
 * cs [0x610b,0x6188) / file [0x630b,0x6388), 125 bytes. EXACT (strict).
 *
 * Reads the scan code from port 60h. A break code (> 0x7F) clears
 * key_down[key - 0x80]; a make code sets key_down[key] = 1 and empties the
 * BIOS keyboard buffer (0040:001C = 0040:001A). Then chains to the old INT 9
 * handler (g_old_int9, saved by install_keyboard_handler) and acknowledges the PIC
 * (outport(0x20, 0x20)).
 *
 * Original inline asm: the explicit `push ax..bp` / `pop bp..ax` around the
 * chained call cannot come from C (TC emits only `pushf; call far [old]`).
 * It also explains why `key` lives at [bp-2] and not in SI: TC does no
 * register allocation in a function that contains `asm` statements.
 */

void interrupt keyboard_isr(void)
{
    int key;

    key = inportb(0x60);
    if (key > 0x7f)
        g_keydown[key - 0x80] = 0;
    else {
        g_keydown[key] = 1;
        poke(0x40, 0x1c, peek(0x40, 0x1a));
    }
    asm push ax
    asm push bx
    asm push cx
    asm push dx
    asm push si
    asm push di
    asm push bp
    (*g_old_int9)();
    asm pop bp
    asm pop di
    asm pop si
    asm pop dx
    asm pop cx
    asm pop bx
    asm pop ax
    outport(0x20, 0x20);
}

/*
 * restore_keyboard_handler
 * cs [0x6188,0x61af) / file [0x6388,0x63af), 39 bytes.
 *
 * Restores the saved INT 9 vector g_old_int9.
 *
 * Evidence for the name: setvect(9, g_old_int9).
 *
 * Codegen: The original tests the ADDRESS of g_old_int9 (mov ax,0x131a / or
 * ax,ax), reproduced as `if (&g_old_int9)`.
 */

void restore_keyboard_handler(void)
{
    if (&g_old_int9)
        setvect(9, g_old_int9);
}

/*
 * read_keyboard_input
 * cs [0x61af,0x6305) / file [0x63af,0x6505), 342 bytes.
 *
 * Returns the player input struct {dir, fire, jump} from the key-state
 * table: 8 configurable direction keys g_key_scans[0..7] (diagonals override),
 * dir encoded 0..7 clockwise from north, 8 = none; fire/jump from keys
 * g_key_scans[8], g_key_scans[9].
 *
 * Evidence for the name: uses the remappable key table g_key_scans edited by
 * config_keyboard.
 *
 * Codegen: Struct return: hidden far destination at [bp+4], copied with
 * N_SCOPY@. switch over dy*3+dx with cases -4..4 -> jump table. `register
 * int dx, dy;` gives dy=SI, dx=DI.
 */

struct input read_keyboard_input(void)
{
    struct input in;
    register int dx, dy;

    dx = 0;
    dy = 0;
    if (g_keydown[g_key_scans[0]])
        dy = -1;
    if (g_keydown[g_key_scans[2]])
        dx = 1;
    if (g_keydown[g_key_scans[4]])
        dy = 1;
    if (g_keydown[g_key_scans[6]])
        dx = -1;
    if (g_keydown[g_key_scans[1]]) {
        dy = -1;
        dx = 1;
    }
    if (g_keydown[g_key_scans[7]]) {
        dy = -1;
        dx = -1;
    }
    if (g_keydown[g_key_scans[3]]) {
        dy = 1;
        dx = 1;
    }
    if (g_keydown[g_key_scans[5]]) {
        dy = 1;
        dx = -1;
    }
    switch (dy * 3 + dx) {
    case -4: in.dir = 7; break;
    case -3: in.dir = 0; break;
    case -2: in.dir = 1; break;
    case -1: in.dir = 6; break;
    case 0: in.dir = 8; break;
    case 1: in.dir = 2; break;
    case 2: in.dir = 5; break;
    case 3: in.dir = 4; break;
    case 4: in.dir = 3; break;
    }
    in.fire = g_keydown[g_key_scans[8]];
    in.jump = g_keydown[g_key_scans[9]];
    return in;
}

/*
 * read_mouse_input
 * cs [0x6305,0x644b) / file [0x6505,0x664b), 326 bytes.
 *
 * Mouse version of the input reader: INT 33h AX=3 position/buttons,
 * direction from displacement of the cursor from the centre (320,100) beyond
 * the dead zone g_mouse_deadzone, then re-centres partly (AX=4).
 *
 * Evidence for the name: INT 33h; same {dir, fire, jump} struct and
 * direction table as read_keyboard_input.
 *
 * Codegen: `x = x - g_mouse_deadzone * 2` (not -=) gives mov dx,di / sub dx,ax / mov
 * di,dx.
 */

struct input read_mouse_input(void)
{
    int dx, dy;
    struct input in;
    register int x, y;

    dx = 0;
    dy = 0;
    _AX = 3;
    geninterrupt(0x33);
    x = _CX;
    y = _DX;
    in.fire = _BX & 1;
    in.jump = (_BX & 2) >> 1;
    if ((x - 320) / 2 > g_mouse_deadzone) {
        dx = 1;
        x = x - g_mouse_deadzone * 2;
    } else if ((x - 320) / 2 < -g_mouse_deadzone) {
        dx = -1;
        x = x + g_mouse_deadzone * 2;
    }
    if (y - 100 > g_mouse_deadzone) {
        dy = 1;
        y = y - g_mouse_deadzone;
    } else if (y - 100 < -g_mouse_deadzone) {
        dy = -1;
        y = y + g_mouse_deadzone;
    }
    _AX = 4;
    _CX = x;
    _DX = y;
    geninterrupt(0x33);
    switch (dy * 3 + dx) {
    case -4: in.dir = 7; break;
    case -3: in.dir = 0; break;
    case -2: in.dir = 1; break;
    case -1: in.dir = 6; break;
    case 0: in.dir = 8; break;
    case 1: in.dir = 2; break;
    case 2: in.dir = 5; break;
    case 3: in.dir = 4; break;
    case 4: in.dir = 3; break;
    }
    return in;
}

/*
 * read_joystick_axes
 * cs [0x644b,0x64f2) / file [0x664b,0x66f2), 167 bytes.
 *
 * Reads the game-port (201h) timing of joystick 1 (bits 0/1) or 2 (bits
 * 2/3): triggers the one-shots, then counts with interrupts disabled until
 * both axis bits drop or a count reaches 500.
 *
 * Evidence for the name: port 0x201, cli/sti, limit 500 shared with
 * detect_hardware.
 *
 * Codegen: `(v & mask) != 0` -> test/je/mov ax,1/xor ax,ax.
 */

void read_joystick_axes(int stick, register int *px, register int *py)
{
    int v, xbit, ybit, xmask, ymask;

    if (stick == 1) {
        xmask = 1;
        ymask = 2;
    } else {
        xmask = 4;
        ymask = 8;
    }
    *px = 0;
    *py = 0;
    outportb(0x201, inportb(0x201));
    disable();
    do {
        v = inportb(0x201);
        xbit = (v & xmask) != 0;
        ybit = (v & ymask) != 0;
        *px += xbit;
        *py += ybit;
    } while (xbit + ybit && *px < 500 && *py < 500);
    enable();
}

/*
 * read_joystick_input
 * cs [0x64f2,0x668c) / file [0x66f2,0x688c), 410 bytes.
 *
 * Joystick input reader: axis counts compared with calibration limits
 * g_joy_xmin/g_joy_xmax (x) and g_joy_ymin/g_joy_ymax (y) per stick, out-of-range readings
 * replaced by min+1, direction from the switch table, buttons from port 201h
 * bits (stick 1: 0x10/0x20, stick 2: 0x40/0x80, active low).
 *
 * Evidence for the name: calibration arrays indexed by stick, port 0x201.
 *
 * Codegen: `(x > 500) | (y > 500)` (bitwise or of two comparisons) gives
 * push/pop dx/or dx,ax.
 */

struct input read_joystick_input(register int stick)
{
    int x, y, dx, dy;
    struct input in;
    register int b;

    x = 0;
    y = 0;
    dx = 0;
    dy = 0;
    read_joystick_axes(stick, &x, &y);
    if ((x > 500) | (y > 500)) {
        x = g_joy_xmin[stick] + 1;
        y = g_joy_ymin[stick] + 1;
    }
    if (g_joy_xmax[stick] < x)
        dx = 1;
    else if (g_joy_xmin[stick] > x)
        dx = -1;
    if (g_joy_ymax[stick] < y)
        dy = 1;
    else if (g_joy_ymin[stick] > y)
        dy = -1;
    switch (dy * 3 + dx) {
    case -4: in.dir = 7; break;
    case -3: in.dir = 0; break;
    case -2: in.dir = 1; break;
    case -1: in.dir = 6; break;
    case 0: in.dir = 8; break;
    case 1: in.dir = 2; break;
    case 2: in.dir = 5; break;
    case 3: in.dir = 4; break;
    case 4: in.dir = 3; break;
    }
    b = inportb(0x201);
    if (stick == 1) {
        in.fire = (b & 0x10) == 0;
        in.jump = (b & 0x20) == 0;
    } else {
        in.fire = (b & 0x40) == 0;
        in.jump = (b & 0x80) == 0;
    }
    return in;
}

/*
 * get_player_input
 * cs [0x668c,0x67b9) / file [0x688c,0x69b9), 301 bytes.
 *
 * Input dispatcher: in live (g_demo_state 0) or record (2) mode reads the device
 * selected by g_input_device[player] (0 keyboard, 1 mouse, 2/3 joystick 1/2); in
 * record mode appends a packed byte dir<<2|jump<<1|fire to the demo buffer
 * g_demo_ptr. In playback mode (1) unpacks the next demo byte. Preserves the
 * original bug that playback sets BOTH fire and jump from bit 0.
 *
 * Evidence for the name: demo buffer pointer g_demo_ptr set by demo_record_start/demo_play_start;
 * mode g_demo_state.
 *
 * Codegen: Struct-returning calls go through compiler temporaries +
 * N_SCOPY@.
 */

struct input get_player_input(int player)
{
    struct input in;
    int packed;

    if (g_demo_state == 0 || g_demo_state == 2) {
        switch (g_input_device[player]) {
        case 0: in = read_keyboard_input(); break;
        case 1: in = read_mouse_input(); break;
        case 2: in = read_joystick_input(1); break;
        case 3: in = read_joystick_input(2); break;
        }
        if (g_demo_state == 2) {
            packed = in.dir << 2 | in.jump << 1 | in.fire;
            *g_demo_ptr = packed;
            g_demo_ptr++;
        }
    } else {
        packed = *g_demo_ptr;
        g_demo_ptr++;
        in.fire = packed & 1;
        in.jump = packed & 1;
        in.dir = (packed & 0x3c) >> 2;
    }
    return in;
}

/*
 * demo_record_start
 * cs [0x67b9,0x67d3) / file [0x69b9,0x69d3), 26 bytes.
 *
 * Starts demo recording: buffer pointer g_demo_ptr = g_demo_buffer, mode g_demo_state = 2.
 *
 * Evidence for the name: consumer get_player_input.
 */

void demo_record_start(void)
{
    g_demo_ptr = g_demo_buffer;
    g_demo_state = 2;
}

/*
 * demo_play_start
 * cs [0x67d3,0x67fb) / file [0x69d3,0x69fb), 40 bytes.
 *
 * Loads a demo file into g_demo_buffer (read_file_far) and starts playback (g_demo_state = 1).
 *
 * Evidence for the name: consumer get_player_input.
 *
 * Codegen: The far argument is written `(char far *)(long)g_demo_buffer`: this
 * reproduces `mov ax,OFF; push ds; push ax`; a plain near->far conversion
 * pushes ds before loading the offset.
 */

void demo_play_start(char *name)
{
    read_file_far(name, (char far *)(long)g_demo_buffer);
    g_demo_ptr = g_demo_buffer;
    g_demo_state = 1;
}

/*
 * demo_save
 * cs [0x67fb,0x6826) / file [0x69fb,0x6a26), 43 bytes.
 *
 * Writes the recorded demo (g_demo_buffer .. g_demo_ptr) to a file with write_file_far and
 * stops recording (g_demo_state = 0).
 *
 * Codegen: Same `(char far *)(long)` far-argument form as demo_play_start;
 * the pointer difference is converted to long (cwd).
 */

void demo_save(char *name)
{
    write_file_far(name, (char far *)(long)g_demo_buffer, g_demo_ptr - g_demo_buffer);
    g_demo_state = 0;
}

/*
 * flush_keyboard
 * cs [0x6826,0x6862) / file [0x6a26,0x6a62), 60 bytes.
 *
 * Drains the BIOS keyboard buffer (bioskey) and clears the key-state table
 * g_keydown.
 */

void flush_keyboard(void)
{
    register int i;

    while (bioskey(1))
        bioskey(0);
    for (i = 0; i < 128; i++)
        g_keydown[i] = 0;
}

/*
 * farmalloc_aligned
 * cs [0x6862,0x68de) / file [0x6a62,0x6ade), 124 bytes.
 *
 * farmalloc(size + 15), remembered in g_alloc_block; on failure restores text mode
 * and prints 'Out of memory!' then exits via quit_game(1); returns the block
 * rounded up to a paragraph boundary (offset 0).
 *
 * Evidence for the name: string 'Out of memory!' (DS:0x131E), farmalloc.
 *
 * Codegen: The pointer is `huge` (NULL test via N_PCMP@). Normalisation
 * written as separate statements on register vars: `off = FP_OFF(p); if
 * (off) { seg = FP_SEG(p); seg++; off = 0; p = MK_FP(seg, off); }`.
 */

void far *farmalloc_aligned(unsigned long size)
{
    void huge *p;
    register unsigned seg, off;

    g_alloc_block = p = farmalloc(size + 15);
    if (p == NULL) {
        set_video_mode(0);
        puts("Out of memory!");
        quit_game(1);
    }
    off = FP_OFF(p);
    if (off) {
        seg = FP_SEG(p);
        seg++;
        off = 0;
        p = MK_FP(seg, off);
    }
    return p;
}

/*
 * read_file_far(name, buf) -> file size
 * cs [0x68de,0x6994) / file [0x6ade,0x6b94), 182 bytes. EXACT (strict).
 *
 * Opens `name` (INT 21h AH=3Dh), seeks to the end (AX=4202h) for the size,
 * then reads the file into the far buffer in 0xFFFF-byte chunks (DS
 * switched to the buffer segment, segment advanced by 0x1000 per chunk,
 * plus a final 1-byte read at offset-1 of each full chunk), closes it and
 * returns the size (0 if the open failed). Callers: demo_play_start demo load,
 * load_file/load_rle_file file loaders, init_game_once high scores, load_graphics EGADAVE.DAV.
 *
 * Evidence of ORIGINAL inline asm (not a matching device): `jb` directly
 * after `int 21h`, `loop`, `push ds/mov ds,ax/pop ds` and `add dx,0ffffh`
 * encoded as 83 C2 FF -- none generated by TC 1.00 from C -- inside a
 * compiled C frame (-N stack check, C locals, C return expression).
 * TCC 1.00 compiles such a file by restarting through TASM ("Restarting
 * compile using assembly"); tools/tcc.py puts the pinned TASM on PATH.
 */

long read_file_far(char *name, char far *buf)
{
    int handle;
    unsigned lo = 0;
    unsigned hi = 0;
    unsigned off = FP_OFF(buf);
    unsigned seg = FP_SEG(buf);
    unsigned poslo = 0;
    unsigned poshi = 0;

    asm mov dx, name
    asm mov ax, 3d00h
    asm int 21h
    asm jb done
    asm mov handle, ax
    asm mov bx, ax
    asm xor cx, cx
    asm xor dx, dx
    asm mov ax, 4202h
    asm int 21h
    asm jb done
    asm mov lo, ax
    asm mov hi, dx
    asm mov cx, hi
    asm inc cx
next:
    asm push cx
    asm mov cx, poshi
    asm mov dx, poslo
    asm mov ax, 4200h
    asm int 21h
    asm push ds
    asm mov bx, handle
    asm mov cx, 0ffffh
    asm mov dx, off
    asm mov ax, seg
    asm mov ds, ax
    asm mov ah, 3fh
    asm int 21h
    asm pop ds
    asm pop cx
    asm jb done
    asm cmp ax, 0ffffh
    asm jne done
    asm push cx
    asm push ds
    asm mov bx, handle
    asm mov cx, 1
    asm mov dx, off
    asm add dx, 0ffffh
    asm mov ax, seg
    asm mov ds, ax
    asm mov ah, 3fh
    asm int 21h
    asm pop ds
    asm pop cx
    asm add seg, 1000h
    asm inc poshi
    asm loop next
done:
    asm mov bx, handle
    asm mov ah, 3eh
    asm int 21h
    return ((long)hi << 16) + lo;
}

/*
 * write_file_far(name, buf, len)
 * cs [0x6994,0x6a1e) / file [0x6b94,0x6c1e), 138 bytes. EXACT (strict).
 *
 * Creates `name` (INT 21h AH=3Ch), writes `len` bytes from the far buffer
 * in 0x8000-byte chunks (buffer segment advanced by 0x800 each) and then
 * the remainder, and closes it. Used for DSCORES.DAV and demo saving.
 * The two locals initialised to 0 are never used (kept: they are in the
 * original frame).
 *
 * Original inline asm (see read_file_far.c). The `eb 00` before `done:` is the
 * compiled `goto done;` -- with no jump optimisation TC emits the jump even
 * to the next statement.
 */

void write_file_far(char *name, char far *buf, long len)
{
    int handle;
    unsigned off = FP_OFF(buf);
    unsigned seg = FP_SEG(buf);
    unsigned poslo = 0;
    unsigned poshi = 0;

    asm mov dx, name
    asm mov ax, 3c00h
    asm xor cx, cx
    asm int 21h
    asm jb done
    asm mov handle, ax
    asm cmp word ptr len+2, 0
    asm je last
big:
    asm push ds
    asm mov bx, handle
    asm mov cx, 8000h
    asm mov dx, off
    asm mov ax, seg
    asm mov ds, ax
    asm mov ah, 40h
    asm int 21h
    asm pop ds
    asm add seg, 800h
    asm sub word ptr len, 8000h
    asm sbb word ptr len+2, 0
    asm cmp word ptr len+2, 0
    asm ja big
    asm cmp word ptr len, 8000h
    asm jae big
last:
    asm push ds
    asm mov bx, handle
    asm mov cx, word ptr len
    asm mov dx, off
    asm mov ax, seg
    asm mov ds, ax
    asm mov ah, 40h
    asm int 21h
    asm pop ds
    goto done;
done:
    asm mov bx, handle
    asm mov ah, 3eh
    asm int 21h
}

/*
 * load_file
 * cs [0x6a1e,0x6a8a) / file [0x6c1e,0x6c8a), 108 bytes.
 *
 * Opens a file (O_BINARY), allocates filelength bytes with
 * farmalloc_aligned, reads it with read_file_far and returns the buffer (NULL if it
 * cannot be opened).
 *
 * Evidence for the name: open/filelength/close/read_file_far.
 *
 * Codegen: if/else with returns in both arms emits a dead jmp after `return
 * buf`.
 */

void far *load_file(char *name)
{
    long len;
    char far *buf;
    register int fd;

    if ((fd = open(name, O_BINARY)) != -1) {
        len = filelength(fd);
        buf = farmalloc_aligned(len);
        close(fd);
        read_file_far(name, buf);
        return buf;
    } else
        return 0;
}

/*
 * load_rle_file
 * cs [0x6a8a,0x6b64) / file [0x6c8a,0x6d64), 218 bytes.
 *
 * Loads a compressed file: reads the 4-byte unpacked size, allocates the
 * output, loads the packed file into a temporary block and decompresses it
 * (RLEExpand) from offset 4, then frees the temporary block and restores
 * g_alloc_block.
 *
 * Evidence for the name: farfree of the temporary, decompressor call RLEExpand.
 *
 * Codegen: `packed` is a huge pointer (packed + 4 via N_PADD@).
 */

char far *load_rle_file(char *name)
{
    long flen, size;
    void far *saved;
    char huge *packed;
    char far *out;
    register int fd;

    if ((fd = open(name, O_BINARY)) != -1) {
        flen = filelength(fd);
        read(fd, &size, 4);
        close(fd);
        out = farmalloc_aligned(size);
        saved = g_alloc_block;
        packed = farmalloc_aligned(flen);
        read_file_far(name, packed);
        RLEExpand(packed + 4, out, size);
        farfree(g_alloc_block);
        g_alloc_block = saved;
        return out;
    } else
        return 0;
}

/*
 * set_video_mode(mode)
 * cs [0x6b64,0x6bc2) / file [0x6d64,0x6dc2), 94 bytes incl. the 4-entry
 * switch jump table.
 *
 * mode 0: BIOS text mode 3
 * mode 1: CGA 320x200x4 (mode 4)
 * mode 2: EGA 320x200x16 (mode 0Dh), then ega_upload_planes
 * mode 3: VGA 320x200x256 (mode 13h), then INT 10h AX=1012h loads all 256
 *         DAC registers from the palette at g_vga_palette
 *
 * Codegen note: `_ES = FP_SEG(p); _DX = FP_OFF(p);` compiles to a single
 * `les dx,[bp-4]`; every `break` emits a jmp to the epilogue, even the last
 * one (eb 00), because jump optimisation is off.
 */

void set_video_mode(int mode)
{
    unsigned char far *pal = g_vga_palette;

    switch (mode) {
    case 0: _AX = 3; geninterrupt(0x10); break;
    case 1: _AX = 4; geninterrupt(0x10); break;
    case 2: _AX = 0xd; geninterrupt(0x10); ega_upload_planes(); break;
    case 3: _AX = 0x13; geninterrupt(0x10);
        _ES = FP_SEG(pal); _DX = FP_OFF(pal); _BX = 0; _CX = 0x100; _AX = 0x1012;
        geninterrupt(0x10);
        break;
    }
}

/*
 * draw_text_window
 * cs [0x6bc2,0x6cb9) / file [0x6dc2,0x6eb9), 247 bytes.
 *
 * Draws a framed text window with frame characters 1..8 via DrawChar, clears
 * its interior, stores the window rectangle (g_win_x1, g_win_x2, g_win_y1, g_win_y2) and puts the
 * text cursor at its top-left inner cell (g_text_x/g_text_left, g_text_y).
 */

void draw_text_window(int x1, int y1, int x2, int y2)
{
    register int x, y;

    g_win_x1 = x1;
    g_win_y1 = y1;
    g_win_x2 = x2;
    g_win_y2 = y2;
    DrawChar(x1, y1, 1);
    for (x = x1 + 1; x < x2; x++)
        DrawChar(x, y1, 2);
    DrawChar(x2, y1, 3);
    for (y = y1 + 1; y < y2; y++) {
        DrawChar(x1, y, 4);
        for (x = x1 + 1; x < x2; x++)
            DrawChar(x, y, ' ');
        DrawChar(x2, y, 5);
    }
    DrawChar(x1, y2, 6);
    for (x = x1 + 1; x < x2; x++)
        DrawChar(x, y2, 7);
    DrawChar(x2, y2, 8);
    g_text_x = g_text_left = x1 + 1;
    g_text_y = y1 + 1;
}

/*
 * clear_text_window
 * cs [0x6cb9,0x6cf1) / file [0x6eb9,0x6ef1), 56 bytes.
 *
 * Fills the stored window rectangle with spaces.
 *
 * Codegen: Register vars: the inner-loop variable gets SI (higher use
 * weight).
 */

void clear_text_window(void)
{
    register int x, y;

    for (y = g_win_y1; y <= g_win_y2; y++)
        for (x = g_win_x1; x <= g_win_x2; x++)
            DrawChar(x, y, ' ');
}

/*
 * draw_centered_window
 * cs [0x6cf1,0x6d3b) / file [0x6ef1,0x6f3b), 74 bytes.
 *
 * Draws a w x h window centred on the 40x25 text screen.
 *
 * Codegen: `register int x, y;` - with equal weight the first-declared gets
 * DI.
 */

void draw_centered_window(int w, int h)
{
    register int x, y;
    x = 19 - w / 2;
    y = 11 - h / 2;
    draw_text_window(x, y, x + w + 2, y + h + 2);
}

/*
 * open_window_anim
 * cs [0x6d3b,0x6d9d) / file [0x6f3b,0x6f9d), 98 bytes.
 *
 * Recursive zoom-open animation for a w x h window: shrinks both dimensions
 * by 2 until <= 2, then draws each step with a delay (WaitVBL).
 */

void open_window_anim(register int w, register int h)
{
    if (w > 2) {
        if (h > 2)
            open_window_anim(w - 2, h - 2);
        else
            open_window_anim_w(w - 2, h);
    } else if (h > 2)
        open_window_anim_h(w, h - 2);
    WaitVBL();
    draw_centered_window(w, h);
}

/*
 * open_window_anim_w
 * cs [0x6d9d,0x6dd1) / file [0x6f9d,0x6fd1), 52 bytes.
 *
 * Zoom animation helper shrinking only the width.
 */

void open_window_anim_w(register int w, int h)
{
    if (w > 2)
        open_window_anim_w(w - 2, h);
    WaitVBL();
    draw_centered_window(w, h);
}

/*
 * open_window_anim_h
 * cs [0x6dd1,0x6e05) / file [0x6fd1,0x7005), 52 bytes.
 *
 * Zoom animation helper shrinking only the height.
 */

void open_window_anim_h(int w, register int h)
{
    if (h > 2)
        open_window_anim_h(w, h - 2);
    WaitVBL();
    draw_centered_window(w, h);
}

/*
 * wait_key_cursor
 * cs [0x6e05,0x6e71) / file [0x7005,0x7071), 108 bytes.
 *
 * Waits for a key while animating a blinking cursor (chars 9..12 with
 * delays) at the text cursor, erases it and returns bioskey(0).
 */

int wait_key_cursor(void)
{
    register int i, key;

    do {
        i = 9;
        while ((key = bioskey(1)) == 0 && i < 13) {
            DrawChar(g_text_x, g_text_y, i++);
            WaitVBL();
            WaitVBL();
            WaitVBL();
            WaitVBL();
            WaitVBL();
        }
    } while (key == 0);
    DrawChar(g_text_x, g_text_y, ' ');
    return bioskey(0);
}

/*
 * print_string
 * cs [0x6e71,0x6ecb) / file [0x7071,0x70cb), 90 bytes.
 *
 * Prints a string at the text cursor handling \n (next line, column reset to
 * g_text_left) and \r.
 *
 * Codegen: `char c` is not register-allocated.
 */

void print_string(char *s)
{
    char c;

    while ((c = *s++) != 0) {
        if (c == '\n') {
            g_text_y++;
            g_text_x = g_text_left;
        } else if (c == '\r')
            g_text_x = g_text_left;
        else
            DrawChar(g_text_x++, g_text_y, c);
    }
}

/*
 * print_int
 * cs [0x6ecb,0x6ef8) / file [0x70cb,0x70f8), 45 bytes.
 *
 * itoa(n) then print_string.
 *
 * Codegen: Calls itoa/ltoa without a prototype (no <stdlib.h>).
 */

void print_int(int n)
{
    char buf[20];

    itoa(n, buf, 10);
    print_string(buf);
}

/*
 * print_long
 * cs [0x6ef8,0x6f25) / file [0x70f8,0x7125), 45 bytes.
 *
 * ltoa(n) then print_string - original bug: n is an int and ltoa is
 * unprototyped, so only one word is pushed.
 *
 * Codegen: No <stdlib.h>: ltoa called with an int argument.
 */

void print_long(int n)
{
    char buf[20];

    ltoa(n, buf, 10);
    print_string(buf);
}

