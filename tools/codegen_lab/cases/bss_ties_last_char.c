/*
 * @behaviour: Names that differ only in their LAST character have equal BSS
 *   keys, so they keep declaration (definition) order -- renaming the last
 *   character of an uninitialised global never moves it; changing its first,
 *   second or second-to-last character or its length can. Ties keep the
 *   order of FIRST APPEARANCE: an earlier `extern` declaration counts
 *   (tie_b is declared extern before tie_c is defined, so tie_b comes
 *   first although it is defined after tie_c).
 *   Char-sized objects are not aligned (c_two at offset 1) but the next
 *   int is (tie_b at 2). Keys: c_one=19 c_two=91 tie_*=428.
 * @expect-bss:
 *   _c_one@0 _c_two@1 _tie_b@2 _tie_c@4 _tie_a@6
 */
extern int tie_b;
int tie_c;
int tie_b;
int tie_a;
char c_two;
char c_one;

int use(void)
{
    return tie_b;
}
