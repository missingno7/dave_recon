/*
 * @behaviour: _BSS order is NOT declaration order. Turbo C++ 1.00 sorts a
 *   unit's uninitialised variables by
 *       key = (n[0] + 256*n[1] + 8*n[len-2] + 64*len) mod 1024
 *   (n = the C name without the leading underscore; for a 1-character name
 *   key = n[0]), ties in declaration order. The LAST character never
 *   matters. (The Turbo C 2.0 rule first + 4*last + 32*len mod 1024 is
 *   refuted -- see ties_last_char.) Then objects are laid out in that order,
 *   word-aligning everything except char / char arrays (even without -a,
 *   unlike _DATA). Fitted on ~800 names and confirmed on 12 fresh random
 *   modules (360 names, mixed types); tools/codegen_lab/bss_order.py
 *   implements it.
 *   Keys: count=19 a=97 b=98 c=99 x9=440 lives=468 abc=561 zz=714.
 * @expect-bss:
 *   _count@0 _a@2 _b@4 _c@6 _x9@8 _lives@10 _abc@12 _zz@14
 */
int count;
int zz;
int c;
int abc;
int b;
int lives;
int x9;
int a;
