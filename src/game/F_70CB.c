/* @flags -G */
void F_7071(char *s);

void F_70CB(int n)
{
    char buf[20];

    itoa(n, buf, 10);
    F_7071(buf);
}
