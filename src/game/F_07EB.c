/* @flags -G */
#include <bios.h>
#include <ctype.h>
extern int D_8A12;
extern int D_8A14;
int F_7005(void);
void F_7878(int, int, int);

void F_07EB(char *name)
{
    int n;
    int key;
    char c;

    n = 0;
    if (bioskey(1))
        bioskey(0);
    do {
        c = toupper(key = F_7005());
        if (c >= ' ' && c <= 'Z' && n < 3) {
            name[n++] = c;
            F_7878(D_8A12++, D_8A14, c);
        }
        if (((key >> 8) == 0x4b || (key >> 8) == 0x0e) && n > 0) {
            F_7878(--D_8A12, D_8A14, ' ');
            n--;
        }
    } while (c != '\r');
}
