/*
 * F_6C8A -- load_rle_file
 * cs [0x6a8a,0x6b64) / file [0x6c8a,0x6d64), 218 bytes. Strict match: tools/match_function.py.
 *
 * Loads a compressed file: reads the 4-byte unpacked size, allocates the
 * output, loads the packed file into a temporary block and decompresses it
 * (F_7E00) from offset 4, then frees the temporary block and restores
 * D_9EC4.
 *
 * Evidence for the name: farfree of the temporary, decompressor call F_7E00.
 *
 * Codegen: `packed` is a huge pointer (packed + 4 via N_PADD@).
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name load_rle_file
 */
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
