/* @flags -G */
void F_7071(char *s);

void F_70F8(int n)
{
    char buf[20];

    ltoa(n, buf, 10);
    F_7071(buf);
}
