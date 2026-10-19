/* @flags -G */
#include <io.h>
#include <fcntl.h>

void far *F_6A62(unsigned long size);
long F_6ADE(char *name, char far *buf);

void far *F_6C1E(char *name)
{
    long len;
    char far *buf;
    register int fd;

    if ((fd = open(name, O_BINARY)) != -1) {
        len = filelength(fd);
        buf = F_6A62(len);
        close(fd);
        F_6ADE(name, buf);
        return buf;
    } else
        return 0;
}
