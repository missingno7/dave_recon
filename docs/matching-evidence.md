# Matching evidence

Superseded. Matching evidence is now produced mechanically and strictly:

- `python tools/verify_sources.py --json build/verify.json` -- every src/game
  C file and src/asm module, with fixup counts and verdicts (all EXACT).
- `python tools/match_function.py src/game/F_XXXX.c --json` -- full per-fixup
  resolution report for one file.

The 2026-09-19 entry for F_6D64 (a 38-byte "dispatch head" with placeholder
case bodies, matched modulo masked fixups) is withdrawn: src/game/F_6D64.c is
the real function (set_video_mode, 94 bytes incl. its jump table), strictly
EXACT.
