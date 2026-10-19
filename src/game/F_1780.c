/*
 * F_1780 -- update_jetpack
 * cs [0x1580,0x1630) / file [0x1780,0x1830), 176 bytes.
 *
 * While the jetpack is on (D_6156 bit 0) every 15 frames consumes one unit
 * of fuel (D_5798) and erases one segment of the fuel bar; when it runs
 * out, switches Dave back to walking, removes the trophy indicator(?),
 * plays sound 2 and restores Dave's normal sprites.
 * @name update_jetpack -- evidence: bar drawn at x = 0x4A + 2*D_5798.
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 */

extern int D_6156;
extern int D_6154;
extern int D_4F86;
extern int D_5798;
extern int D_4F8A;
extern int D_0208;
extern int D_020A[];
extern int D_0336[];
extern int D_033C[];
extern int D_0348[];
extern int D_579E;
extern int D_57E2;
extern int D_573E;
extern int D_57E4;
void F_1BD6(int, int, int);
void F_371F(void);
void F_763E(int);

void F_1780(void)
{
    if (D_6156 & 1) {
        if (--D_6154 == 0) {
            D_6154 = 0xf;
            F_1BD6(D_5798 * 2 + 0x4a, 0xae, D_0348[D_4F86]);
            D_5798--;
            if (D_5798 == 0) {
                F_371F();
                D_6156 = D_6156 & 0xe0 | 8;
                D_4F8A = 0;
                F_1BD6(0, 0xaa, D_020A[D_4F86 * D_0208]);
                F_763E(2);
                D_579E = D_57E2;
                D_57E2 = 8;
                D_573E = D_0336[D_4F86];
                D_57E4 = D_033C[D_4F86];
            }
        }
    }
}
