/* @flags -G */
extern int D_8A12, D_8A14, D_8A22;
void F_7878(int x, int y, int c);

void F_7071(char *s)
{
    char c;

    while ((c = *s++) != 0) {
        if (c == '\n') {
            D_8A14++;
            D_8A12 = D_8A22;
        } else if (c == '\r')
            D_8A12 = D_8A22;
        else
            F_7878(D_8A12++, D_8A14, c);
    }
}
