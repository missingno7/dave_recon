/* @flags -G */
#include <stdlib.h>
void F_6388(void);
void F_760F(void);
void F_6D64(int);

void F_04D2(int code)
{
    F_6388();
    F_760F();
    if (code == 0)
        F_6D64(0);
    exit(code);
}
