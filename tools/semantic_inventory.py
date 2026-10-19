"""Generate the semantic inventory (PORT_ROADMAP M2.1).

    python tools/semantic_inventory.py            # write docs/semantic-inventory.{json,md}
    python tools/semantic_inventory.py --check    # regenerate and compare with the committed files

One entry per C function, assembly procedure, global variable / DGROUP data
object, far-data segment and resource format, plus one per subsystem
(a grouping of the others). Every entry has

  identity   name, historical address (cs / DS / file / far paragraph),
             unit, size, type;
  purpose    one line;
  status     understood | partial | behaviour_understood_representation_unclear
             | representation_understood_behaviour_unclear | unresolved;
  evidence   where it is established;
  relations  callers / callees, readers / writers, ...;
  subsystem  tag; for data also a `role` (game state, presentation,
             platform, resource buffer, layout artifact, ...).

Two kinds of input, kept apart on purpose:

  * MECHANICAL (this file): identities and relations are parsed from the
    recovered sources -- src/DAVE.H, src/*.C, src/asm/*.asm -- plus
    layout/bss-map.json for the _BSS addresses. Calls, reads and writes are
    found by tokenising every function body / procedure; nothing in the
    relations is typed by hand. Cross-checks against independent evidence
    (the binary call graph docs/function-census-callgraph-v2.json, the
    DS-reference sweep docs/data-layout.json, the source headers' own
    address claims) are recorded in the JSON (`checks`) and asserted by
    tests/test_semantic_inventory.py.
  * CURATED (tools/semantic_annotations.py): purpose, status, evidence,
    subsystem, role. Each status there is a claim that must be backed by its
    evidence; `understood` requires both the behaviour and the representation
    to be explained.

The address convention is the project's: cs = CS offset (file offset -
0x200), file = offset in build/DAVE_unpacked.exe, DS = DGROUP offset.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import semantic_annotations as ann  # noqa: E402

SRC = ROOT / "src"
UNITS = ["DAVE.C", "CONFIG.C", "HARDWARE.C"]
ASM_MODULES = ["lowlevel.asm", "tiles.asm"]
OUT_JSON = ROOT / "docs" / "semantic-inventory.json"
OUT_MD = ROOT / "docs" / "semantic-inventory.md"
FILE_BASE = 0x200                 # MZ header: file = cs + 0x200
STATUSES = ("understood", "partial", "behaviour_understood_representation_unclear",
            "representation_understood_behaviour_unclear", "unresolved")
DRAFT = False                     # --draft: placeholders for missing annotations
ROLES = ("game_state", "game_constant", "presentation_state", "presentation_constant",
         "platform_state", "config", "resource_buffer", "layout_artifact", "runtime")


def h(n: int | None, width: int = 4) -> str | None:
    return None if n is None else f"0x{n:0{width}X}"


# =========================================================================== C

def strip_comments(text: str) -> str:
    """Comments and string/char literals blanked out (same length, newlines kept)."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j]))
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            out.append(c + " " * (j - i - 1) + c)
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


TOKEN = re.compile(r"[A-Za-z_]\w*|0[xX][0-9a-fA-F]+|\d+|<<=|>>=|->|\+\+|--|&&|\|\||[-+*/%&|^<>=!]=|<<|>>|\S")
ASSIGN = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}
# callee -> argument positions (1-based) whose pointee the callee WRITES
WRITES_ARG = {"movmem": [2], "setmem": [1], "read_file_far": [2], "RLEExpand": [2],
              "SaveUnderCGA": [4], "SaveUnderEGA": [4], "SaveUnderVGA": [4],
              "save_background": [4], "input_initials": [1], "read_joystick_axes": [2, 3],
              "ultoa": [2], "itoa": [2], "ltoa": [2]}


def tokens(code: str):
    return [m.group(0) for m in TOKEN.finditer(code)]


def ctype_size(t: str, structs: dict) -> int:
    t = t.strip()
    if "(" in t:                                  # function pointer
        return 4 if "far" in t else 2
    if "*" in t:
        return 4 if ("far" in t or "huge" in t) else 2
    base = re.sub(r"\b(unsigned|signed|register|extern|static)\b", "", t).strip()
    if base.startswith("struct "):
        return structs[base.split()[1]]
    if base == "":
        base = "int"                              # bare `unsigned`
    return {"char": 1, "int": 2, "long": 4, "void": 0}[base]


def parse_structs(text: str) -> dict:
    """struct name -> {size, fields[(name, type, offset, size)]} from DAVE.H."""
    code = strip_comments(text)
    structs, sizes = {}, {}
    for m in re.finditer(r"struct\s+(\w+)\s*\{(.*?)\};", code, re.S):
        name, body = m.group(1), m.group(2)
        off, fields = 0, []
        for decl in body.split(";"):
            decl = decl.strip()
            if not decl:
                continue
            dm = re.match(r"(.*?)(\**)\s*(\w+)\s*((?:\[[^\]]*\])*)$", decl)
            ftype, stars, fname, dims = dm.group(1).strip(), dm.group(2), dm.group(3), dm.group(4)
            size = ctype_size(ftype + stars, sizes)
            for d in re.findall(r"\[([^\]]*)\]", dims):
                size *= int(eval(d, {}))          # dims are integer constant expressions
            fields.append({"name": fname, "type": (ftype + " " + stars).strip() + dims,
                           "offset": off, "size": size})
            off += size
        sizes[name] = off
        structs[name] = {"size": off, "fields": fields}
    return structs


def parse_header(text: str):
    """DAVE.H: storage #defines, extern declarations (with section), prototypes."""
    defines = dict(re.findall(r"^#define\s+(\w+)\s+(\w+)", text, re.M))
    externs, section = {}, None
    for line in text.splitlines():
        sm = re.match(r"/\* ---- (.*?)(?: \(.*)?\s*\*/", line.strip())
        if sm:
            section = sm.group(1)
        m = re.match(r"extern\s+(.+?);\s*(?:/\*\s*(.*?)\s*\*/)?$", line.strip())
        if m:
            decl, comment = m.group(1), m.group(2) or ""
            fp = re.search(r"\(far \*(\w+)\)", decl)
            name = fp.group(1) if fp else re.search(r"(\w+)\s*(?:\[[^\]]*\])*\s*$", decl).group(1)
            externs[name] = {"decl": decl, "comment": comment, "section": section}
    protos = {}
    for m in re.finditer(r"^([A-Za-z].*?\b(\w+)\s*\(([^;{]*)\));", strip_comments(text), re.M):
        if not m.group(1).startswith(("extern", "struct ") ) or "(" in m.group(1).split()[1]:
            protos[m.group(2)] = re.sub(r"\s+", " ", m.group(1))
    return defines, externs, protos


def parse_decl(stmt: str, structs: dict):
    """One top-level data declaration -> (name, type, size, has_init)."""
    s = re.sub(r"\s+", " ", stmt.strip())
    head = s.split("=", 1)[0].strip()
    fp = re.match(r"(.*)\(far \*(\w+)\)\(\)$", head)
    if fp:
        return fp.group(2), "void interrupt (far *)()", 4, "=" in s
    m = re.match(r"(.*?)(\**)\s*(\w+)\s*((?:\[[^\]]*\])*)$", head)
    base, stars, name, dims = m.group(1).strip(), m.group(2), m.group(3), m.group(4)
    size = ctype_size(base + stars, {k: v["size"] for k, v in structs.items()})
    ds = [d for d in re.findall(r"\[([^\]]*)\]", dims)]
    for d in ds:
        size *= int(d, 0)
    return name, (base + (" " + stars if stars else "")).strip() + dims, size, "=" in s


def parse_unit(path: pathlib.Path, structs: dict) -> dict:
    text = path.read_text(encoding="latin-1")
    code = strip_comments(text)
    lines = text.splitlines(keepends=True)
    starts = [0]
    for ln in lines:
        starts.append(starts[-1] + len(ln))
    at = int(re.search(r"@at (0x[0-9a-fA-F]+)", text).group(1), 16)
    data_base = int(re.search(r"@seg _DATA (0x[0-9a-fA-F]+)", text).group(1), 16)
    bss_base = int(re.search(r"@seg _BSS (0x[0-9a-fA-F]+)", text).group(1), 16)

    # function definitions: a line at column 0 ending in ')' followed by '{'
    funcs = []
    code_lines = code.splitlines(keepends=True)
    i = 0
    while i < len(code_lines) - 1:
        ln = code_lines[i]
        if (ln[:1].isalpha() and ln.rstrip().endswith(")") and code_lines[i + 1].strip() == "{"
                and not ln.startswith("#")):
            name = re.search(r"(\w+)\s*\(", ln.replace("(far *", "")).group(1)
            body_start = starts[i + 1]
            depth, j = 0, body_start
            while True:
                if code[j] == "{":
                    depth += 1
                elif code[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            funcs.append({"name": name, "signature": ln.strip(), "line": i + 1,
                          "def_pos": starts[i], "body": code[body_start:j + 1], "end_pos": j + 1})
            i = code[:j].count("\n") + 1
        else:
            i += 1
    # header comment of each function: the comments between the previous item and it
    prev_end = 0
    for f in funcs:
        seg = text[prev_end:f["def_pos"]]
        f["header"] = "\n".join(re.findall(r"/\*(.*?)\*/", seg, re.S))
        prev_end = f["end_pos"]
    # function-like macros of the unit (pick_up_items' PICK), expanded in bodies
    macros = {}
    for m in re.finditer(r"^#define\s+(\w+)\(([^)]*)\)((?:.*\\\n)*.*)$", code, re.M):
        params = [p.strip() for p in m.group(2).split(",")]
        macros[m.group(1)] = (params, m.group(3).replace("\\\n", "\n"))
    for f in funcs:
        f["body"] = expand_macros(f["body"], macros)
        # inline `asm` statements reference registers, not C objects
        f["body"] = re.sub(r"^\s*asm\b.*$", "", f["body"], flags=re.M)

    # top-level data declarations (before the first function)
    decl_region = code[:funcs[0]["def_pos"]] if funcs else code
    variables, pos, depth, stmt_start = [], 0, 0, 0
    for k, c in enumerate(decl_region):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == ";" and depth == 0:
            stmt = decl_region[stmt_start:k]
            stmt_clean = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("#"))
            line_no = decl_region[:k].count("\n")
            stmt_start = k + 1
            if not stmt_clean.strip() or re.match(r"\s*(struct\s+\w+\s*\{|typedef)", stmt_clean):
                continue
            name, ctype, size, init = parse_decl(stmt_clean, structs)
            cm = re.search(r";\s*/\*\s*(.*?)\s*\*/", lines[line_no])
            variables.append({"name": name, "type": ctype, "size": size, "init": init,
                              "line": line_no + 1, "comment": cm.group(1) if cm else ""})
    # _DATA addresses: initialised globals in definition order, unpadded
    ds = data_base
    for v in variables:
        if v["init"]:
            v["ds"] = ds
            ds += v["size"]
    m = re.search(r"initialised data ends at DS (0x[0-9a-fA-F]+)", text)
    data_end_claim = int(m.group(1), 16) if m else None
    return {"unit": path.name, "path": path, "text": text, "at": at, "data_base": data_base,
            "bss_base": bss_base, "data_end": ds, "data_end_claim": data_end_claim,
            "functions": funcs, "variables": variables}


def expand_macros(body: str, macros: dict) -> str:
    for name, (params, repl) in macros.items():
        while True:
            m = re.search(r"\b%s\s*\(" % name, body)
            if not m:
                break
            depth, j, args, start = 0, m.end() - 1, [], m.end()
            while True:
                c = body[j]
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        args.append(body[start:j])
                        break
                elif c == "," and depth == 1:
                    args.append(body[start:j])
                    start = j + 1
                j += 1
            text = repl
            for p, a in zip(params, args):
                text = re.sub(r"\b%s\b" % re.escape(p), a.strip(), text)
            body = body[:m.start()] + text + body[j + 1:]
    return body


def header_address(f: dict, unit_text: str):
    # group comments list several functions: "<name>  cs [0x..,0x..)  N bytes"
    m = re.search(r"\b%s\s+cs \[0x([0-9a-fA-F]+),\s*0x([0-9a-fA-F]+)\)" % re.escape(f["name"]), unit_text)
    if m:
        return int(m.group(1), 16), int(m.group(2), 16)
    ms = re.findall(r"cs \[0x([0-9a-fA-F]+),\s*0x([0-9a-fA-F]+)\)", f["header"])
    if ms:      # the last claim is the function's own (a unit header may precede it)
        return int(ms[-1][0], 16), int(ms[-1][1], 16)
    return None, None


def lvalue_end(toks, k):
    """Index after the postfix expression starting with the identifier at k."""
    j = k + 1
    while j < len(toks):
        if toks[j] == "[":
            depth = 0
            while j < len(toks):
                depth += {"[": 1, "]": -1}.get(toks[j], 0)
                j += 1
                if depth == 0:
                    break
        elif toks[j] in (".", "->") and j + 1 < len(toks):
            j += 2
        else:
            break
    return j


def analyse_body(body: str, functions: set, globals_: dict):
    """Calls, library calls, reads / writes / address-taken of globals."""
    toks = tokens(body)
    calls, libcalls = [], []
    reads, writes, through, addr, whole = set(), set(), set(), set(), set()
    keywords = {"if", "for", "while", "switch", "return", "sizeof", "do", "else", "case"}

    # call arguments: identify the callee and each argument's token span
    def call_args(k):
        """k = index of '(' after a callee; returns list of (start, end) token spans."""
        spans, depth, start = [], 0, k + 1
        for j in range(k, len(toks)):
            if toks[j] in "([":
                depth += 1
            elif toks[j] in ")]":
                depth -= 1
                if depth == 0:
                    spans.append((start, j))
                    return spans
            elif toks[j] == "," and depth == 1:
                spans.append((start, j))
                start = j + 1
        return spans

    for k, t in enumerate(toks):
        if re.match(r"[A-Za-z_]\w*$", t) and k + 1 < len(toks) and toks[k + 1] == "(" \
                and t not in keywords and t not in globals_:
            if t in functions:
                calls.append(t)
            elif not (k > 0 and toks[k - 1] in ("int", "char", "void", "long")):
                libcalls.append(t)
            for pos in WRITES_ARG.get(t, []):
                spans = call_args(k + 1)
                if pos <= len(spans):
                    a, b = spans[pos - 1]
                    for x in toks[a:b]:
                        if x in globals_:
                            (through if globals_[x]["pointer"] else writes).add(x)
                            if not globals_[x]["pointer"]:
                                whole.add(x)
    freads, fwrites = set(), set()
    for k, t in enumerate(toks):
        if t not in globals_:
            continue
        g = globals_[t]
        j = lvalue_end(toks, k)
        nxt = toks[j] if j < len(toks) else ""
        prv = toks[k - 1] if k else ""
        subscripted = j > k + 1
        member = None
        for q in range(k + 1, j - 1):
            if toks[q] in (".", "->"):
                member = f"{t}.{toks[q + 1]}"
                break
        if prv == "&" and (k < 2 or toks[k - 2] in "(,=" or toks[k - 2] in ASSIGN or toks[k - 2] == "return"):
            if g["pointer"] and subscripted:
                reads.add(t)                  # &p[i]: the pointer is read, the pointee referenced
            else:
                addr.add(t)
            continue
        if nxt in ASSIGN or nxt in ("++", "--") or prv in ("++", "--"):
            if g["pointer"] and subscripted:
                through.add(t)
                reads.add(t)
            else:
                writes.add(t)
                if member:
                    fwrites.add(member)
                else:
                    whole.add(t)
                if nxt != "=":
                    reads.add(t)
                    if member:
                        freads.add(member)
            continue
        reads.add(t)
        if member:
            freads.add(member)
    # writes through a dereferenced pointer expression: *( ... g ... ) = ...
    for k, t in enumerate(toks):
        if t == "*" and k + 1 < len(toks) and toks[k + 1] == "(" and (k == 0 or toks[k - 1] in (";", "{", "}", ")")):
            depth, j = 0, k + 1
            while j < len(toks):
                depth += {"(": 1, ")": -1}.get(toks[j], 0)
                j += 1
                if depth == 0:
                    break
            if j < len(toks) and toks[j] in ASSIGN:
                for x in toks[k + 1:j]:
                    if x in globals_ and globals_[x]["pointer"]:
                        through.add(x)
    return {"calls": calls, "tail_jumps": [], "library_calls": libcalls, "reads": reads, "writes": writes,
            "writes_through": through, "address_taken": addr, "field_reads": freads, "field_writes": fwrites,
            "whole_writes": whole}


# ========================================================================= asm

ASM_INSN = re.compile(r"^\s*(?:(?P<label>[@\w]+):)?\s*(?P<op>[a-z]+)?\s*(?P<args>[^;]*)(?:;(?P<comment>.*))?$", re.I)
WRITE_OPS = {"mov", "add", "sub", "adc", "sbb", "inc", "dec", "and", "or", "xor", "not", "neg",
             "shl", "shr", "sal", "sar", "rol", "ror", "rcl", "rcr", "pop", "xchg"}
DATA_DIRECTIVE = re.compile(r"^(?:(?P<name>[A-Za-z_@]\w*)\s+)?(?P<kind>db|dw|dd|label)\b\s*(?P<rest>.*)$", re.I)


def asm_item_size(kind: str, rest: str) -> int:
    rest = rest.split(";", 1)[0].strip()
    unit = {"db": 1, "dw": 2, "dd": 4}[kind.lower()]
    total = 0
    for part in re.findall(r"'[^']*'|[^,]+", rest):
        part = part.strip()
        if part.startswith("'"):
            total += len(part) - 2
        else:
            m = re.match(r"(\d+)\s+dup\s*\(", part, re.I)
            total += unit * (int(m.group(1)) if m else 1)
    return total


def parse_asm(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="latin-1")
    lines = text.splitlines()
    at = int(re.search(r"@at (0x[0-9a-fA-F]+)", text).group(1), 16)
    data_base = int(re.search(r"@seg _DATA (0x[0-9a-fA-F]+)", text).group(1), 16)
    aliases = {}           # name -> DS address of a C-owned global (extrn _D_XXXX + equ)
    for m in re.finditer(r"^(\w+)\s+equ\s+_D_([0-9A-F]{4})", text, re.M):
        aliases[m.group(1)] = int(m.group(2), 16)
    for m in re.finditer(r"extrn\s+_D_([0-9A-F]{4}):\w+\s*;\s*(.*)", text):
        aliases.setdefault("_D_" + m.group(1), int(m.group(1), 16))
    publics = set()
    for m in re.finditer(r"^\s*public\s+(.*)$", text, re.M):
        publics |= {p.strip() for p in m.group(1).split(",")}
    section, procs, data, cur = None, [], [], None
    pending_ds, in_rept = data_base, False
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.upper().startswith(".DATA"):
            section = "data"
            continue
        if s.upper().startswith(".CODE"):
            section = "code"
            continue
        pm = re.match(r"^(\w+)\s+proc\b", s, re.I)
        if pm:
            name = pm.group(1)
            # the closest preceding comment line(s) describe the procedure
            k, doc = n - 2, []
            while k >= 0 and (lines[k].strip().startswith(";") or lines[k].strip().lower().startswith("public")):
                if lines[k].strip().startswith(";"):
                    doc.insert(0, lines[k].strip().lstrip("; "))
                k -= 1
            inline = raw.split(";", 1)[1].strip() if ";" in raw else ""
            cm = re.findall(r"F_([0-9A-F]{4})|file ([0-9a-f]{4})", " ".join(doc) + " " + inline)
            fid = None
            if cm:
                a, b = cm[0] if inline == "" else cm[-1]
                fid = int(a or b, 16)
            cur = {"name": name, "line": n, "file": fid, "doc": " ".join(doc) or inline,
                   "inline": inline, "far": " far" in raw.lower(), "body": [],
                   "public": name in publics}
            procs.append(cur)
            continue
        if cur and re.match(r"^%s\s+endp\b" % re.escape(cur["name"]), s, re.I):
            cur["end_line"] = n
            cur = None
            continue
        if cur is not None:
            cur["body"].append(raw)
            continue
        if re.match(r"^rept\b", s, re.I):
            in_rept = True
            continue
        if re.match(r"^endm\b", s, re.I):
            in_rept = False
            continue
        if in_rept:          # the body of a rept table belongs to the label before it
            continue
        sm = re.match(r"^(\w+)\s+VIDstruct\s+<>", s)          # struct instance (VideoID)
        dm = DATA_DIRECTIVE.match(s)
        if (dm or sm) and section in ("data", "code") and not s.lower().startswith(("public", "extrn")):
            if sm:
                name, kind, rest, size = sm.group(1), "struct", "", 4
            else:
                name, kind, rest = dm.group("name"), dm.group("kind").lower(), dm.group("rest")
                size = asm_item_size(kind, rest) if kind != "label" else None
            addr_m = re.search(r";\s*(ds|cs)\s+([0-9a-f]{4})", raw)
            comment = raw.split(";", 1)[1].strip() if ";" in raw else ""
            comment = re.sub(r"^(ds|cs)\s+[0-9a-f]{4}\s*", "", comment)
            item = {"name": name, "kind": kind, "line": n, "section": section, "size": size,
                    "comment": comment, "public": name in publics if name else False}
            prev = data[-1] if data else None
            contiguous = (prev is not None and prev["section"] == section
                          and all(not lines[k].strip() or lines[k].strip().startswith(";")
                                  for k in range(prev["last_line"], n - 1)))
            if section == "data":
                if addr_m:
                    pending_ds = int(addr_m.group(2), 16)
                item["ds"] = pending_ds
                if size:
                    pending_ds += size
            else:
                if addr_m:
                    item["cs"] = int(addr_m.group(2), 16)
                elif contiguous and prev.get("cs") is not None and prev.get("size") is not None:
                    item["cs"] = prev["cs"] + prev["size"]      # follows the previous item directly
                else:
                    item["cs"] = None
            # an unnamed directive continues the previous item (BarPattern, the
            # TestSequence routine words, ...) unless it carries its own address
            if name is None and contiguous and not addr_m:
                prev["size"] = (prev["size"] or 0) + (size or 0)
                prev["last_line"] = n
                continue
            item["last_line"] = n
            data.append(item)
    tm = re.search(r"_TEXT\s+cs \[(0x[0-9a-f]+),\s*(0x[0-9a-f]+)\)", text)
    text_end = int(tm.group(2), 16)
    m = re.search(r"_DATA\s+ds \[(0x[0-9a-f]+),\s*(0x[0-9a-f]+)\)", text)
    data_end = int(m.group(2), 16) if m else None
    # labels (`label word`) followed by rept blocks: size up to the next item
    ds_items = [d for d in data if d["section"] == "data"]
    for a, b in zip(ds_items, ds_items[1:] + [None]):
        if a["kind"] == "label" or a.get("size") is None:
            a["size"] = (b["ds"] if b else data_end) - a["ds"]
    return {"module": path.name, "text": text, "at": at, "text_end": text_end,
            "data_base": data_base, "data_end": data_end,
            "aliases": aliases, "procs": procs, "data": data, "publics": publics}


def asm_refs(proc: dict, names: set, proc_names: set):
    """Mechanical reads / writes / calls of a procedure body."""
    calls, jumps, reads, writes, addr = [], [], set(), set(), set()
    for raw in proc["body"]:
        m = ASM_INSN.match(raw)
        if not m or not m.group("op"):
            continue
        op, args = m.group("op").lower(), (m.group("args") or "").strip()
        if op in ("rept", "endm", "local", "include", "assume", "equ", "macro"):
            continue
        ops = [a.strip() for a in re.split(r",(?![^\[]*\])", args)] if args else []
        if op == "call":
            tgt = re.sub(r"^(far|near)\s+ptr\s+", "", args).strip()
            tgt = tgt.split()[-1] if tgt else tgt
            if tgt in proc_names:
                calls.append(tgt)
            elif tgt in names:
                reads.add(tgt)                    # indirect call through a variable
            continue
        if op.startswith("j") and ops:
            tgt = ops[0].split()[-1]
            if tgt in proc_names:
                jumps.append(tgt)
            continue
        for i, a in enumerate(ops):
            for ident in re.findall(r"[A-Za-z_@][\w@]*", a):
                if ident not in names:
                    continue
                if re.search(r"\boffset\s+%s\b" % re.escape(ident), a):
                    addr.add(ident)
                elif i == 0 and op in WRITE_OPS and len(ops) >= 1:
                    writes.add(ident)
                    if op not in ("mov", "pop"):
                        reads.add(ident)
                    if op == "xchg":
                        reads.add(ident)
                else:
                    reads.add(ident)
                    if op == "xchg":
                        writes.add(ident)
    return {"calls": calls, "tail_jumps": jumps, "reads": reads, "writes": writes, "address_taken": addr}


# ======================================================================= build

def load_json(rel: str):
    return json.loads((ROOT / rel).read_text())


def build() -> dict:
    header_text = (SRC / "DAVE.H").read_text(encoding="latin-1")
    structs = parse_structs(header_text)
    defines, externs, protos = parse_header(header_text)
    units = [parse_unit(SRC / u, structs) for u in UNITS]
    mods = [parse_asm(SRC / "asm" / m) for m in ASM_MODULES]
    bss = load_json("layout/bss-map.json")
    callgraph = load_json("docs/function-census-callgraph-v2.json")
    layout = load_json("docs/data-layout.json")

    checks = {}
    # ------------------------------------------------------------ data objects
    data = {}            # name -> entry
    bss_by_name = {}
    for u in bss["units"]:
        for e in u["entries"]:
            if e["kind"] == "variable":
                bss_by_name[e["name"]] = (u["unit"], e)
    for u in units:
        for v in u["variables"]:
            ent = {"name": v["name"], "kind": "global", "unit": u["unit"], "type": v["type"],
                   "size": v["size"], "segment": "_DATA" if v["init"] else "_BSS",
                   "source": f"src/{u['unit']}:{v['line']}", "source_comment": v["comment"]}
            if v["init"]:
                ent["ds"] = v["ds"]
            else:
                bu, be = bss_by_name[v["name"]]
                ent["ds"] = be["ds"]
                ent["storage_name"] = be["storage"]
                if be["size"] != v["size"]:
                    raise SystemExit(f"{v['name']}: size {v['size']} vs bss-map {be['size']}")
            data[v["name"]] = ent
        checks[f"{u['unit']}_data_end"] = {"computed": h(u["data_end"]), "claimed": h(u["data_end_claim"]),
                                          "ok": u["data_end"] == u["data_end_claim"]}
    # padding in _BSS
    for u in bss["units"]:
        for e in u["entries"]:
            if e["kind"] != "variable":
                nm = f"pad_{e['ds']:04x}"
                data[nm] = {"name": nm, "kind": "global", "unit": u["unit"] + ".C", "type": "padding",
                            "size": e["size"], "segment": "_BSS", "ds": e["ds"],
                            "source": "layout/bss-map.json", "source_comment": e.get("comment", "")}
    # asm data (DGROUP) and CS-resident variables
    for m in mods:
        for d in m["data"]:
            if not d["name"]:
                nm = f"{m['module'].split('.')[0]}_anon_{(d.get('ds') or d.get('cs') or 0):04x}"
            else:
                nm = d["name"].lstrip("_") if d["public"] else d["name"]
            ent = {"name": nm, "kind": "global", "unit": "asm/" + m["module"],
                   "type": {"db": "byte", "dw": "word", "dd": "dword", "label": "table",
                            "struct": "VIDstruct"}[d["kind"]],
                   "size": d["size"], "source": f"src/asm/{m['module']}:{d['line']}",
                   "source_comment": d["comment"], "asm_label": d["name"]}
            if d["section"] == "data":
                ent["segment"], ent["ds"] = "_DATA", d["ds"]
            else:
                ent["segment"], ent["cs"] = "_TEXT", d.get("cs")
            data[nm] = ent
    # vidtabs.inc tables (one copy at the start of each module's _TEXT)
    for m in mods:
        mod = m["module"].split(".")[0]
        base = m["at"]
        for k, (tab, size) in enumerate((("CgaRowOfs", 400), ("EgaRowOfs", 400), ("VgaRowOfs", 400))):
            nm = f"{mod}.{tab}"
            data[nm] = {"name": nm, "kind": "global", "unit": "asm/vidtabs.inc (in " + m["module"] + ")",
                        "type": "word[200]", "size": size, "segment": "_TEXT", "cs": base + 400 * k,
                        "source": "src/asm/vidtabs.inc", "source_comment": "", "asm_label": tab}
    # objects declared in DAVE.H that no C unit or asm module defines
    for name, info in ann.EXTRA_DATA.items():
        ent = {"name": name, "kind": info.get("kind", "global"), "unit": info["unit"], "type": info["type"],
               "size": info["size"], "segment": info["segment"], "source": info["source"],
               "source_comment": info.get("comment", "")}
        for key in ("ds", "para", "file"):
            if key in info:
                ent[key] = info[key]
        data[name] = ent
    # every DAVE.H extern has an entry
    missing = [n for n in externs if n not in data]
    checks["externs_without_entry"] = missing

    # address -> data name (for asm aliases and the data-layout coverage check)
    def owner_of(ds: int):
        for nm, e in data.items():
            if "ds" in e and e["ds"] is not None and e.get("size") and e["ds"] <= ds < e["ds"] + e["size"]:
                if e["type"] != "padding":
                    return nm, ds - e["ds"]
        return None, None

    # ------------------------------------------------------------- functions
    c_funcs = {f["name"]: (u, f) for u in units for f in u["functions"]}
    asm_procs = {}
    for m in mods:
        for p in m["procs"]:
            pub = p["name"].lstrip("_") if p["public"] else p["name"]
            asm_procs[pub] = (m, p)
    fnames = set(c_funcs) | set(asm_procs)
    # globals visible to C code: the C definitions + the asm publics + EXTRA_DATA
    c_globals = {}
    for nm, e in data.items():
        if e["unit"].endswith(".C") or (e.get("asm_label") or "").startswith("_") or nm in ann.EXTRA_DATA:
            if e["type"] == "padding":
                continue
            ptr = "*" in e["type"] and "[" not in e["type"].split("*")[0]
            c_globals[nm] = {"pointer": ptr and "(" not in e["type"]}

    funcs = {}
    for name, (u, f) in c_funcs.items():
        cs0, cs1 = header_address(f, u["text"])
        rel = analyse_body(f["body"], fnames, c_globals)
        for lc in rel["library_calls"]:          # runtime data touched by library routines
            rel["reads"] |= set(ann.LIBRARY_DATA.get(lc, {}).get("reads", ()))
            rel["writes"] |= set(ann.LIBRARY_DATA.get(lc, {}).get("writes", ()))
        funcs[name] = {"name": name, "kind": "c_function", "unit": u["unit"],
                       "cs": cs0, "cs_end": cs1, "signature": f["signature"],
                       "source": f"src/{u['unit']}:{f['line']}", "rel": rel}
    # functions in unit order give the cs extents of those without header claims
    for u in units:
        for a, b in zip(u["functions"], u["functions"][1:]):
            if funcs[b["name"]]["cs"] is None and funcs[a["name"]]["cs_end"] is not None:
                funcs[b["name"]]["cs"] = funcs[a["name"]]["cs_end"]
    asm_names = set(asm_procs)
    for m in mods:
        for d in m["data"]:
            if d["name"]:
                asm_names.add(d["name"])
        asm_names |= set(m["aliases"])
        asm_names |= {"CgaRowOfs", "EgaRowOfs", "VgaRowOfs"}
    raw_to_pub = {p["name"]: pub for pub, (m, p) in asm_procs.items()}
    for pub, (m, p) in asm_procs.items():
        names = asm_names | set(raw_to_pub)
        r = asm_refs(p, names, set(raw_to_pub))
        fid = p["file"] if p["file"] is not None else ann.ASM_ADDRESSES.get(pub)
        mod = m["module"].split(".")[0]

        def resolve(x):
            if x in raw_to_pub:
                return raw_to_pub[x]
            if x in m["aliases"]:
                o, off = owner_of(m["aliases"][x])
                return o + (f"+{off}" if off else "") if o else f"DS:{m['aliases'][x]:04X}"
            if x in ("CgaRowOfs", "EgaRowOfs", "VgaRowOfs"):
                return f"{mod}.{x}"
            return x.lstrip("_") if x.startswith("_") else x
        rel = {"calls": [resolve(x) for x in r["calls"]], "tail_jumps": [resolve(x) for x in r["tail_jumps"]],
               "reads": {resolve(x) for x in r["reads"]} - set(asm_procs),
               "writes": {resolve(x) for x in r["writes"]} - set(asm_procs),
               "address_taken": {resolve(x) for x in r["address_taken"]},
               "library_calls": [], "writes_through": set()}
        # procedures reached through a dispatch table (VideoID's TestSequence)
        funcs[pub] = {"name": pub, "kind": "asm_procedure", "unit": "asm/" + m["module"],
                      "cs": (fid - FILE_BASE) if fid is not None else None, "cs_end": None,
                      "signature": p["doc"].split(" -- ")[0] if " -- " in p["doc"] else "",
                      "source": f"src/asm/{m['module']}:{p['line']}", "rel": rel, "public": p["public"],
                      "far": p["far"], "doc": p["doc"]}
    for table, (proc, targets) in ann.DISPATCH_TABLES.items():
        funcs[proc]["rel"]["calls"] += targets
        funcs[proc]["rel"]["reads"].add(table)
    # sizes for asm procs from the census where it knows the procedure
    census = {f["file_start"]: f for f in load_json("docs/function-census.json")["functions"]}
    for name, f in funcs.items():
        if f["cs"] is not None and f["cs_end"] is None:
            c = census.get(f["cs"] + FILE_BASE)
            if c:
                f["cs_end"] = c["cs_end"]
    for f in funcs.values():
        f["size_basis"] = "census" if f["cs_end"] is not None else None
    for m in mods:                  # the rest: up to the next procedure (or the module end)
        mine = sorted((f for f in funcs.values() if f["unit"] == "asm/" + m["module"] and f["cs"] is not None),
                      key=lambda f: f["cs"])
        for a, b in zip(mine, mine[1:] + [None]):
            if a["cs_end"] is None:
                a["cs_end"] = b["cs"] if b else m["text_end"]
                a["size_basis"] = "extent to the next procedure (includes any CS-resident data between)"
    # the C units' headers vs the census
    mismatch = []
    for name, f in funcs.items():
        if f["kind"] == "c_function":
            c = census.get(f["cs"] + FILE_BASE)
            if not c or c["cs_end"] != f["cs_end"]:
                mismatch.append(name)
    checks["c_header_address_vs_census"] = {"mismatches": mismatch, "ok": not mismatch}

    # ------------------------------------------------------- inverse relations
    callers = {n: set() for n in funcs}
    for n, f in funcs.items():
        for c in f["rel"]["calls"] + f["rel"]["tail_jumps"]:
            if c in callers:
                callers[c].add(n)
    readers = {n: set() for n in data}
    writers = {n: set() for n in data}
    through_writers = {n: set() for n in data}
    addr_by = {n: set() for n in data}

    def base_name(x):
        return x.split("+")[0]
    for n, f in funcs.items():
        for kind, table in (("reads", readers), ("writes", writers), ("writes_through", through_writers),
                            ("address_taken", addr_by)):
            for g in f["rel"][kind]:
                b = base_name(g)
                if b in table:
                    table[b].add(n)
    field_rw = {}        # data name -> field -> {"readers", "writers"}
    for n, f in funcs.items():
        for kind, key in (("field_reads", "readers"), ("field_writes", "writers")):
            for fr in f["rel"].get(kind, ()):
                g, fld = fr.split(".", 1)
                field_rw.setdefault(g, {}).setdefault(fld, {"readers": set(), "writers": set()})[key].add(n)
    # installed handlers count as callers (interrupts)
    for isr, installer in ann.INTERRUPT_HANDLERS.items():
        callers[isr].add(f"{installer} (installs as interrupt handler)")

    # reachability: from main (C0S calls it) and the interrupt handlers
    reach, todo = set(), ["main"] + list(ann.INTERRUPT_HANDLERS)
    while todo:
        n = todo.pop()
        if n in reach:
            continue
        reach.add(n)
        todo += funcs[n]["rel"]["calls"] + funcs[n]["rel"]["tail_jumps"]

    # ------------------------------------------- cross-check: binary call graph
    bin_funcs = {f["file_offset"] - FILE_BASE for f in callgraph["functions"]}
    bin_edges = {(e["caller_id"], e["callee_id"]) for e in callgraph["call_edges"]}
    fid = {n: f"F_{f['cs'] + FILE_BASE:04X}" for n, f in funcs.items() if f["cs"] is not None}
    src_edges = set()
    for n, f in funcs.items():
        if f["kind"] != "c_function" or n not in fid:
            continue
        for c in f["rel"]["calls"]:
            if c in fid:
                src_edges.add((fid[n], fid[c]))
    game_ids = set(fid.values())
    bin_game = {(a, b) for a, b in bin_edges if a in game_ids and b in game_ids
                and a in {fid[n] for n, f in funcs.items() if f["kind"] == "c_function"}}
    # the binary walk stops a function body at its first indirect jmp (a
    # switch table): edges after it are missing from the binary graph
    truncated = {t["caller_id"] for t in callgraph["unresolved_indirect_targets"]
                 if t["kind"] == "indirect_jmp"}
    only_src = sorted(f"{a}->{b}" for a, b in src_edges - bin_game
                      if a in {f"F_{x + FILE_BASE:04X}" for x in bin_funcs})
    checks["call_graph_vs_binary"] = {
        "source_edges": len(src_edges), "binary_edges": len(bin_game),
        "only_in_source_after_a_switch_table": [e for e in only_src if e.split("->")[0] in truncated],
        "only_in_source": [e for e in only_src if e.split("->")[0] not in truncated],
        "only_in_binary": sorted(f"{a}->{b}" for a, b in bin_game - src_edges)}
    checks["call_graph_vs_binary"]["ok"] = not (checks["call_graph_vs_binary"]["only_in_source"]
                                                or checks["call_graph_vs_binary"]["only_in_binary"])
    bin_reach = {n for n, f in funcs.items() if f["cs"] is not None and f["cs"] in bin_funcs}
    by_id = {v: k for k, v in fid.items()}
    # reachable in the source but not in the binary walk: explained when every
    # source path to it passes through a truncated (switch-table) caller
    explained, changed = set(), True
    while changed:
        changed = False
        for n in reach - bin_reach - explained:
            if any((fid.get(c) in truncated) or c in explained for c in callers[n] if c in funcs):
                explained.add(n)
                changed = True
    bin_only = sorted(n for n in bin_reach - reach)
    checks["reachability_vs_binary"] = {
        "reachable_in_source_not_binary_explained_by_switch_tables": sorted(
            n for n in explained if funcs[n]["kind"] == "c_function"),
        "reachable_in_source_not_binary_unexplained": sorted(
            n for n in reach - bin_reach - explained
            if n not in ann.INTERRUPT_HANDLERS and n not in ann.ASM_ADDRESSES and funcs[n]["kind"] == "c_function"),
        "reached_in_binary_not_source": {n: ann.BINARY_WALK_ARTIFACTS.get(n, "UNEXPLAINED") for n in bin_only}}
    checks["reachability_vs_binary"]["ok"] = not (
        checks["reachability_vs_binary"]["reachable_in_source_not_binary_unexplained"]
        or "UNEXPLAINED" in checks["reachability_vs_binary"]["reached_in_binary_not_source"].values())
    del by_id

    # ----------------------------------------- cross-check: DS reference sweep
    uncovered = []
    for g in layout["globals"]:
        ds = int(g["ds_offset"], 16)
        if ds < 0x00A8 or 0x493A <= ds < 0x4C60:
            continue                          # C0S / CS.LIB _DATA (runtime)
        o, _ = owner_of(ds)
        if o is None:
            uncovered.append(g["ds_offset"])
    checks["data_layout_refs_covered"] = {"uncovered": uncovered, "ok": not uncovered}
    # U-M2: the BSS holes are referenced neither by the sources nor by any
    # DGROUP operand the binary sweep found
    refs = [int(g["ds_offset"], 16) for g in layout["globals"]]
    holes = {}
    for nm, e in data.items():
        if nm.startswith("g_unused_"):
            lo, hi = e["ds"], e["ds"] + e["size"]
            holes[nm] = {"source_refs": sorted(readers[nm] | writers[nm] | through_writers[nm] | addr_by[nm]),
                         "binary_refs": [h(r) for r in refs if lo <= r < hi]}
    checks["unused_holes_unreferenced"] = {"holes": sorted(holes),
                                           "ok": all(not v["source_refs"] and not v["binary_refs"]
                                                     for v in holes.values())}

    # ------------------------------------------------------------- assemble
    entries = []
    cur_ann = ann.FUNCTIONS
    for n in sorted(funcs, key=lambda x: (funcs[x]["cs"] if funcs[x]["cs"] is not None else 1 << 20, x)):
        f = funcs[n]
        a = cur_ann.get(n)
        if a is None:
            if not DRAFT:
                raise SystemExit(f"no annotation for function {n}")
            a = {"purpose": "TODO", "status": "unresolved", "subsystem": "TODO"}
        rel = f["rel"]
        e = {"id": ("c:" if f["kind"] == "c_function" else "asm:") + n, "kind": f["kind"], "name": n,
             "identity": {"unit": f["unit"], "cs": h(f["cs"]), "cs_end": h(f["cs_end"]),
                          "file": h(f["cs"] + FILE_BASE if f["cs"] is not None else None),
                          "size": (f["cs_end"] - f["cs"]) if (f["cs"] is not None and f["cs_end"]) else None,
                          "size_basis": f.get("size_basis") if f["kind"] == "asm_procedure" else "source header",
                          "census_id": fid.get(n), "source": f["source"],
                          "signature": f["signature"] or None},
             "purpose": a["purpose"], "status": a["status"], "subsystem": a["subsystem"],
             "evidence": [f["source"] + " (header comment)" if f["kind"] == "c_function" else f["source"]]
             + a.get("evidence", []),
             "relations": {"callers": sorted(callers[n]),
                           "callees": sorted(set(rel["calls"]) | set(rel["tail_jumps"])),
                           "library_calls": sorted(set(rel["library_calls"])),
                           "reads": sorted(rel["reads"]), "writes": sorted(rel["writes"]),
                           "writes_through_pointer": sorted(rel["writes_through"]),
                           "address_taken": sorted(rel["address_taken"])},
             "reachable": n in reach}
        for key in ("note", "ledger", "quirks"):
            if key in a:
                e[key] = a[key]
        entries.append(e)
    for n in sorted(data, key=lambda x: (0 if "ds" in data[x] else 1 if "cs" in data[x] else 2,
                                         data[x].get("ds") or data[x].get("cs") or data[x].get("para") or 0, x)):
        d = data[n]
        a = ann.DATA.get(n)
        if a is None:
            if not DRAFT:
                raise SystemExit(f"no annotation for data object {n}")
            a = {"purpose": "TODO", "status": "unresolved", "subsystem": "TODO", "role": "layout_artifact"}
        ident = {"unit": d["unit"], "segment": d["segment"], "type": d["type"], "size": d["size"],
                 "source": d["source"]}
        if "ds" in d:
            ident["ds"] = h(d["ds"])
            ident["file"] = h(0x256D0 + d["ds"], 5) if d["ds"] < 0x4C60 else None
        if "cs" in d:
            ident["cs"] = h(d["cs"])
            ident["file"] = h(d["cs"] + FILE_BASE) if d["cs"] is not None else None
        if "para" in d:
            ident["far"] = f"{d['para']:04X}:0000"
            ident["file"] = h(d["para"] * 16 + FILE_BASE, 5)
        if "storage_name" in d and d["storage_name"] != n:
            ident["storage_name"] = d["storage_name"]
        e = {"id": "data:" + n, "kind": d["kind"], "name": n, "identity": ident,
             "purpose": a["purpose"], "status": a["status"], "subsystem": a["subsystem"], "role": a["role"],
             "evidence": [d["source"]] + a.get("evidence", []),
             "relations": {"readers": sorted(readers[n]), "writers": sorted(writers[n]),
                           "written_through_pointer_by": sorted(through_writers[n]),
                           "address_taken_by": sorted(addr_by[n])}}
        if n in field_rw:
            whole = sorted(f for f in funcs if n in funcs[f]["rel"].get("whole_writes", ()))
            e["relations"]["fields"] = {fld: {"readers": sorted(v["readers"]), "writers": sorted(v["writers"])}
                                        for fld, v in sorted(field_rw[n].items())}
            e["relations"]["whole_object_writers"] = whole   # struct copies, setmem/movmem targets
        if d.get("source_comment"):
            e["source_comment"] = d["source_comment"]
        for key in ("note", "ledger", "fields", "width", "quirks"):
            if key in a:
                e[key] = a[key]
        entries.append(e)
    for n, a in ann.FORMATS.items():
        entries.append({"id": "format:" + n, "kind": "resource_format", "name": n,
                        "identity": a["identity"], "purpose": a["purpose"], "status": a["status"],
                        "subsystem": a["subsystem"], "evidence": a["evidence"],
                        "relations": {"objects": a.get("objects", []), "codec": a.get("codec")},
                        **({"note": a["note"]} if "note" in a else {}),
                        **({"ledger": a["ledger"]} if "ledger" in a else {})})
    # subsystems: members gathered mechanically from the subsystem tags
    for n, a in ann.SUBSYSTEMS.items():
        members = [e["id"] for e in entries if e["subsystem"] == n]
        st = [e["status"] for e in entries if e["subsystem"] == n]
        if not members and not DRAFT:
            raise SystemExit(f"subsystem {n} has no members")
        if all(s == "understood" for s in st):
            agg = "understood"
        elif all(s == "unresolved" for s in st):
            agg = "unresolved"
        else:
            agg = "partial"
        entries.append({"id": "subsystem:" + n, "kind": "subsystem", "name": n,
                        "identity": {"members": len(members)}, "purpose": a["purpose"],
                        "status": agg, "subsystem": n, "evidence": a.get("evidence", []),
                        "relations": {"members": members,
                                      "member_status": {s: st.count(s) for s in STATUSES if st.count(s)}},
                        **({"open": a["open"]} if "open" in a else {})})
    tags = {e["subsystem"] for e in entries}
    unknown = sorted(tags - set(ann.SUBSYSTEMS))
    if unknown and not DRAFT:
        raise SystemExit(f"unknown subsystem tags: {unknown}")
    for e in entries:
        if e["status"] not in STATUSES:
            raise SystemExit(f"{e['id']}: bad status {e['status']}")
        if e["kind"] in ("global",) and e.get("role") not in ROLES:
            raise SystemExit(f"{e['id']}: bad role {e.get('role')}")
    extra = sorted(set(ann.FUNCTIONS) - set(funcs)) + sorted(set(ann.DATA) - set(data))
    if extra:
        raise SystemExit(f"annotations for unknown entries: {extra}")

    counts = {}
    for e in entries:
        counts.setdefault(e["kind"], {}).setdefault(e["status"], 0)
        counts[e["kind"]][e["status"]] += 1
    return {"schema": "dave-semantic-inventory-v1",
            "generator": "tools/semantic_inventory.py (annotations: tools/semantic_annotations.py)",
            "address_convention": "cs = CS offset (file - 0x200); file = offset in build/DAVE_unpacked.exe; "
                                  "DS = DGROUP offset (DS:0 = file 0x256D0); far = paragraph:offset",
            "statuses": list(STATUSES), "roles": ann.ROLE_DOC,
            "counts": counts, "checks": checks, "entries": entries}


# ===================================================================== output

def md_escape(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def markdown(doc: dict) -> str:
    out = ["# Semantic inventory", "",
           "Generated by `python tools/semantic_inventory.py` from the recovered sources",
           "(identities and relations, parsed mechanically) and `tools/semantic_annotations.py`",
           "(purpose, status, evidence, subsystem, role). Do not edit by hand; `--check` verifies",
           "that this file and `semantic-inventory.json` are current. Machine-readable",
           "relations (callers/callees, readers/writers) are in the JSON.", "",
           "Statuses: **understood** (behaviour and representation explained with evidence),",
           "**partial**, **behaviour_understood_representation_unclear**,",
           "**representation_understood_behaviour_unclear**, **unresolved**.", "",
           "## Counts", "", "| kind | " + " | ".join(STATUSES) + " | total |",
           "|---|" + "---|" * (len(STATUSES) + 1)]
    for kind, c in doc["counts"].items():
        out.append(f"| {kind} | " + " | ".join(str(c.get(s, 0)) for s in STATUSES) + f" | {sum(c.values())} |")
    out += ["", "## Mechanical cross-checks", ""]
    for k, v in doc["checks"].items():
        out.append(f"- `{k}`: {json.dumps(v)}")
    out += ["", "## Roles of data objects", ""]
    for k, v in doc["roles"].items():
        out.append(f"- **{k}**: {v}")
    sections = [("subsystem", "Subsystems"), ("c_function", "C functions"), ("asm_procedure", "Assembly procedures"),
                ("global", "Global variables and DGROUP / CS-resident data objects"),
                ("far_data", "Far data segments"), ("resource_format", "Resource and record formats")]
    by_kind = {}
    for e in doc["entries"]:
        by_kind.setdefault(e["kind"], []).append(e)
    for kind, title in sections:
        es = by_kind.get(kind, [])
        out += ["", f"## {title} ({len(es)})", ""]
        if kind == "subsystem":
            for e in es:
                ms = e["relations"]["member_status"]
                out.append(f"### {e['name']} -- {e['status']}")
                out.append("")
                out.append(e["purpose"])
                out.append("")
                out.append("Members: " + ", ".join(f"{v} {k}" for k, v in ms.items()) + ".")
                if e.get("open"):
                    out.append("Open: " + "; ".join(e["open"]) + ".")
                out.append("")
            continue
        if kind in ("c_function", "asm_procedure"):
            out += ["| name | cs | size | unit | subsystem | status | purpose | callers | callees |",
                    "|---|---|---|---|---|---|---|---|---|"]
            for e in es:
                i, r = e["identity"], e["relations"]
                out.append(f"| `{e['name']}`{'' if e['reachable'] else ' (unreachable)'} | {i['cs'] or '?'} | "
                           f"{i['size'] if i['size'] is not None else '?'} | {i['unit']} | {e['subsystem']} | "
                           f"{e['status']} | {md_escape(e['purpose'])} | {len(r['callers'])} | "
                           f"{', '.join(r['callees']) or '-'} |")
        elif kind in ("global", "far_data"):
            out += ["| name | address | size | type | role | subsystem | status | purpose | readers / writers |",
                    "|---|---|---|---|---|---|---|---|---|"]
            for e in es:
                i, r = e["identity"], e["relations"]
                addr = ("DS " + i["ds"]) if i.get("ds") else ("cs " + i["cs"]) if i.get("cs") else \
                    ("far " + i["far"]) if i.get("far") else "?"
                out.append(f"| `{e['name']}` | {addr} | {i['size']} | `{md_escape(i['type'])}` | {e['role']} | "
                           f"{e['subsystem']} | {e['status']} | {md_escape(e['purpose'])} | "
                           f"{len(r['readers'])} / {len(r['writers']) + len(r['written_through_pointer_by'])} |")
        else:
            out += ["| name | where | subsystem | status | purpose |", "|---|---|---|---|---|"]
            for e in es:
                out.append(f"| `{e['name']}` | {md_escape(e['identity'].get('where', ''))} | {e['subsystem']} | "
                           f"{e['status']} | {md_escape(e['purpose'])} |")
    # details of everything not understood: what is missing
    out += ["", "## Not fully understood: what is missing", ""]
    for e in doc["entries"]:
        if e["status"] != "understood" and e["kind"] != "subsystem":
            out.append(f"- `{e['id']}` ({e['status']}): {md_escape(e.get('note', e['purpose']))}")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--draft", action="store_true", help="placeholders for missing annotations (development)")
    args = ap.parse_args()
    global DRAFT
    DRAFT = args.draft
    doc = build()
    js = json.dumps(doc, indent=1) + "\n"
    md = markdown(doc)
    if args.check:
        bad = [p for p, s in ((OUT_JSON, js), (OUT_MD, md))
               if not p.exists() or p.read_text(encoding="utf-8") != s]
        failed = [k for k, v in doc["checks"].items() if isinstance(v, dict) and v.get("ok") is False]
        for p in bad:
            print(f"stale: {p.relative_to(ROOT)} (run python tools/semantic_inventory.py)")
        for k in failed:
            print(f"check failed: {k}: {doc['checks'][k]}")
        sys.exit(1 if bad or failed else 0)
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON.relative_to(ROOT)}, {OUT_MD.relative_to(ROOT)}: "
          + ", ".join(f"{k} {sum(v.values())}" for k, v in doc["counts"].items()))


if __name__ == "__main__":
    main()
