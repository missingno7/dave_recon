/*
 * TEST-ONLY: the input the world's waiting loops see, reconstructed for one
 * verified pipeline call from the oracle run (state-model D2/D7).
 *
 * Sources:
 *  - the pre-call snapshot: the INT 9 key table g_keydown, the bindings
 *    g_key_scans and the player-1 device (only the keyboard is modelled);
 *  - $DAVE_BRIDGE_INPUTS (written by tools/native_check.py from the run's
 *    script and ticks.jsonl):
 *        event <ms> down|up <scan>       the scenario's key events
 *        pair <index> start <ms> time <u32>
 *    `start` is the emulated time of the tick head of the verified call;
 *    the poll after r retraces of the call is placed at start + r retrace
 *    periods (exact for attract_mode, the first call of the tick; later
 *    calls are verified with keys held across them). `time` is time(NULL)
 *    as the original's srand saw it at the end of the call.
 *  - the BIOS key buffer is not in the snapshot: it is modelled as empty at
 *    the start of the call and holding the last key pressed DURING the call
 *    (the INT 9 handler empties the buffer before the BIOS adds the new key);
 *    modifier keys (Ctrl, Alt, Shift) never enter it; typematic repeat is
 *    not modelled.
 *  - $DAVE_BRIDGE_DEMOS: the 4,368-byte demo bank (far segment 0x0B31);
 *  - $DAVE_BRIDGE_LEVELS: g_levels as DAVE.EXE initialises it (the level
 *    resources; without it they are taken from each snapshot).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "dgroup_map.h"
#include "world_io.h"

#define VBL_MS (1000.0 / 70.086)     /* tools/oracle.py VBL_MS */
#define MAX_EVENTS 4096
#define MAX_PAIRS 65536
#define POLL_LIMIT 200000            /* a wait the input never ends: give up (reported) */

struct key_event { double ms; int down; int scan; };
struct pair_info { int known; double start; uint32_t time; };

static struct key_event events[MAX_EVENTS];
static int n_events;
static struct pair_info *pairs;
static unsigned char pristine_levels[LEVEL_COUNT * LEVEL_RECORD_BYTES];
static int have_levels;

static struct {
    struct dgroup_keyboard kb;
    double start;
    uint32_t time;
    int next_event;
    int16_t buffer;
    long polls;
    long index;
} cur;

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

void bridge_world_load(struct resources *r)
{
    const char *demos = getenv("DAVE_BRIDGE_DEMOS");
    if (demos) {
        FILE *f = fopen(demos, "rb");
        if (!f || fread(r->demos, 1, DEMO_BANK_BYTES, f) != DEMO_BANK_BYTES)
            fprintf(stderr, "dave_bridge: cannot read demo bank %s\n", demos);
        if (f)
            fclose(f);
    }
    const char *levels = getenv("DAVE_BRIDGE_LEVELS");
    if (levels) {
        FILE *f = fopen(levels, "rb");
        have_levels = f && fread(pristine_levels, 1, sizeof pristine_levels, f) == sizeof pristine_levels;
        if (!have_levels)
            fprintf(stderr, "dave_bridge: cannot read levels %s\n", levels);
        if (f)
            fclose(f);
    }
    pairs = calloc(MAX_PAIRS, sizeof *pairs);
    const char *inputs = getenv("DAVE_BRIDGE_INPUTS");
    if (!inputs || !pairs)
        return;
    FILE *f = fopen(inputs, "r");
    if (!f) {
        fprintf(stderr, "dave_bridge: cannot read %s\n", inputs);
        return;
    }
    char line[256], kind[16];
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
        } else if (sscanf(line, "pair %ld start %lf time %lu", &k, &ms, &t) == 3 && k >= 0 && k < MAX_PAIRS) {
            pairs[k].known = 1;
            pairs[k].start = ms;
            pairs[k].time = (uint32_t)t;
        }
    }
    fclose(f);
}

void bridge_world_begin(long index, const unsigned char *snap, struct game *g, struct resources *r)
{
    dgroup_import_world(g, r, snap, have_levels ? pristine_levels : NULL);
    memset(&cur, 0, sizeof cur);
    cur.index = index;
    dgroup_import_keyboard(&cur.kb, snap);
    if (pairs && index >= 0 && index < MAX_PAIRS && pairs[index].known) {
        cur.start = pairs[index].start;
        cur.time = pairs[index].time;
        while (cur.next_event < n_events && events[cur.next_event].ms <= cur.start)
            cur.next_event++;
    } else {
        cur.next_event = n_events;    /* no timing: the snapshot's keys, constant */
    }
}

/* Apply the scenario's key events up to the poll after `retrace` retraces. */
static void advance(uint32_t retrace)
{
    double t = cur.start + retrace * VBL_MS;
    while (cur.next_event < n_events && events[cur.next_event].ms <= t) {
        const struct key_event *e = &events[cur.next_event++];
        if (e->scan >= 0 && e->scan < 128)
            cur.kb.keydown[e->scan] = (int16_t)e->down;
        if (e->down && !is_modifier(e->scan))
            cur.buffer = (int16_t)(e->scan << 8 | key_ascii(e->scan));
    }
}

static int give_up(void)
{
    if (++cur.polls == POLL_LIMIT)
        fprintf(stderr, "dave_bridge: pair %ld: no input ends the wait; giving up\n", cur.index);
    return cur.polls >= POLL_LIMIT;
}

static struct wait_input player(void *ctx, uint32_t retrace)
{
    (void)ctx;
    advance(retrace);
    struct wait_input in = {8, 0, 0};
    int forced = give_up();
    if (cur.kb.device == 0) {         /* read_keyboard_input; mouse/joystick: not modelled */
        const int16_t *down = cur.kb.keydown;
        const uint8_t *s = cur.kb.scans;
        int dx = 0, dy = 0;
        if (down[s[0] & 0x7F]) dy = -1;
        if (down[s[2] & 0x7F]) dx = 1;
        if (down[s[4] & 0x7F]) dy = 1;
        if (down[s[6] & 0x7F]) dx = -1;
        if (down[s[1] & 0x7F]) { dy = -1; dx = 1; }
        if (down[s[7] & 0x7F]) { dy = -1; dx = -1; }
        if (down[s[3] & 0x7F]) { dy = 1; dx = 1; }
        if (down[s[5] & 0x7F]) { dy = 1; dx = -1; }
        static const int16_t dir_of[9] = {7, 0, 1, 6, 8, 2, 5, 4, 3};   /* dy*3+dx = -4..4 */
        in.dir = dir_of[dy * 3 + dx + 4];
        in.fire = down[s[8] & 0x7F];
        in.jump = down[s[9] & 0x7F];
    }
    if (forced)
        in.dir = 2;
    return in;
}

static int16_t key_peek(void *ctx, uint32_t retrace)
{
    (void)ctx;
    advance(retrace);
    if (give_up())
        return ' ' | 0x3900;
    return cur.buffer;
}

static void key_take(void *ctx, uint32_t retrace)
{
    (void)ctx;
    advance(retrace);
    cur.buffer = 0;
}

static uint32_t clock_now(void *ctx, uint32_t retrace)
{
    (void)ctx;
    (void)retrace;
    return cur.time;
}

const struct world_io *bridge_world_io(void)
{
    static const struct world_io io = {NULL, player, key_peek, key_take, clock_now};
    return &io;
}
