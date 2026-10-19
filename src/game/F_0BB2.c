/* @flags -G */
extern int D_4F8A;
extern int D_4F84;
extern int D_4F88;
extern int D_4F86;
extern int D_0208;
extern int D_020A[];
void F_371F(void);
void F_1BD6(int, int, int);
void F_0C34(void);
void F_0DFB(void);

void F_0BB2(void)
{
    if (D_4F8A) {
        F_371F();
        F_1BD6(0, 0xaa, D_020A[D_4F86 * D_0208]);
    }
    if (D_4F84)
        F_1BD6(0xf0, 0xaa, D_020A[D_4F86 * D_0208 + 1]);
    if (D_4F88)
        F_1BD6(0x48, 0xb8, D_020A[D_4F86 * D_0208 + 5]);
    F_0C34();
    F_0DFB();
}
