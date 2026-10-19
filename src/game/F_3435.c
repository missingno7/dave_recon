/*
 * F_3435 -- wait_for_input_flashing()
 * cs [0x3235,0x32cb) / file [0x3435,0x34cb), 150 bytes.
 * Strict match: tools/match_function.py.
 *
 * Flushes a pending keystroke, then repeatedly runs F_1C28, ten
 * (F_7831, F_332C) ticks, F_1C6A, ten more ticks, and polls the input
 * device through F_688C(1) (returns a 6-byte input-state struct by value).
 * Keeps looping while the first word of that state is 8 (apparently "no
 * input") and no key is waiting. Afterwards, if bit 3 of DS:0x6156 (sound
 * options?) is set, plays effect 2 through F_763E.
 *
 * @name wait_for_input (tentative; F_1C28/F_1C6A are a show/hide pair)
 *
 * Codegen notes: a struct-returning call assigned to a local compiles to
 * `push ss; push &dst; <args>; push ss; push &tmp; call; add sp; push ss;
 * push &tmp; mov cx,size; call SCOPY@` -- the hidden return pointer is far.
 */


struct input {
    int dir;
    int b1;
    int b2;
};

extern int D_6156;

int bioskey(int cmd);
void F_1C28(void);
void F_1C6A(void);
void F_7831(void);
void F_332C(void);
struct input F_688C(int mode);
void F_763E(int snd);

void F_3435(void)
{
    int i;
    struct input in;

    if (bioskey(1))
        bioskey(0);
    do {
        F_1C28();
        for (i = 0; i < 10; i++) {
            F_7831();
            F_332C();
        }
        F_1C6A();
        for (i = 0; i < 10; i++) {
            F_7831();
            F_332C();
        }
        in = F_688C(1);
    } while (in.dir == 8 && bioskey(1) == 0);
    if ((D_6156 & 8) == 8)
        F_763E(2);
}
