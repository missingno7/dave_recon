/* @flags -G */
extern int D_8A24, D_8A26, D_8A28, D_8A2A;
extern int D_8A12, D_8A14, D_8A22;
void F_7878(int x, int y, int c);

void F_6DC2(int x1, int y1, int x2, int y2)
{
    register int x, y;

    D_8A24 = x1;
    D_8A28 = y1;
    D_8A26 = x2;
    D_8A2A = y2;
    F_7878(x1, y1, 1);
    for (x = x1 + 1; x < x2; x++)
        F_7878(x, y1, 2);
    F_7878(x2, y1, 3);
    for (y = y1 + 1; y < y2; y++) {
        F_7878(x1, y, 4);
        for (x = x1 + 1; x < x2; x++)
            F_7878(x, y, ' ');
        F_7878(x2, y, 5);
    }
    F_7878(x1, y2, 6);
    for (x = x1 + 1; x < x2; x++)
        F_7878(x, y2, 7);
    F_7878(x2, y2, 8);
    D_8A12 = D_8A22 = x1 + 1;
    D_8A14 = y1 + 1;
}
