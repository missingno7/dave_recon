/* @flags -G */
extern int D_8A24, D_8A26, D_8A28, D_8A2A;
void F_7878(int x, int y, int c);

void F_6EB9(void)
{
    register int x, y;

    for (y = D_8A28; y <= D_8A2A; y++)
        for (x = D_8A24; x <= D_8A26; x++)
            F_7878(x, y, ' ');
}
