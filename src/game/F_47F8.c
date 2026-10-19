/*
 * F_47F8 -- find_object(id)
 * cs [0x45f8,0x463f) / file [0x47f8,0x483f), 71 bytes.
 * Strict match: tools/match_function.py.
 *
 * Scans the 5-entry table of 14-byte records at DS:0x56F6 and returns the
 * index of the first record whose word 0 is 1 (active) and whose word at
 * +0x0C equals id; -1 if none.
 *
 * @name find_object
 */
/* @flags -G */
struct obj {
    int active;
    int f2, f4, f6, f8, fa;
    int id;
};

extern struct obj D_56F6[];     /* 5 objects, 14 bytes each */
int F_47F8(int id)
{
    register int i;

    for (i = 0; i < 5; i++)
        if (D_56F6[i].active == 1 && D_56F6[i].id == id)
            return i;
    return -1;
}
