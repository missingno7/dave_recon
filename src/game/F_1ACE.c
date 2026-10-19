/* @flags -G */
extern int D_4F86;
void F_89E6(int, int, int, int);
void F_86A9(int, int, int, int);
void F_8871(int, int, int, int);

void F_1ACE(int a, int b, int c, int d)
{
    switch (D_4F86) {
    case 0: F_89E6(a, b, c, d); break;
    case 1: F_86A9(a, b, c, d); break;
    case 2: F_8871(a, b, c, d); break;
    }
}
