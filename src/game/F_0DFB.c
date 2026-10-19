/* @flags -G */
extern int D_4F86;
extern int D_56F4;
extern int D_01EA[];
void F_1B84(int, int, int);

void F_0DFB(void)
{
    F_1B84(0xb0, 1, D_01EA[D_4F86] + (D_56F4 + 1) / 10);
    F_1B84(0xb8, 1, D_01EA[D_4F86] + (D_56F4 + 1) % 10);
}
