"""Predict Turbo C++ 1.00's _BSS order and layout for a unit's uninitialised globals.

Rule (fitted on ~800 compiled names, then confirmed on 12 fresh random
modules / 360 names; see docs/compiler-behaviors.md):

    key(name) = name[0]                                     if len(name) == 1
              = (name[0] + 256*name[1] + 8*name[len-2] + 64*len) % 1024 otherwise

`name` is the C identifier WITHOUT the compiler's leading underscore. Variables
are sorted by key, ties kept in definition order; then laid out in that order,
every object except char / char arrays aligned to an even offset (in _BSS
only -- _DATA is never padded without -a).

    python tools/codegen_lab/bss_order.py count:2 lives:2 flag:1 buf:c40
      -> prints offset, name, key for each (size suffix ':c<N>' = char array)
"""
from __future__ import annotations

import sys


def bss_key(name: str) -> int:
    if len(name) == 1:
        return ord(name)
    return (ord(name[0]) + 256 * ord(name[1]) + 8 * ord(name[-2]) + 64 * len(name)) % 1024


def bss_layout(items):
    """items: [(name, size, is_char)] in definition order -> [(offset, name, key)]."""
    order = sorted(enumerate(items), key=lambda e: (bss_key(e[1][0]), e[0]))
    out, off = [], 0
    for _, (name, size, is_char) in order:
        if not is_char and off % 2:
            off += 1
        out.append((off, name, bss_key(name)))
        off += size
    return out


def main(argv):
    items = []
    for a in argv:
        name, _, spec = a.partition(":")
        spec = spec or "2"
        is_char = spec.startswith("c") or spec == "1"
        size = int(spec.lstrip("c") or 1)
        items.append((name, size, is_char))
    for off, name, key in bss_layout(items):
        print(f"{off:5d}  {name:24s} key={key}")


if __name__ == "__main__":
    main(sys.argv[1:])
