"""Batch compiler: many C sources through the pinned TCC in ONE DOSBox-X session.

Each source is copied to an 8.3 name (S0001.C ...) in a fresh work directory,
compiled with the project flags plus per-file extras, and the .OBJ paths are
returned in input order (None for a failed compile; its log is kept).

    from tcc import compile_many
    objs = compile_many([pathlib.Path("src/game/F_6D64.c")])

Project flags: -c -ms -1- -f- -N  (small model and -N are proven; see
docs/flag-investigation.md and tools/compile_probe.py). A source can add
flags with a directive comment:  /* @flags -O */
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLCHAIN = json.loads((ROOT / "layout" / "toolchain.json").read_text())
BASE_FLAGS = "-c -ms -1- -f- -N -G"


def assembler_dir() -> str:
    """toolchain/ subdirectory holding the TASM used for inline asm."""
    lock = ROOT / "layout" / "assembler.json"
    if lock.exists():
        return json.loads(lock.read_text()).get("toolchain_dir", "TASM20")
    return "TASM20"


def source_flags(text: str) -> str:
    return " ".join(re.findall(r"@flags\s+([^*\n]+?)\s*\*/", text))


def compile_many(sources, work: pathlib.Path | None = None, extra_flags: str = "") -> list:
    work = work or (ROOT / "build" / "tcc_batch")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    # TCC restarts a compile through TASM when a file contains inline `asm`
    # statements (Turbo C++ 1.00 has no built-in assembler); TASM is found
    # through PATH. layout/assembler.json pins which TASM that is.
    lines = ["@ECHO OFF", "SET PATH=C:\\BIN;C:\\" + assembler_dir(), "D:", "CD \\"]
    stems = []
    for n, src in enumerate(sources, 1):
        stem = f"S{n:04d}"
        stems.append(stem)
        text = pathlib.Path(src).read_text(encoding="latin1")
        (work / f"{stem}.C").write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("latin1"))
        flags = f"{BASE_FLAGS} {source_flags(text)} {extra_flags}".strip()
        lines.append(f"C:\\BIN\\TCC.EXE {flags} -IC:\\INCLUDE {stem}.C > {stem}.LOG")
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
        out.append(obj if obj.exists() else None)
    return out


def log_for(obj_or_none, work: pathlib.Path, index: int) -> str:
    p = work / f"S{index + 1:04d}.LOG"
    return p.read_text(errors="replace") if p.exists() else ""
