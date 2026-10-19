"""Turbo C++ 1.00 codegen catalog: compile every case and check it against its expectation.

Each tools/codegen_lab/cases/*.c opens with a /* ... */ header of `@key: value`
lines (a value continues on the following lines until the next `@key`, a blank
line, or the end of the comment):

  @behaviour:   the rule the case demonstrates (free text, not checked)
  @flags:       extra TCC switches for this case, appended to RECOMMENDED
  @original:    START END -- the case's _TEXT must reproduce file offsets
                [START, END) of build/DAVE_unpacked.exe modulo fixups (the
                tools/match_function.py standard); a real-function case
  @expect-text: hex bytes of the WHOLE _TEXT segment; `..` marks a byte that
                must be covered by a FIXUPP (an address the linker fills in)
  @expect-data: hex bytes of the whole _DATA segment
  @expect-bss:  public names in _BSS, in offset order (`name@offset` pairs)
  @expect-segs: one `NAME CLASS ALIGN LENGTH` line per SEGDEF, in order
                (the unit's file stem in a segment name is written MOD)
  @asm-contains / @asm-absent: one disassembly substring per line that must
                (not) appear in _TEXT ("mov bx, word ptr [bp + 4]")
  @contrast:    one switch set per line; compiled with RECOMMENDED + @flags +
                that set, the primary expectation (@original or @expect-text,
                @expect-data, @expect-bss) must FAIL -- evidence that the flag
                is observable and that the recommended setting is the right one
  @same-as:     one switch set per line whose _TEXT and _DATA must be
                byte-identical to the primary compile (the flag has no
                observable effect on this code)

All compiles of all cases run in ONE DOSBox-X session (tools/tcc_batch.py).

Usage:
    python tools/codegen_lab/run.py               # check all cases
    python tools/codegen_lab/run.py -k switch     # only cases whose name contains "switch"
    python tools/codegen_lab/run.py --show NAME   # print the case's disassembly
    python tools/codegen_lab/run.py --bless NAME  # (re)write NAME's @expect-text/-data/-bss
                                                    from the current compile
"""
from __future__ import annotations

import argparse
import pathlib
import re
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import omf  # noqa: E402
import tcc_batch  # noqa: E402

CASES = pathlib.Path(__file__).resolve().parent / "cases"
IMAGE = ROOT / "build" / "DAVE_unpacked.exe"

# The flag line this catalog establishes (docs/compiler-behaviors.md).
RECOMMENDED = "-ms -1- -f- -N -G"

LIST_KEYS = {"asm-contains", "asm-absent", "contrast", "same-as", "expect-segs"}


class Case:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.name = path.stem
        self.source = path.read_text(encoding="latin1")
        self.meta = parse_header(self.source)
        self.flags = " ".join(self.meta.get("flags", [])).strip()

    def get(self, key):
        return self.meta.get(key)

    def text(self, key):
        v = self.meta.get(key)
        return " ".join(v) if v else None


def parse_header(src: str) -> dict:
    m = re.match(r"\s*/\*(.*?)\*/", src, re.S)
    if not m:
        return {}
    meta: dict = {}
    key = None
    for raw in m.group(1).splitlines():
        line = re.sub(r"^\s*\*?\s?", "", raw).rstrip()
        km = re.match(r"^@([\w-]+):\s*(.*)$", line)
        if km:
            key = km.group(1)
            meta.setdefault(key, [])
            if km.group(2):
                meta[key].append(km.group(2))
        elif not line.strip():
            key = None
        elif key:
            meta[key].append(line.strip())
    for k in list(meta):
        if k in LIST_KEYS:
            meta[k] = [re.sub(r"\s+#.*$", "", v).strip() for v in meta[k] if v.strip()]
    return meta


def segdefs(obj: bytes) -> list:
    """[(name, class, align, length)] in SEGDEF order (omf.py drops the class)."""
    lnames, out = [], []
    align_names = {1: "byte", 2: "word", 3: "para", 4: "page", 5: "dword"}
    for kind, body in omf.OmfReader.records(obj):
        if kind == 0x96:
            at = 0
            while at < len(body):
                n = body[at]
                lnames.append(body[at + 1:at + 1 + n].decode("latin1"))
                at += 1 + n
        elif kind == 0x98:
            acbp = body[0]
            at = 1 + (3 if acbp >> 5 == 0 else 0)
            length = struct.unpack_from("<H", body, at)[0]
            name, cls = lnames[body[at + 2] - 1], lnames[body[at + 3] - 1]
            out.append((name, cls, align_names.get(acbp >> 5, str(acbp >> 5)), length))
    return out


def hex_tokens(lines) -> list:
    toks = []
    for line in lines or []:
        for t in line.split():
            if t == "..":
                toks.append(None)
            elif re.fullmatch(r"[0-9a-fA-F]{2}", t):
                toks.append(int(t, 16))
            else:
                break  # trailing commentary on a hex line
    return toks


def fixup_cover(mod, seg="_TEXT") -> set:
    cov = set()
    for f in mod.fixups_in(seg):
        cov.update(range(f["offset"], f["offset"] + f["width"]))
    return cov


def disasm_text(mod) -> str:
    rows = tcc_batch.disassemble(mod.segment_bytes("_TEXT"), 0, mod.fixups_in("_TEXT")) \
        if "_TEXT" in mod.segments else []
    return "\n".join(t for _, _, t in rows)


def check_primary(case: Case, res, image: bytes | None) -> list:
    """Problems with the primary expectation (empty list = pass)."""
    if res.obj is None:
        return [f"compile failed: {res.log.strip()}"]
    mod = res.module()
    text = mod.segments.get("_TEXT", b"")
    cov = fixup_cover(mod)
    errs = []
    if case.get("original"):
        start, end = (int(x, 0) for x in case.text("original").split()[:2])
        if image is None:
            errs.append("build/DAVE_unpacked.exe missing")
        else:
            target = image[start:end]
            if len(text) < len(target):
                errs.append(f"_TEXT {len(text)} bytes < original range {len(target)}")
            else:
                bad = [i for i in range(len(target)) if text[i] != target[i] and i not in cov]
                if bad:
                    errs.append(f"differs from original at +{bad[0]:#x} (file {start + bad[0]:#x}),"
                                f" {len(bad)} unexplained bytes")
    if case.get("expect-text") is not None:
        exp = hex_tokens(case.get("expect-text"))
        if len(exp) != len(text):
            errs.append(f"_TEXT length {len(text)} != expected {len(exp)}")
        for i, (e, a) in enumerate(zip(exp, text)):
            if e is None:
                if i not in cov:
                    errs.append(f"_TEXT+{i:#x}: expected a fixup-covered byte")
                    break
            elif e != a:
                errs.append(f"_TEXT+{i:#x}: {a:02x} != expected {e:02x}")
                break
    if case.get("expect-data") is not None:
        exp = bytes(t or 0 for t in hex_tokens(case.get("expect-data")))
        got = mod.segments.get("_DATA", b"")
        if exp != got:
            errs.append(f"_DATA {got.hex()} != expected {exp.hex()}")
    if case.get("expect-bss") is not None:
        exp = case.text("expect-bss").split()
        got = [f"{p['name']}@{p['offset']}" for p in mod.publics_in("_BSS")]
        if exp != got:
            errs.append(f"_BSS order {' '.join(got)} != expected {' '.join(exp)}")
    if case.get("expect-segs") is not None:
        got = [" ".join(map(str, s)).replace(res.stem, "MOD") for s in segdefs(res.obj)]
        if got != case.get("expect-segs"):
            errs.append(f"SEGDEFs {got} != expected {case.get('expect-segs')}")
    dis = disasm_text(mod)
    for s in case.get("asm-contains") or []:
        if s not in dis:
            errs.append(f"disassembly lacks {s!r}")
    for s in case.get("asm-absent") or []:
        if s in dis:
            errs.append(f"disassembly unexpectedly has {s!r}")
    return errs


def primary_kind(case: Case) -> bool:
    return any(case.get(k) is not None for k in ("original", "expect-text", "expect-data", "expect-bss"))


def contrast_fails(case: Case, res, image) -> bool:
    """True when the contrast compile does NOT meet the primary byte expectation."""
    if res.obj is None:
        return True
    shadow = Case.__new__(Case)
    shadow.name, shadow.path, shadow.source, shadow.flags = case.name, case.path, case.source, case.flags
    shadow.meta = {k: v for k, v in case.meta.items()
                   if k in ("original", "expect-text", "expect-data", "expect-bss")}
    return bool(check_primary(shadow, res, image))


def load_cases(pattern: str | None = None) -> list:
    cases = [Case(p) for p in sorted(CASES.glob("*.c"))]
    if pattern:
        cases = [c for c in cases if pattern in c.name]
    return cases


def run(cases, show=False) -> list:
    """Compile and check; returns [(case name, [problems])]."""
    jobs = []
    for c in cases:
        base = f"{RECOMMENDED} {c.flags}".strip()
        jobs.append((f"{c.name}|", c.source, base))
        for v in (c.get("contrast") or []) + (c.get("same-as") or []):
            jobs.append((f"{c.name}|{v}", c.source, f"{base} {v}"))
    res = tcc_batch.compile_many(jobs, workdir=ROOT / "build" / "codegen_lab")
    image = IMAGE.read_bytes() if IMAGE.exists() else None
    report = []
    for c in cases:
        prim = res[f"{c.name}|"]
        errs = check_primary(c, prim, image)
        if not primary_kind(c) and not c.get("asm-contains"):
            errs.append("case states no checkable expectation")
        for v in c.get("contrast") or []:
            if not contrast_fails(c, res[f"{c.name}|{v}"], image):
                errs.append(f"contrast {v!r} still meets the expectation (flag not shown observable)")
        for v in c.get("same-as") or []:
            r = res[f"{c.name}|{v}"]
            if r.obj is None or prim.obj is None:
                errs.append(f"same-as {v!r}: compile failed")
                continue
            a, b = prim.module(), r.module()
            for seg in ("_TEXT", "_DATA"):
                if a.segments.get(seg, b"") != b.segments.get(seg, b""):
                    errs.append(f"same-as {v!r}: {seg} differs")
        report.append((c.name, errs))
        if show:
            print(f"===== {c.name}  [{RECOMMENDED} {c.flags}]")
            if prim.obj is not None:
                mod = prim.module()
                pubs = {p["offset"]: p["name"] for p in mod.publics_in("_TEXT")}
                for off, hx, t in tcc_batch.disassemble(mod.segments.get("_TEXT", b""), 0,
                                                        mod.fixups_in("_TEXT")):
                    if off in pubs:
                        print(f"{pubs[off]}:")
                    print(f"  {off:04x}  {hx:14s} {t}")
                for seg, data in mod.segments.items():
                    if seg != "_TEXT":
                        print(f"  {seg}: {data.hex(' ')}")
                print("  BSS:", " ".join(f"{p['name']}@{p['offset']}" for p in mod.publics_in("_BSS")))
                for s in segdefs(prim.obj):
                    print("  SEGDEF", *s)
            else:
                print(prim.log)
    return report, res


def hex_block(data: bytes, cover: set) -> list:
    toks = [".." if i in cover else f"{b:02x}" for i, b in enumerate(data)]
    return [" ".join(toks[i:i + 16]) for i in range(0, len(toks), 16)] or [""]


def bless(case: Case, res) -> None:
    mod = res.module()
    src = case.source
    close = src.index("*/")
    line_start = src.rfind("\n", 0, close) + 1
    head, tail = src[:line_start], src[line_start:]
    cov = fixup_cover(mod)

    def replace(key, lines):
        nonlocal head
        block = "\n".join(f" * @{key}:" if i == 0 else f" *   {l}" for i, l in enumerate([""] + lines))
        block = block.replace(f" * @{key}:\n *   ", f" * @{key}:\n *   ", 1)
        pat = re.compile(rf"^ \* @{key}:.*?(?=^ \* @|^ \*\s*$|\Z)", re.S | re.M)
        if pat.search(head):
            head = pat.sub(block + "\n", head, count=1)
        else:
            head = head.rstrip() + "\n" + block + "\n "

    if case.get("expect-text") is not None:
        replace("expect-text", hex_block(mod.segments.get("_TEXT", b""), cov))
    if case.get("expect-data") is not None:
        replace("expect-data", hex_block(mod.segments.get("_DATA", b""), set()))
    if case.get("expect-bss") is not None:
        replace("expect-bss", [" ".join(f"{p['name']}@{p['offset']}" for p in mod.publics_in("_BSS"))])
    case.path.write_text(head + tail, encoding="latin1", newline="\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", dest="pattern")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--bless", action="store_true")
    args = ap.parse_args()
    if not tcc_batch.toolchain_available():
        raise SystemExit("toolchain/DOSBox-X not available (run tools/bootstrap.py)")
    cases = load_cases(args.pattern)
    report, res = run(cases, show=args.show)
    if args.bless:
        for c in cases:
            bless(c, res[f"{c.name}|"])
        cases = load_cases(args.pattern)
        report, res = run(cases)
    bad = 0
    for name, errs in report:
        print(f"{'ok  ' if not errs else 'FAIL'} {name}")
        for e in errs:
            print(f"       {e}")
        bad += bool(errs)
    print(f"{len(report) - bad}/{len(report)} cases pass")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
