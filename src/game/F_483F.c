/*
 * F_483F -- object_exists(id)
 * cs [0x463f,0x4686) / file [0x483f,0x4886), 71 bytes.
 * Strict match: tools/match_function.py.
 *
 * Like F_47F8 but returns 1 if an active record with word +0x0C == id
 * exists in the 5-entry table at DS:0x56F6, else 0.
 *
 * @name object_exists
 */
/* @flags -G */
struct obj {
    int active;
    int f2, f4, f6, f8, fa;
    int id;
};

extern struct obj D_56F6[];     /* 5 objects, 14 bytes each */
int F_483F(int id)
{
    register int i;

    for (i = 0; i < 5; i++)
        if (D_56F6[i].active == 1 && D_56F6[i].id == id)
            return 1;
    return 0;
}
