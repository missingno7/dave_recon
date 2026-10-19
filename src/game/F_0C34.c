/* @flags -G */
/* @seg _DATA 0x07c8 */
#include <stdlib.h>
#include <string.h>
#include <mem.h>
extern unsigned long D_4C60;
extern unsigned long D_6148;
extern int D_56EE;
extern int D_4F86;
extern int D_0208;
extern int D_020A[];
extern int D_01EA[];
void F_1BD6(int, int, int);
void F_1B84(int, int, int);
void F_763E(int);

void F_0C34(void)
{
    char num[6] = "";
    char digits[6] = "00000";

    if (D_4C60 - D_6148 >= 20000) {
        D_6148 = D_4C60;
        D_6148 = D_6148 / 20000 * 20000;
        if (D_56EE < 3) {
            F_1BD6(D_56EE * 16 + 0x100, 0, D_020A[D_0208 * D_4F86 + 6]);
            D_56EE++;
            F_763E(0xc);
        }
    }
    if (D_4C60 > 99999L)
        D_4C60 = 99999L;
    ultoa(D_4C60, num, 10);
    movmem(num, digits + (5 - strlen(num)), strlen(num));
    F_1B84(0x40, 1, D_01EA[D_4F86] + digits[0] - '0');
    F_1B84(0x48, 1, D_01EA[D_4F86] + digits[1] - '0');
    F_1B84(0x50, 1, D_01EA[D_4F86] + digits[2] - '0');
    F_1B84(0x58, 1, D_01EA[D_4F86] + digits[3] - '0');
    F_1B84(0x60, 1, D_01EA[D_4F86] + digits[4] - '0');
}
