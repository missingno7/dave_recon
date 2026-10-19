/*
 * F_6F3B -- open_window_anim
 * cs [0x6d3b,0x6d9d) / file [0x6f3b,0x6f9d), 98 bytes. Strict match: tools/match_function.py.
 *
 * Recursive zoom-open animation for a w x h window: shrinks both dimensions
 * by 2 until <= 2, then draws each step with a delay (F_7831).
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name open_window_anim
 */

void F_6F9D(int w, int h);
void F_6FD1(int w, int h);
void F_6EF1(int w, int h);
void F_7831(void);

void F_6F3B(register int w, register int h)
{
    if (w > 2) {
        if (h > 2)
            F_6F3B(w - 2, h - 2);
        else
            F_6F9D(w - 2, h);
    } else if (h > 2)
        F_6FD1(w, h - 2);
    F_7831();
    F_6EF1(w, h);
}
