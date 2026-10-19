/*
 * F_1D16 -- move_dave
 * cs [0x1b16,0x2a1f) / file [0x1d16,0x2c1f), 3849 bytes incl. 5 jump tables.
 *
 * Dave's per-frame movement state machine, driven by the requested
 * direction D_57E2 (0 up, 1 up-right, 2 right, 3 down-right, 4 down,
 * 5 down-left, 6 left, 7 up-left, 8 none; consumed by setting it to 8) and
 * the state bits in D_6156:
 *   0x20 alive (else only F_7831), 0x04 walking, 0x08 falling,
 *   0x10 jumping (y deltas from D_00BA[D_579A], 0x80 = apex/end),
 *   0x02 climbing (tile property D_0262[tile] == 1), 0x01 jetpack,
 *   0x40 killed -> state 0, erase Dave, spawn the death explosion
 *   (F_1830 kind 5 arms the death timer handled by F_15A5).
 * Collision probes: F_2C70(dx, dy) -> 0 free, 1 solid, 2 deadly;
 * F_2CD8(dx, dy) -> tile index. Movement speed is throttled by D_5794.
 * Every branch ends with the same redraw: erase (F_1C28) / draw (F_1C6A)
 * Dave around the frame wait F_7831, ordered by whether Dave is in the upper
 * or lower part of the screen (y < 100) to avoid flicker.
 * @name move_dave -- evidence: all writes to Dave x/y (D_56EA/D_56EC) and
 * his sprite (D_573E/D_57E4), death on deadly tiles, jump/climb/jetpack.
 *
 * Codegen (-G): sequential `if (state & bit) { ...; return; }` blocks (no
 * else: a `return` jumps straight to the epilogue and no dead jmp follows);
 * `D_5794--;` as a statement then `if (D_5794 > 0 ...)` gives dec/cmp [m],0;
 * `y = ++y & 0xff` gives inc [m]; mov ax,[m]; and; mov [m],ax; the first
 * and last case of a switch-with-table need no particular order: TCC emits
 * case bodies in source order (6,2,0,1/7 here) and the table by value; a
 * missing break on the last case of the small inner switches is required
 * (no trailing jmp). Register vars: moved = SI, t = DI, hit on the stack.
 */

extern int D_6156;              /* Dave state bits */
extern int D_5794;
extern int D_57E2;              /* requested direction 0..7, 8 = none */
extern int D_579E;              /* previous direction */
extern int D_5740;              /* facing: 0 left, 1 right */
extern int D_56EA;              /* Dave x */
extern int D_56EC;              /* Dave y */
extern int D_6548;              /* animation delay */
extern int D_6150;              /* animation frame 0..3 */
extern int D_4F86;              /* gfx index */
extern int D_573E;              /* Dave sprite */
extern int D_57E4;              /* Dave mask */
extern int D_579A;              /* jump table position */
extern int D_57E6;              /* jetpack facing */
extern int D_00BA[];            /* jump y-delta table, 0x80 terminated */
extern int D_0262[];            /* tile is climbable */
extern int D_0336[];
extern int D_033C[];
extern int D_01D2[];
extern int D_01D8[];
extern int D_01DE[];
extern int D_01E4[];
extern int D_0436[];
extern int D_044E[];
extern int D_0466[];
extern int D_047E[];
extern int D_03A6[];
extern int D_03BE[];
extern int D_03D6[];
extern int D_03EE[];
void F_7831(void);
int F_2C70(int, int);
int F_2CD8(int, int);
void F_763E(int);
void F_46B0(void);
void F_769B(void);
void F_2C1F(void);
void F_1C28(void);
void F_1C6A(void);
void F_1830(int, int, int);

void F_1D16(void)
{
    int moved;
    int t;
    int hit;

    moved = 0;
    if (D_6156 & 0x20) {
        D_5794--;
        if (D_5794 > 0 && (D_6156 & 4) || D_5794 > 3 && (D_6156 & 8) ||
            D_5794 > 1 && ((D_6156 & 0x10) || (D_6156 & 2))) {
            F_7831();
            return;
        }
        D_5794 = 3;

        if (D_6156 & 4) {
            switch (D_57E2) {
            case 6:
                if (D_579E == 2 && F_2C70(-2, 0) == 0) {
                    D_56EA -= 2;
                    D_579E = D_57E2;
                    moved++;
                }
                D_5740 = 0;
                if (F_2C70(-2, 0) == 1) {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    F_763E(1);
                    break;
                }
                if (F_2C70(0, 0) == 2) {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                    break;
                }
                if (F_2C70(2, 0x10) == 0 && F_2C70(8, 0x10) == 0) {
                    F_763E(2);
                    D_6156 = D_6156 & 0xfb | 8;
                    D_56EC = ++D_56EC & 0xff;
                    D_56EA--;
                    moved++;
                }
                if (F_2C70(2, 0x10) == 2) {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                    break;
                }
                if (--D_6548 == 0) {
                    D_6548 = 2;
                    D_6150 = ++D_6150 & 3;
                }
                t = D_4F86 * 4 + D_6150;
                D_573E = D_0436[t];
                D_57E4 = D_044E[t];
                D_56EA -= 2;
                F_46B0();
                F_763E(4);
                moved++;
                D_57E2 = 8;
                break;
            case 2:
                if (D_579E == 6 && F_2C70(0xd, 0) == 0) {
                    D_56EA += 2;
                    moved++;
                    D_579E = D_57E2;
                }
                D_5740 = 1;
                if (F_2C70(0xf, 0) == 1) {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    F_763E(1);
                    break;
                }
                if (F_2C70(0xd, 0) == 2) {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                    break;
                }
                if (F_2C70(5, 0x10) == 0 && F_2C70(0xb, 0x10) == 0) {
                    F_763E(2);
                    D_6156 = D_6156 & 0xfb | 8;
                    D_56EC = ++D_56EC & 0xff;
                    D_56EA++;
                    moved++;
                }
                if (F_2C70(9, 0x10) == 2) {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                    break;
                }
                if (--D_6548 == 0) {
                    D_6548 = 2;
                    D_6150 = ++D_6150 & 3;
                }
                t = D_4F86 * 4 + D_6150;
                D_573E = D_0466[t];
                D_57E4 = D_047E[t];
                D_56EA += 2;
                F_46B0();
                F_763E(4);
                moved++;
                D_579E = D_57E2;
                D_57E2 = 8;
                break;
            case 0:
                if (D_0262[F_2CD8(6, -2)] == 1) {
                    D_6156 = D_6156 & 0xfb | 2;
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    D_573E = D_0336[D_4F86];
                    D_57E4 = D_033C[D_4F86];
                    break;
                }
            case 1:
            case 7:
                D_579A = 0;
                F_763E(5);
                D_6156 = D_6156 & 0xfb | 0x10;
                if (D_57E2 == 0) {
                    switch (D_5740) {
                    case 0:
                        D_573E = D_01D2[D_4F86];
                        D_57E4 = D_01DE[D_4F86];
                        break;
                    case 1:
                        D_573E = D_01D8[D_4F86];
                        D_57E4 = D_01E4[D_4F86];
                    }
                } else {
                    D_573E = D_01D8[D_4F86];
                    D_57E4 = D_01E4[D_4F86];
                    D_5740 = 1;
                    if (D_57E2 == 7) {
                        D_573E = D_01D2[D_4F86];
                        D_57E4 = D_01DE[D_4F86];
                        D_5740 = 0;
                    }
                }
                D_579E = D_57E2;
                D_57E2 = 8;
                break;
            }
            if (moved) {
                if (D_56EC >= 100)
                    F_7831();
                F_1C28();
                F_1C6A();
                if (D_56EC < 100)
                    F_7831();
            } else
                F_7831();
            return;
        }

        if (D_6156 & 8) {
            switch (D_57E2) {
            case 0:
            case 4:
                D_579E = D_57E2;
                D_57E2 = 8;
                break;
            case 5:
            case 6:
            case 7:
                if (F_2C70(-2, 6) != 1 && F_2C70(-4, 0xf) != 1) {
                    D_56EA--;
                    D_573E = D_0436[D_4F86 * 4];
                    D_57E4 = D_044E[D_4F86 * 4];
                    F_46B0();
                    moved++;
                } else {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                }
                D_5740 = 0;
                break;
            case 1:
            case 2:
            case 3:
                if (F_2C70(0xd, 6) != 1 && F_2C70(0xf, 0xf) != 1) {
                    D_56EA++;
                    D_573E = D_0466[D_4F86 * 4];
                    D_57E4 = D_047E[D_4F86 * 4];
                    F_46B0();
                    moved++;
                } else {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                }
                D_5740 = 1;
                break;
            }
            t = F_2C70(5, 0x11) | F_2C70(8, 0x11);
            switch (t) {
            case 0:
                D_56EC = ++D_56EC & 0xff;
                moved++;
                break;
            case 1:
                D_573E = D_0436[D_4F86 * 4 + 1];
                D_57E4 = D_044E[D_4F86 * 4 + 1];
                if (D_579E == 0 || D_579E == 4 || D_579E == 8) {
                    D_573E = D_0336[D_4F86];
                    D_57E4 = D_033C[D_4F86];
                }
                if (D_579E == 2 || D_579E == 1 || D_579E == 3) {
                    D_573E = D_0466[D_4F86 * 4 + 1];
                    D_57E4 = D_047E[D_4F86 * 4 + 1];
                }
                D_6156 = D_6156 & 0xf7 | 4;
                D_56EC = ++D_56EC & 0xf0;
                F_769B();
                moved++;
                break;
            case 2:
                D_57E2 = 8;
                F_769B();
                F_763E(3);
                D_6156 = D_6156 & 0xe0 | 0x40;
            }
            if (moved) {
                if (D_56EC >= 100)
                    F_7831();
                F_1C28();
                F_1C6A();
                if (D_56EC < 100)
                    F_7831();
            } else
                F_7831();
            return;
        }

        if (D_6156 & 0x10) {
            switch (D_57E2) {
            case 6:
            case 7:
                D_579E = D_57E2;
                D_57E2 = 8;
                D_5740 = 0;
                if (D_0262[F_2CD8(-2, -2)] == 1) {
                    D_6156 = D_6156 & 0xef | 2;
                    break;
                }
                if ((F_2C70(-4, 2) | F_2C70(0, 0xf)) == 1)
                    break;
                if ((F_2C70(-2, 2) | F_2C70(2, 0xd)) == 2) {
                    F_769B();
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                }
                D_573E = D_01D2[D_4F86];
                D_57E4 = D_01DE[D_4F86];
                D_56EA -= 2;
                F_46B0();
                break;
            case 1:
            case 2:
                D_579E = D_57E2;
                D_57E2 = 8;
                D_5740 = 1;
                if (D_0262[F_2CD8(0xd, -2)] == 1) {
                    D_6156 = D_6156 & 0xef | 2;
                    break;
                }
                if ((F_2C70(0xf, 2) | F_2C70(0xd, 0xf)) == 1)
                    break;
                if ((F_2C70(0xd, 2) | F_2C70(0xd, 0xd)) == 2) {
                    F_769B();
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                }
                D_573E = D_01D8[D_4F86];
                D_57E4 = D_01E4[D_4F86];
                D_56EA += 2;
                F_46B0();
                break;
            }
            t = D_00BA[D_579A];
            if (t == 0x80) {
                t = 0;
                D_6156 = D_6156 & 0xef | 8;
            }
            if (t > 0) {
                hit = F_2C70(4, t + 0xf) | F_2C70(0xb, t + 0xf);
                if (hit == 2) {
                    F_769B();
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                }
                if (hit == 1) {
                    F_769B();
                    D_6156 = D_6156 & 0xef | 4;
                    D_56EC = (D_56EC + t) & 0xf0;
                    t = 0;
                    D_573E = D_0436[D_4F86 * 4 + 1];
                    D_57E4 = D_044E[D_4F86 * 4 + 1];
                    if (D_579E == 2 || D_579E == 1 || D_579E == 3) {
                        D_573E = D_0466[D_4F86 * 4 + 1];
                        D_57E4 = D_047E[D_4F86 * 4 + 1];
                    }
                    D_579E = D_57E2;
                    D_57E2 = 8;
                }
            }
            if (t < 0) {
                hit = F_2C70(4, t + 1) | F_2C70(9, t + 1);
                if (hit == 2) {
                    F_769B();
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                }
                if (hit == 1) {
                    D_6156 = D_6156 & 0xef | 8;
                    t = 0;
                    D_56EC = --D_56EC & 0xff;
                }
            }
            D_56EC = (D_56EC + t) & 0xff;
            D_579A++;
            if (D_56EC >= 100)
                F_7831();
            F_1C28();
            F_1C6A();
            if (D_56EC < 100)
                F_7831();
            return;
        }

        if (D_6156 & 2) {
            switch (D_57E2) {
            case 1:
                D_579A = 0;
                F_763E(5);
                D_6156 = D_6156 & 0xfd | 0x10;
                D_579E = D_57E2;
                D_57E2 = 8;
                D_56EA += 2;
                D_56EC -= 2;
                F_46B0();
                D_5740 = 1;
                moved++;
                break;
            case 7:
                D_579A = 0;
                F_763E(5);
                D_6156 = D_6156 & 0xfd | 0x10;
                D_579E = D_57E2;
                D_57E2 = 8;
                D_56EA -= 2;
                D_56EC -= 2;
                F_46B0();
                D_5740 = 0;
                moved++;
                break;
            case 0:
                if (D_0262[F_2CD8(6, -2)] == 1) {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    D_56EC -= 2;
                    F_763E(4);
                    F_2C1F();
                } else {
                    D_579A = 0;
                    F_763E(5);
                    D_6156 = D_6156 & 0xfd | 0x10;
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    D_56EC -= 2;
                }
                moved++;
                break;
            case 4:
                if (D_0262[F_2CD8(6, 0x10)] == 1) {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    F_763E(4);
                    D_56EC += 2;
                    F_763E(4);
                    F_2C1F();
                    moved++;
                } else {
                    D_6156 = D_6156 & 0xfd | 8;
                }
                break;
            case 6:
                if (D_0262[F_2CD8(0, 8)] == 1) {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    D_56EA -= 2;
                    F_46B0();
                    F_763E(4);
                    F_2C1F();
                    moved++;
                } else {
                    D_6156 = D_6156 & 0xfd | 8;
                }
                D_5740 = 0;
                break;
            case 2:
                if (D_0262[F_2CD8(0xd, 8)] == 1) {
                    D_579E = D_57E2;
                    D_57E2 = 8;
                    D_56EA += 2;
                    F_46B0();
                    F_763E(4);
                    F_2C1F();
                    moved++;
                } else {
                    D_6156 = D_6156 & 0xfd | 8;
                }
                D_5740 = 1;
                break;
            }
            if (moved) {
                if (D_56EC >= 100)
                    F_7831();
                F_1C28();
                F_1C6A();
                if (D_56EC < 100)
                    F_7831();
            } else
                F_7831();
            return;
        }

        if (D_6156 & 1) {
            F_763E(9);
            switch (D_57E2) {
            case 0:
            case 1:
            case 7:
                D_579E = D_57E2;
                D_57E2 = 8;
                t = F_2C70(2, 0) | F_2C70(0xb, 0);
                if ((t & 1) == 1) {
                    D_6156 = D_6156 & 0xfe | 1;
                    break;
                }
                if (t == 2) {
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                    break;
                }
                if (D_56EC > 0)
                    D_56EC--;
                moved++;
                break;
            case 4:
                D_579E = D_57E2;
                D_57E2 = 8;
                t = F_2C70(2, 0x10) | F_2C70(0xb, 0x10);
                if ((t & 1) == 1) {
                    D_6156 = D_6156 & 0xfe | 1;
                    break;
                }
                if (t == 2) {
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                    break;
                }
                if (D_56EC < 0xaa)
                    D_56EC++;
                else {
                    D_6156 = D_6156 & 0xfe | 8;
                    D_573E = D_0336[D_4F86];
                    D_57E4 = D_033C[D_4F86];
                }
                moved++;
                break;
            case 6:
                D_579E = D_57E2;
                D_57E2 = 8;
                D_5740 = 0;
                t = F_2C70(-2, 4) | F_2C70(-2, 0xc);
                if (t == 1)
                    break;
                if (t == 2) {
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                    break;
                }
                D_56EA--;
                moved++;
                F_46B0();
                D_57E6 = 0;
                break;
            case 2:
                D_579E = D_57E2;
                D_57E2 = 8;
                D_5740 = 1;
                t = F_2C70(0xd, 4) | F_2C70(0xd, 0xc);
                if (t == 1)
                    break;
                if (t == 2) {
                    F_763E(3);
                    D_6156 = D_6156 & 0xe0 | 0x40;
                    break;
                }
                D_56EA++;
                moved++;
                F_46B0();
                D_57E6 = 1;
                break;
            }
            if (--D_6548 == 0) {
                D_6548 = 4;
                D_6150 = ++D_6150 & 3;
                if (D_57E6 == 0) {
                    D_573E = D_03D6[D_4F86 * 4 + D_6150];
                    D_57E4 = D_03EE[D_4F86 * 4 + D_6150];
                } else {
                    D_573E = D_03A6[D_4F86 * 4 + D_6150];
                    D_57E4 = D_03BE[D_4F86 * 4 + D_6150];
                }
                moved++;
            }
            if (moved) {
                if (D_56EC >= 100)
                    F_7831();
                F_1C28();
                F_1C6A();
                if (D_56EC < 100)
                    F_7831();
            } else
                F_7831();
            return;
        }

        if (D_6156 & 0x40) {
            D_6156 = 0;
            F_1C28();
            F_1830(D_56EA, D_56EC + 3, 5);
        }
    } else
        F_7831();
}
