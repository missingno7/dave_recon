/* @flags -G */
extern int D_4F86;
void F_88FD(int, int, int, int);
void F_8525(int, int, int, int);
void F_8778(int, int, int, int);

void F_1B29(int a, int b, int c, int d)
{
    switch (D_4F86) {
    case 0: F_88FD(a, b, c, d); break;
    case 1: F_8525(a, b, c, d); break;
    case 2: F_8778(a, b, c, d); break;
    }
}
