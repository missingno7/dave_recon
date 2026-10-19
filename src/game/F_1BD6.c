/* @flags -G */
extern int D_4F86;
void F_8D95(int, int, int);
void F_8A88(int, int, int);
void F_8C66(int, int, int);

void F_1BD6(int a, int b, int c)
{
    switch (D_4F86) {
    case 0: F_8D95(a, b, c); break;
    case 1: F_8A88(a, b, c); break;
    case 2: F_8C66(a, b, c); break;
    }
}
