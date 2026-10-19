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
