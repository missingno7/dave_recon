#include "rng.h"

void rng_srand(struct game *g, uint16_t seed)
{
    g->rng_seed = seed;
}

int16_t rng_rand(struct game *g)
{
    g->rng_seed = g->rng_seed * RNG_MULTIPLIER + 1u;   /* uint32_t: wraps like the original */
    return (int16_t)((g->rng_seed >> 16) & 0x7FFF);
}

int16_t rng_scaled(struct game *g, int16_t n)
{
    /* 32-bit product and truncating division, as N_LXMUL@ / N_LDIV@ */
    int32_t r = rng_rand(g);
    return (int16_t)(r * n / RNG_MAX);
}
