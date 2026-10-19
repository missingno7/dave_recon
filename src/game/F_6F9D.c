/*
 * F_6F9D -- open_window_anim_w
 * cs [0x6d9d,0x6dd1) / file [0x6f9d,0x6fd1), 52 bytes. Strict match: tools/match_function.py.
 *
 * Zoom animation helper shrinking only the width.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name open_window_anim_w
 */

void F_6EF1(int w, int h);
void F_7831(void);

void F_6F9D(register int w, int h)
{
    if (w > 2)
        F_6F9D(w - 2, h);
    F_7831();
    F_6EF1(w, h);
}
