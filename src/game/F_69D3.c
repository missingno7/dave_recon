/* @flags -G */
extern char *D_8A2C;
extern char D_8B34[];
extern int D_9EC2;
long F_6ADE(char *name, char far *buf);

void F_69D3(char *name)
{
    F_6ADE(name, (char far *)(long)D_8B34);
    D_8A2C = D_8B34;
    D_9EC2 = 1;
}
