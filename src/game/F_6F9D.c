/* @flags -G */
void F_6EF1(int w, int h);
void F_7831(void);

void F_6F9D(register int w, int h)
{
    if (w > 2)
        F_6F9D(w - 2, h);
    F_7831();
    F_6EF1(w, h);
}
