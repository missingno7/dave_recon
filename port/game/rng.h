/*
 * Borland C++ rand()/srand(), reproduced exactly on game.rng_seed (U-S1,
 * docs/state-model.md section 3).
 *
 * The original links CS.LIB's rand: Seed = Seed * 0x015A4E35 + 1 (32-bit,
 * wrapping), result (Seed >> 16) & 0x7FFF; srand(seed) sets Seed = seed
 * (an unsigned int, so the high word becomes 0). Callers scale it with
 * `(long)rand() * n / 32767` in 32-bit arithmetic, which can equal n for
 * rand() == 32767 (U-M1 items 4 and 5): rng_scaled() keeps that.
 */
#ifndef DAVE_RNG_H
#define DAVE_RNG_H

#include <stdint.h>
#include "state.h"

#define RNG_MULTIPLIER 0x015A4E35u
#define RNG_MAX 32767

void    rng_srand(struct game *g, uint16_t seed);
int16_t rng_rand(struct game *g);
/* (long)rand() * n / 32767: 0 .. n (n only for rand() == 32767) */
int16_t rng_scaled(struct game *g, int16_t n);

#endif
