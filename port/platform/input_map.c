#include "input_map.h"

void input_from_keyboard(struct frame_input *in, const uint8_t key_down[128],
                         const struct input_settings *s)
{
    int dx = 0, dy = 0;
#define DOWN(b) (key_down[s->keys[b] & 0x7F] != 0)
    if (DOWN(BIND_N)) dy = -1;
    if (DOWN(BIND_E)) dx = 1;
    if (DOWN(BIND_S)) dy = 1;
    if (DOWN(BIND_W)) dx = -1;
    if (DOWN(BIND_NE)) { dy = -1; dx = 1; }
    if (DOWN(BIND_NW)) { dy = -1; dx = -1; }
    if (DOWN(BIND_SE)) { dy = 1; dx = 1; }
    if (DOWN(BIND_SW)) { dy = 1; dx = -1; }
    /* the original's switch over dy * 3 + dx */
    static const int16_t dir_of[9] = {
        DIR_NW, DIR_N, DIR_NE,   /* dy = -1 */
        DIR_W, DIR_NONE, DIR_E,  /* dy =  0 */
        DIR_SW, DIR_S, DIR_SE    /* dy = +1 */
    };
    in->dir = dir_of[(dy + 1) * 3 + (dx + 1)];
    in->fire = DOWN(BIND_FIRE);
    in->jump = DOWN(BIND_JUMP);
#undef DOWN
}
