/* @flags -G */
extern int D_4F86;
void F_8E5E(int, int, int);
void F_8B9F(int, int, int);
void F_8D17(int, int, int);

void F_1B84(int a, int b, int c)
{
    switch (D_4F86) {
    case 0: F_8E5E(a, b, c); break;
    case 1: F_8B9F(a, b, c); break;
    case 2: F_8D17(a, b, c); break;
    }
}
