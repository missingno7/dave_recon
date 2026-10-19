/* @flags -G */
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
