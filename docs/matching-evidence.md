# Matching evidence

Superseded. Matching evidence is now produced mechanically and strictly:

- `python tools/verify_sources.py --json build/verify.json` -- the three C
  translation units (src/*.C) and every src/asm module, with fixup counts,
  verdicts (all EXACT) and the whole-program layout check.
- `python tools/link_probe.py` -- TLINK links everything; the load module is
  compared with the original.

The 2026-09-19 entry for F_6D64 (a 38-byte "dispatch head" with placeholder
case bodies, matched modulo masked fixups) is withdrawn: set_video_mode in src/HARDWARE.C is
the real function (set_video_mode, 94 bytes incl. its jump table), strictly
EXACT.
