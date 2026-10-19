"""Storage names that make Turbo C++ 1.00 lay out a unit's _BSS in the original order.

TC++ 1.00 does not keep uninitialised globals in declaration order: it sorts
them by a hash of the NAME (docs/compiler-behaviors.md, `_BSS`):

    key = (n[0] + 256*n[1] + 8*n[len-2] + 64*len) mod 1024     (n[0] for 1-char names)

ties in order of first appearance. So the original layout is a property of the
original names, which are lost. We recover the layout instead (the duke1_recon
technique): every variable keeps its readable name in the code, and where that
name would hash into the wrong slot the definition uses a STORAGE name chosen
to hash into the right one, bound by `#define readable storage` in src/DAVE.H.

Algorithm (per unit, variables in original address order):
  1. keys of the readable names; the longest non-decreasing run of them keeps
     its names (ties are fine: DAVE.H declares every variable `extern` in
     address order before any definition, so first appearance = address order);
  2. every other variable gets a storage name whose key equals the key of the
     nearest kept variable before it (or after it, at the start of the unit),
     so the whole key sequence is non-decreasing;
  3. storage name = readable name + "_" + c + "h", with c chosen so that
     n[len-2] = c gives the target key (a "_" is inserted before it when the
     length has to change). "h" (for hash) is the last character, which the
     hash ignores.

The input is layout/bss-map.json (the game BSS map: per unit, every variable
with its DS offset, size and char-ness, plus padding). This tool fills in
`storage` (`--solve`), and checks (`--check`, also run by the test suite):
  * bss_order's predicted layout of the storage names reproduces every DS
    offset and the unit's _BSS length;
  * src/DAVE.H has exactly the `#define readable storage` lines this map
    implies, and declares each unit's variables in address order.
The compiler itself is the final judge: tools/verify_sources.py resolves
every _BSS reference through the unit's own _BSS base and the object's
symbol offsets.

Usage:
    python tools/bss_names.py --solve      # (re)compute storage names into the map
    python tools/bss_names.py --check
    python tools/bss_names.py --defines    # print the #define block for DAVE.H
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import string
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "codegen_lab"))
from bss_order import bss_key, bss_layout  # noqa: E402

MAP = ROOT / "layout" / "bss-map.json"
HEADER = ROOT / "src" / "DAVE.H"
CHARS = string.ascii_lowercase + string.digits + string.ascii_uppercase


def load():
    return json.loads(MAP.read_text())


def lnds(keys):
    """Indices of a longest non-decreasing subsequence (earliest on ties)."""
    import bisect
    tails, tails_idx, prev = [], [], [None] * len(keys)
    for i, k in enumerate(keys):
        pos = bisect.bisect_right(tails, k)
        if pos == len(tails):
            tails.append(k); tails_idx.append(i)
        else:
            tails[pos] = k; tails_idx[pos] = i
        prev[i] = tails_idx[pos - 1] if pos else None
    out, i = [], tails_idx[-1] if tails_idx else None
    while i is not None:
        out.append(i); i = prev[i]
    return sorted(out)


def storage_name(readable: str, lo: int, hi: int) -> str:
    """Shortest readable + "_" [+ "_"...] + c + "h" whose key lies in [lo, hi];
    among equally short ones the lowest key (leaves room for later names)."""
    for pad in range(0, 16):
        best = None
        for c in CHARS:
            name = readable + "_" + "_" * pad + c + "h"
            k = bss_key(name)
            if lo <= k <= hi and (best is None or k < best[0]):
                best = (k, name)
        if best:
            return best[1]
    raise SystemExit(f"no storage name for {readable} with key in [{lo}, {hi}]")


def solve_unit(variables):
    """Readable names on a longest non-decreasing key run stay; each other
    variable gets the shortest storage name keeping the sequence non-decreasing
    (key between the previous name's key and the next kept name's key)."""
    keys = [bss_key(v["name"]) for v in variables]
    keep = set(lnds(keys))
    out, lo = [], 0
    for i, v in enumerate(variables):
        if i in keep:
            out.append(v["name"])
            lo = keys[i]
            continue
        after = [j for j in keep if j > i]
        hi = keys[min(after)] if after else 1023
        name = storage_name(v["name"], lo, hi)
        lo = bss_key(name)
        out.append(name)
    return out


def unit_vars(unit):
    return [e for e in unit["entries"] if e["kind"] == "variable"]


def predicted(unit):
    items = [(v["storage"], v["size"], v["char"]) for v in unit_vars(unit)]
    return {name: off for off, name, _ in bss_layout(items)}


def check(doc) -> list:
    problems = []
    defines = []
    for unit in doc["units"]:
        lay = predicted(unit)
        base = unit["bss"][0]
        for v in unit_vars(unit):
            want = v["ds"] - base
            got = lay.get(v["storage"])
            if got != want:
                problems.append(f"{unit['unit']}: {v['name']} ({v['storage']}) predicted at "
                                f"+{got} but lies at +{want} (DS {v['ds']:#06x})")
            if v["storage"] != v["name"]:
                defines.append((v["name"], v["storage"]))
        last = max(unit_vars(unit), key=lambda v: v["ds"])
        end = last["ds"] + last["size"]
        if end != unit["bss"][1]:
            problems.append(f"{unit['unit']}: variables end at {end:#06x}, _BSS ends at {unit['bss'][1]:#06x}")
    if HEADER.exists():
        h = HEADER.read_text(encoding="latin1")
        found = re.findall(r"^#define\s+(g_\w+)\s+(\1_+[A-Za-z0-9]h)\s*$", h, re.M)
        if sorted(found) != sorted(defines):
            missing = sorted(set(defines) - set(found))
            extra = sorted(set(found) - set(defines))
            problems.append(f"DAVE.H storage #defines differ: missing {missing}, extra {extra}")
        # declaration order = address order, per unit
        decl_pos = {}
        for m in re.finditer(r"^extern\b[^;]*?\b(g_\w+)\s*(\[[^;]*)?;", h, re.M):
            decl_pos.setdefault(m.group(1), m.start())
        for unit in doc["units"]:
            pos = [decl_pos.get(v["name"]) for v in unit_vars(unit)]
            if None in pos:
                miss = [v["name"] for v, p in zip(unit_vars(unit), pos) if p is None]
                problems.append(f"DAVE.H lacks extern declarations of {miss}")
            elif pos != sorted(pos):
                problems.append(f"DAVE.H declares {unit['unit']}'s _BSS variables out of address order")
    return problems


def markdown(doc) -> str:
    """docs/bss-map.md: the game _BSS map as tables."""
    lo, hi = doc["range"]
    out = ["# Game _BSS map (DS 0x%04X-0x%04X)" % (lo, hi), "",
           "Generated by `python tools/bss_names.py --doc` from `layout/bss-map.json`; do",
           "not edit by hand. Offsets and sizes are verified by `tools/verify_sources.py`",
           "(every _BSS reference of every unit resolves through the unit's own _BSS base",
           "and the object's symbol offsets, which follow from the storage names);",
           "`tests/test_link_probe.py` shows TLINK producing the same layout.",
           "", "| unit | DS range | bytes | variables | storage names | padding |", "|---|---|---|---|---|---|"]
    for u in doc["units"]:
        vs = unit_vars(u)
        pads = [e for e in u["entries"] if e["kind"] == "padding"]
        out.append(f"| {u['unit']}.C | 0x{u['bss'][0]:04X}-0x{u['bss'][1]:04X} | {u['bss'][1] - u['bss'][0]} "
                   f"| {len(vs)} | {sum(v['storage'] != v['name'] for v in vs)} "
                   f"| {', '.join('0x%04X' % p['ds'] for p in pads) or '-'} |")
    out += ["", "Next: CS.LIB's _BSS from 0x%04X (`__atexittbl`), then `_BSSEND`; C0S clears" % hi,
            "[0x4C60, 0x9F12) at start-up.", "",
            "Which unit DEFINES a variable is not visible in the bytes (all units",
            "reference each other's globals through DGROUP); see docs/link-forensics.md",
            "for the evidence behind the assignment. Unreferenced holes are kept as",
            "`g_unused_XXXX` variables (their size and position are exact, their type is not).", ""]
    for u in doc["units"]:
        out += [f"## {u['unit']}.C  (DS 0x{u['bss'][0]:04X}-0x{u['bss'][1]:04X})", "",
                "| DS | size | name | storage name (hash key) | type | notes |", "|---|---|---|---|---|---|"]
        for e in u["entries"]:
            if e["kind"] == "padding":
                out.append(f"| 0x{e['ds']:04X} | {e['size']} | *(padding)* | | | {e['reason']} |")
                continue
            st = e["storage"] if e["storage"] != e["name"] else "="
            out.append(f"| 0x{e['ds']:04X} | {e['size']} | `{e['name']}` | `{st}` ({e.get('key', bss_key(e['storage']))}) "
                       f"| `{e['type']}` | {e.get('comment', '')} |")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solve", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--defines", action="store_true")
    ap.add_argument("--doc", action="store_true", help="write docs/bss-map.md")
    args = ap.parse_args()
    doc = load()
    if args.doc:
        (ROOT / "docs" / "bss-map.md").write_text(markdown(doc), encoding="utf-8")
        print("wrote docs/bss-map.md")
        return
    if args.solve:
        for unit in doc["units"]:
            vs = unit_vars(unit)
            for v, s in zip(vs, solve_unit(vs)):
                v["storage"] = s
                v["key"] = bss_key(s)
        MAP.write_text(json.dumps(doc, indent=1) + "\n")
        print("storage names written to", MAP.relative_to(ROOT))
    if args.defines:
        for unit in doc["units"]:
            print(f"/* {unit['unit']}.C _BSS */")
            for v in unit_vars(unit):
                if v["storage"] != v["name"]:
                    print(f"#define {v['name']} {v['storage']}")
    if args.check or not (args.solve or args.defines):
        problems = check(doc)
        for p in problems:
            print("FAIL", p)
        if problems:
            sys.exit(1)
        n = sum(len(unit_vars(u)) for u in doc["units"])
        r = sum(1 for u in doc["units"] for v in unit_vars(u) if v["storage"] != v["name"])
        print(f"ok: {n} _BSS variables in {len(doc['units'])} units, {r} storage names")


if __name__ == "__main__":
    main()
