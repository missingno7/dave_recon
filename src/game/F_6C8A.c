/* @flags -G */
#include <io.h>
#include <fcntl.h>
#include <alloc.h>

extern void far *D_9EC4;
void far *F_6A62(unsigned long size);
long F_6ADE(char *name, char far *buf);
void F_7E00(char huge *src, char far *dst, long size);

char far *F_6C8A(char *name)
{
    long flen, size;
    void far *saved;
    char huge *packed;
    char far *out;
    register int fd;

    if ((fd = open(name, O_BINARY)) != -1) {
        flen = filelength(fd);
        read(fd, &size, 4);
        close(fd);
        out = F_6A62(size);
        saved = D_9EC4;
        packed = F_6A62(flen);
        F_6ADE(name, packed);
        F_7E00(packed + 4, out, size);
        farfree(D_9EC4);
        D_9EC4 = saved;
        return out;
    } else
        return 0;
}
