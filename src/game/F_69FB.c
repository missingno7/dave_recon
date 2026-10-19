/* @flags -G */
extern char *D_8A2C;
extern char D_8B34[];
extern int D_9EC2;
void F_6B94(char *name, char far *buf, long len);

void F_69FB(char *name)
{
    F_6B94(name, (char far *)(long)D_8B34, D_8A2C - D_8B34);
    D_9EC2 = 0;
}
