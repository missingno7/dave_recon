int probe2(int a, int b)
{
    char buf1[20];
    char buf2[6];
    int total;

    total = a + b;
    buf1[0] = (char)total;
    buf2[0] = (char)b;
    return total;
}
