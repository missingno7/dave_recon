/*
 * F_6C1E -- load_file
 * cs [0x6a1e,0x6a8a) / file [0x6c1e,0x6c8a), 108 bytes. Strict match: tools/match_function.py.
 *
 * Opens a file (O_BINARY), allocates filelength bytes with
 * farmalloc_aligned, reads it with F_6ADE and returns the buffer (NULL if it
 * cannot be opened).
 *
 * Evidence for the name: open/filelength/close/F_6ADE.
 *
 * Codegen: if/else with returns in both arms emits a dead jmp after `return
 * buf`.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name load_file
 */

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
