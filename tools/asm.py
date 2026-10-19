"""Batch assembler: many .asm sources through a pinned DOS assembler in ONE DOSBox-X session.

Mirrors tools/tcc.py. Each source is copied to an 8.3 name (S0001.ASM ...)
in a fresh work directory, assembled, and the .OBJ paths are returned in
input order (None when assembly failed; the listing/log is kept).

    from asm import assemble_many
    objs = assemble_many([pathlib.Path("src/asm/sound.asm")])

The assembler and its default options come from layout/assembler.json
("assembler" key, "options"). Candidate assemblers live in the git-ignored
toolchain/ASM/<KEY>/ (e.g. toolchain/ASM/TASM200/TASM.EXE); KEYS lists every
key this driver knows how to invoke, so assembler-identification probes can
run the same source through all of them. A source may add options with a
directive comment:  ; @asmflags /ml
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLCHAIN = json.loads((ROOT / "layout" / "toolchain.json").read_text())
CONFIG_PATH = ROOT / "layout" / "assembler.json"

# key -> (executable, command-line style)
KEYS = {
    "TASM100": ("TASM.EXE", "tasm"),
    "TASM101": ("TASM.EXE", "tasm"),
    "TASM200": ("TASM.EXE", "tasm"),
    "TASM201": ("TASM.EXE", "tasm"),
    "MASM400": ("MASM.EXE", "masm"),
    "MASM500": ("MASM.EXE", "masm"),
    "MASM510": ("MASM.EXE", "masm"),
    "MASM51A": ("MASM.EXE", "masm"),
}


def pinned() -> tuple[str, str]:
    """(assembler key, default options) from layout/assembler.json."""
    cfg = json.loads(CONFIG_PATH.read_text())
    return cfg["assembler"], cfg.get("options", "")


def source_flags(text: str) -> str:
    return " ".join(m.strip() for m in re.findall(r";\s*@asmflags\s+([^\n]+)", text))


def command(key: str, options: str, stem: str) -> str:
    exe, style = KEYS[key]
    path = f"C:\\ASM\\{key}\\{exe}"
    if style == "tasm":
        return f"{path} {options} {stem}.ASM,{stem}.OBJ,{stem}.LST > {stem}.LOG"
    return f"{path} {options} {stem}.ASM,{stem}.OBJ,{stem}.LST,NUL; > {stem}.LOG"


def assemble_many(sources, key: str | None = None, options: str | None = None,
                  work: pathlib.Path | None = None) -> list:
    """Assemble every source; return [Path to .OBJ or None] in input order."""
    if key is None or options is None:
        pkey, popts = pinned()
        key = key or pkey
        options = popts if options is None else options
    if key not in KEYS:
        raise SystemExit(f"unknown assembler key {key!r}; known: {', '.join(KEYS)}")
    exe = ROOT / "toolchain" / "ASM" / key / KEYS[key][0]
    if not exe.exists():
        raise SystemExit(f"{exe} missing; see layout/assembler.json for provenance")
    work = work or (ROOT / "build" / "asm_batch")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    lines = ["@ECHO OFF", "D:", "CD \\"]
    stems = []
    # INCLUDE files live next to the sources; the assembler sees them in D:\.
    for inc_dir in {pathlib.Path(s).resolve().parent for s in sources}:
        for inc in inc_dir.glob("*.inc"):
            text = inc.read_text(encoding="latin1")
            (work / inc.name.upper()).write_bytes(
                text.replace("\r\n", "\n").replace("\n", "\r\n").encode("latin1"))
    for n, src in enumerate(sources, 1):
        stem = f"S{n:04d}"
        stems.append(stem)
        text = pathlib.Path(src).read_text(encoding="latin1")
        (work / f"{stem}.ASM").write_bytes(
            text.replace("\r\n", "\n").replace("\n", "\r\n").encode("latin1"))
        flags = f"{options} {source_flags(text)}".strip()
        lines.append(command(key, flags, stem))
    lines.append("EXIT")
    (work / "GO.BAT").write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii"))
    conf = work / "dosbox.conf"
    conf.write_text(
        "[sdl]\nautolock=false\n\n[cpu]\ncycles=max\n\n[dosbox]\nmemsize=16\n\n"
        "[autoexec]\n"
        f'mount c "{ROOT / "toolchain"}"\n'
        f'mount d "{work}"\n'
        "d:\nGO.BAT\nexit\n")
    subprocess.run([TOOLCHAIN["dosbox_default"], "-conf", str(conf), "-noconsole", "-exit"],
                   cwd=ROOT, timeout=60 + 5 * len(sources))
    out = []
    for stem in stems:
        obj = work / f"{stem}.OBJ"
        out.append(obj if obj.exists() and obj.stat().st_size > 0 else None)
    return out


def log_for(work: pathlib.Path, index: int) -> str:
    p = work / f"S{index + 1:04d}.LOG"
    return p.read_text(errors="replace") if p.exists() else ""
