/* @flags -G */
void F_6DC2(int x1, int y1, int x2, int y2);
void F_6EF1(int w, int h)
{
    register int x, y;
    x = 19 - w / 2;
    y = 11 - h / 2;
    F_6DC2(x, y, x + w + 2, y + h + 2);
}
