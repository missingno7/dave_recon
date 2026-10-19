/*
 * F_4997 -- title_handle_key()
 * cs [0x4797,0x4827) / file [0x4997,0x4a27), 144 bytes.
 * Strict match: tools/match_function.py.
 *
 * Peeks at the keyboard (bioskey(1)) and dispatches on the scan code:
 * F1 (0x3B) -> F_0EDF, F2 (0x3C) -> F_5DD5, F3 (0x3D) -> F_0E57,
 * F9 (0x43) -> F_12B9, Esc (0x01) / F10 (0x44) -> F_124B. Any other key
 * while DS:0x00AA == 1 (attract/demo mode) restores the 1000-byte (100x10)
 * tile grid from the backup at DS:0x615C into the current level grid
 * (pointer DS:0x57A8), clears demo mode and starts a new game: F_769B,
 * F_535A (init_game_state), F_4E69, F_13FF, F_3435.
 *
 * @name handle_menu_key
 */
/* @flags -G */

extern int D_00AA;              /* demo / attract mode flag */
extern char D_615C[];           /* saved 100x10 tile grid */
extern char *D_57A8;            /* current level tile grid */

int bioskey(int cmd);
void movmem(void *src, void *dest, unsigned length);
void F_0EDF(void);
void F_5DD5(void);
void F_0E57(void);
void F_12B9(void);
void F_124B(void);
void F_769B(void);
void F_535A(void);
void F_4E69(void);
void F_13FF(void);
void F_3435(void);

void F_4997(void)
{
    int key;

    key = bioskey(1) >> 8;
    switch (key) {
    case 0x3b: F_0EDF(); break;
    case 0x3c: F_5DD5(); break;
    case 0x3d: F_0E57(); break;
    case 0x43: F_12B9(); break;
    case 1:
    case 0x44: F_124B(); break;
    default:
        if (D_00AA == 1 && key != 0) {
            movmem(D_615C, D_57A8, 1000);
            D_00AA = 0;
            F_769B();
            F_535A();
            F_4E69();
            F_13FF();
            F_3435();
        }
    }
}
