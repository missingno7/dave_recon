/*
 * F_6FD1 -- open_window_anim_h
 * cs [0x6dd1,0x6e05) / file [0x6fd1,0x7005), 52 bytes. Strict match: tools/match_function.py.
 *
 * Zoom animation helper shrinking only the height.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name open_window_anim_h
 */
/* @flags -G */
void F_6EF1(int w, int h);
void F_7831(void);

void F_6FD1(int w, register int h)
{
    if (h > 2)
        F_6FD1(w, h - 2);
    F_7831();
    F_6EF1(w, h);
}
