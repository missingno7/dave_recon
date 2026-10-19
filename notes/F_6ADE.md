# F_6ADE -- read_file_far(name, far buf) -> long -- NOT MATCHED (inline asm)

cs [0x68de,0x6994) / file [0x6ade,0x6b94), 182 bytes.

Opens `name` (INT 21h AH=3Dh), seeks to the end (AX=4202h) to get the file
size, seeks back, then reads it into the far buffer in 64 KB - 1 chunks
(AH=3Fh with DS switched to the buffer segment, advancing the segment by 0x1000
per chunk; `loop` over size_hi + 1 chunks, then a final 1-byte read at
offset -1 per full chunk), closes it (AH=3Eh) and returns the file size
(DX:AX). Callers: F_69D3 (demo load), F_6C1E/F_6C8A (file loaders).

Only the start is compiled C: `int handle; long size = 0; unsigned off = FP_OFF(buf),
seg = FP_SEG(buf); long pos = 0;` (`mov word ptr [bp-4],0` ... `[bp-0xe],0`)
and the epilogue (`return size;` with `xor ax,ax; add ax,[bp-4]; adc dx,0`).
The body is an inline `asm` block: `jb` directly after `int 21h`,
`push cx`/`pop cx` around calls, `push ds`/`mov ds,ax`/`pop ds`, and the
`loop` instruction, none of which TC 1.00 generates from C (pseudo-register
code would emit `pushf/pop` flag tests, never `loop`).

Blocked: inline asm is forbidden here and the toolchain has no TASM.EXE.
