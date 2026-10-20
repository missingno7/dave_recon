/*
 * TEST-ONLY free-running replay (docs/PORT_ROADMAP.md M3.3).
 *
 * Imports ONE original DGROUP snapshot (the head of the start tick of an
 * oracle run) into struct game, then calls game_tick() once per input line,
 * never looking at the original's state again. After every tick it exports
 * struct game into a copy of the START snapshot (so a game-state byte the
 * native game does not model keeps its start value and shows up as a
 * divergence wherever the original changes it) and writes it to stdout;
 * tools/native_replay.py compares it with the original's next tick head.
 *
 *   dave_replay <start.bin> <inputs.txt> <events.txt>  > native snapshots
 *
 * The only things taken from the original run per tick are INPUTS
 * (port/README.md "Input model"; state-model D6, D7):
 *   - the key-state table at the first poll of each pass (`keys`: the
 *     original's INT 9 table g_keydown as process_input read it, or at the
 *     tick head -- platform state, not game state: state-model section 4;
 *     tools/native_replay.py first_poll_keys), advanced by the scenario's
 *     key events (`event <ms> down|up <scan>`) for the later polls inside
 *     the pass, as port/tests/bridge/world_io.c does per call;
 *   - the BIOS key buffer: one persistent slot, empty at the start, set by
 *     every non-modifier make code, emptied by bioskey(0) (key_take) -- the
 *     original's INT 9 handler empties the buffer before the BIOS adds a key,
 *     so at most one key is ever waiting (input.h, N2-5);
 *   - the timeline: `tick <k> start <ms> time <t> keys <scans|->` gives the
 *     emulated time of tick k's head (when the platform delivers the frame)
 *     and time(NULL) for that tick (D7). A poll after r retraces of the pass
 *     reads the keys at start + r * vbl (`vbl <ms>`, the video mode's
 *     retrace period).
 * Settings (input device, key bindings) are read once from the start
 * snapshot (D6: settings live outside struct game).
 *
 * events.txt, one block per tick, flushed per tick:
 *   tick <k> status <0|1|2> menu <m> retraces <n> sounds <s1,s2,...|->
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
#include "dgroup_map.h"
#include "game.h"
#include "input_map.h"
#include "world_io.h"

#define MAX_EVENTS 8192
#define MAX_TICKS 200000
#define POLL_LIMIT 2000000L     /* polls in one tick: a wait no input ends */

struct key_event { double ms; int down; int scan; };
struct tick_info { long tick; double start; uint32_t time; uint8_t keys[128]; };

static struct key_event events[MAX_EVENTS];
static int n_events;
static struct tick_info *ticks;
static long n_ticks;
static double vbl_ms = 1000.0 / 70.086;

static struct {
    struct dgroup_keyboard kb;   /* key table (evolving) + settings (fixed) */
    int next_event;
    int16_t buffer;              /* the one waiting BIOS key, 0 = none */
    double start;                /* emulated ms of the current tick head */
    uint32_t time;
    long polls;
} in;

static int16_t key_ascii(int scan)
{
    static const char row1[] = "qwertyuiop", row2[] = "asdfghjkl", row3[] = "zxcvbnm";
    if (scan == 0x39) return ' ';
    if (scan == 0x1C) return '\r';
    if (scan == 0x01) return 0x1B;
    if (scan >= 0x10 && scan < 0x10 + 10) return row1[scan - 0x10];
    if (scan >= 0x1E && scan < 0x1E + 9) return row2[scan - 0x1E];
    if (scan >= 0x2C && scan < 0x2C + 7) return row3[scan - 0x2C];
    return 0;
}

static int is_modifier(int scan)
{
    return scan == 0x1D || scan == 0x38 || scan == 0x2A || scan == 0x36 || scan == 0x3A;
}

static void advance(uint32_t retrace)
{
    double t = in.start + retrace * vbl_ms;
    if (++in.polls > POLL_LIMIT) {
        fprintf(stderr, "dave_replay: no input ends a wait (poll limit); stopping\n");
        exit(3);
    }
    while (in.next_event < n_events && events[in.next_event].ms <= t) {
        const struct key_event *e = &events[in.next_event++];
        if (e->scan >= 0 && e->scan < 128)
            in.kb.keydown[e->scan] = (int16_t)e->down;
        if (e->down && !is_modifier(e->scan))
            in.buffer = (int16_t)(e->scan << 8 | key_ascii(e->scan));
    }
}

static struct frame_input io_player(void *ctx, uint32_t retrace)
{
    (void)ctx;
    advance(retrace);
    struct frame_input s = {DIR_NONE, 0, 0, 0, in.time};
    if (in.kb.device == DEVICE_KEYBOARD) {   /* mouse/joystick: not in the corpus */
        struct input_settings set;
        uint8_t down[128];
        set.device = in.kb.device;
        for (int k = 0; k < BIND_COUNT; k++)
            set.keys[k] = in.kb.scans[k];
        for (int k = 0; k < 128; k++)
            down[k] = in.kb.keydown[k] != 0;
        input_from_keyboard(&s, down, &set);
    }
    return s;
}

static int16_t io_key_peek(void *ctx, uint32_t retrace)
{
    (void)ctx;
    advance(retrace);
    return in.buffer;
}

static void io_key_take(void *ctx, uint32_t retrace)
{
    (void)ctx;
    advance(retrace);
    in.buffer = 0;
}

static uint32_t io_clock(void *ctx, uint32_t retrace)
{
    (void)ctx;
    (void)retrace;
    return in.time;
}

static const struct world_io replay_io = {NULL, io_player, io_key_peek, io_key_take, io_clock};

static void load_inputs(const char *path)
{
    FILE *f = fopen(path, "r");
    if (!f) {
        perror(path);
        exit(2);
    }
    ticks = calloc(MAX_TICKS, sizeof *ticks);
    char line[1024], kind[16], keys[601];
    while (fgets(line, sizeof line, f)) {
        double ms;
        int scan;
        long k;
        unsigned long t;
        if (sscanf(line, "event %lf %15s %i", &ms, kind, &scan) == 3 && n_events < MAX_EVENTS) {
            events[n_events].ms = ms;
            events[n_events].down = strcmp(kind, "down") == 0;
            events[n_events].scan = scan;
            n_events++;
        } else if (sscanf(line, "tick %ld start %lf time %lu keys %600s", &k, &ms, &t, keys) == 4
                   && n_ticks < MAX_TICKS) {
            struct tick_info *ti = &ticks[n_ticks++];
            ti->tick = k;
            ti->start = ms;
            ti->time = (uint32_t)t;
            for (char *tok = strtok(keys, ","); tok; tok = strtok(NULL, ","))
                if (strcmp(tok, "-") != 0 && atoi(tok) >= 0 && atoi(tok) < 128)
                    ti->keys[atoi(tok)] = 1;
        } else if (sscanf(line, "vbl %lf", &ms) == 1) {
            vbl_ms = ms;
        }
    }
    fclose(f);
}

int main(int argc, char **argv)
{
    if (argc < 4) {
        fprintf(stderr, "usage: dave_replay <start.bin> <inputs.txt> <events.txt> > native.bin\n");
        return 2;
    }
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    static unsigned char start[DGROUP_LEN], snap[DGROUP_LEN];
    static struct game g;
    static struct resources res;
    static struct frame_output out;
    FILE *f = fopen(argv[1], "rb");
    if (!f || fread(start, 1, DGROUP_LEN, f) != DGROUP_LEN) {
        fprintf(stderr, "dave_replay: cannot read %s\n", argv[1]);
        return 2;
    }
    fclose(f);
    load_inputs(argv[2]);
    FILE *ev = fopen(argv[3], "w");
    if (!ev) {
        perror(argv[3]);
        return 2;
    }

    /* the one import: game state, level resources (DAVE.EXE's g_levels via
     * $DAVE_BRIDGE_LEVELS, the demo bank via $DAVE_BRIDGE_DEMOS), settings */
    bridge_world_load(&res);
    dgroup_import(&g, start);
    dgroup_import_resources(&res, start);
    bridge_world_begin(-1, start, &g, &res);
    dgroup_import_keyboard(&in.kb, start);
    if (n_ticks > 0)
        while (in.next_event < n_events && events[in.next_event].ms <= ticks[0].start)
            in.next_event++;     /* already in the start snapshot's key table */

    for (long k = 0; k < n_ticks; k++) {
        in.start = ticks[k].start;
        in.time = ticks[k].time;
        in.polls = 0;
        /* the tick head: key events up to here are in the head's key table
         * (or still in the keyboard's delivery); a make code among them is
         * the key waiting in the BIOS buffer */
        while (in.next_event < n_events && events[in.next_event].ms <= in.start) {
            const struct key_event *e = &events[in.next_event++];
            if (e->down && !is_modifier(e->scan))
                in.buffer = (int16_t)(e->scan << 8 | key_ascii(e->scan));
        }
        for (int sc = 0; sc < 128; sc++)
            in.kb.keydown[sc] = ticks[k].keys[sc];
        fprintf(ev, "tick %ld", ticks[k].tick);
        memset(&out, 0, sizeof out);
        struct tick_result r = game_tick(&g, &res, &replay_io, &out);
        fprintf(ev, " status %d menu %d retraces %u sounds ", (int)r.status, (int)r.menu, out.retraces);
        if (out.n_sounds == 0)
            fputc('-', ev);
        for (unsigned i = 0; i < out.n_sounds; i++)
            fprintf(ev, i ? ",%d" : "%d", out.sounds[i]);
        if (out.n_sounds == OUTPUT_MAX_SOUNDS)
            fputs(",overflow", ev);
        fputc('\n', ev);
        fflush(ev);

        if (r.status != TICK_CONTINUE)
            break;               /* the inner loop ends / the pass left the pipeline: the
                                    original's next observed state is not this pass's */
        memcpy(snap, start, DGROUP_LEN);
        dgroup_export_levels(&g, &res, snap);
        dgroup_export(&g, snap);
        if (fwrite(snap, 1, DGROUP_LEN, stdout) != DGROUP_LEN)
            return 0;            /* the reader stopped (first divergence) */
        fflush(stdout);
    }
    fclose(ev);
    return 0;
}
