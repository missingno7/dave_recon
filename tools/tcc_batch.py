"""Compile many C sources with the pinned Turbo C++ 1.00 in ONE DOSBox-X session.

tools/compile_probe.py starts a fresh DOSBox-X per compile (~2 s each). For
experiment sweeps (flag A/B tests, the codegen catalog in tools/codegen_lab/)
that is too slow, so this module writes every job into one work directory,
generates a single GO.BAT that runs TCC once per job, and boots DOSBox-X once.

Each job is (name, source_text, flags). `flags` is the FULL TCC switch list
for that job except `-c` and the include path (so a job states its model,
e.g. "-ms -1- -f- -N"); DEFAULT_FLAGS is the project's current baseline.
Job names are mapped to DOS 8.3 file names J0001.C, J0002.C, ... so callers
may use any name they like.

    from tcc_batch import compile_many, DEFAULT_FLAGS
    results = compile_many([("probe", "int f(int a){return a+1;}", DEFAULT_FLAGS)])
    results["probe"].obj        # bytes of the .OBJ, or None on failure
    results["probe"].log        # TCC's console output
    results["probe"].module()   # omf.ObjectModule

Command line (compile .c files, print _TEXT disassembly):
    python tools/tcc_batch.py a.c b.c [--flags "-ms -1- -f- -N -O"] [--asm]

`--asm` additionally runs TCC with -S and prints the compiler's own assembly
listing (useful for seeing symbol names behind fixups).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess

import dosrun
import tcc as tcc_driver
import sys
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import omf  # noqa: E402

TOOLCHAIN_DIR = ROOT / "toolchain"
DEFAULT_FLAGS = "-ms -1- -f- -N"


def dosbox_exe() -> str:
    lock = json.loads((ROOT / "layout" / "toolchain.json").read_text())
    return lock["dosbox_default"]


def toolchain_available() -> bool:
    return (TOOLCHAIN_DIR / "BIN" / "TCC.EXE").exists() and pathlib.Path(dosbox_exe()).exists()


@dataclass
class Result:
    name: str
    flags: str
    obj: bytes | None
    log: str
    asm: str | None = None
    stem: str = ""          # the DOS file stem used (J0001...): module/segment names derive from it

    def module(self) -> omf.ObjectModule:
        if self.obj is None:
            raise RuntimeError(f"{self.name}: compile failed:\n{self.log}")
        return omf.OmfReader().read(self.obj, self.name)

    def text(self) -> bytes:
        mod = self.module()
        return mod.segment_bytes("_TEXT") if "_TEXT" in mod.segments else b""


def compile_many(jobs, workdir: pathlib.Path | None = None, asm: bool = False,
                 timeout: int = 600) -> dict:
    """Compile every (name, source, flags) job: under MS-DOS Player by default
    (tools/dosrun.py), or in one DOSBox-X session with DAVE_DOS_HOST=dosbox."""
    jobs = list(jobs)
    work = workdir or (ROOT / "build" / "tcc_batch")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    lines = ["@ECHO OFF", "D:", "CD \\", "SET INCLUDE=C:\\INCLUDE"]
    stems = {}
    for n, (name, source, flags) in enumerate(jobs, 1):
        stem = f"J{n:04d}"
        stems[name] = (stem, flags)
        (work / f"{stem}.C").write_text(source.replace("\r\n", "\n").replace("\n", "\r\n"),
                                        encoding="latin1")
        lines.append(f"C:\\BIN\\TCC.EXE -c {flags} -IC:\\INCLUDE {stem}.C > {stem}.LOG")
        if asm:
            lines.append(f"C:\\BIN\\TCC.EXE -S {flags} -IC:\\INCLUDE {stem}.C > NUL")
    lines.append("ECHO DONE > DONE.TXT")
    lines.append("EXIT")
    if dosrun.use_msdos():
        tcc_exe, inc = TOOLCHAIN_DIR / "BIN" / "TCC.EXE", "-I" + str(TOOLCHAIN_DIR / "INCLUDE")
        tasm_dir = TOOLCHAIN_DIR / tcc_driver.assembler_dir()
        for name, (stem, flags) in stems.items():
            _, log = dosrun.run([tcc_exe, "-c", *flags.split(), inc, f"{stem}.C"], cwd=work,
                                tool_dirs=[tasm_dir])
            (work / f"{stem}.LOG").write_text(log, encoding="latin1")
            if asm:
                dosrun.run([tcc_exe, "-S", *flags.split(), inc, f"{stem}.C"], cwd=work,
                           tool_dirs=[tasm_dir])
        (work / "DONE.TXT").write_text("DONE\r\n")
    else:
        _run_dosbox(work, lines, timeout)
    return _collect(work, stems)


def _run_dosbox(work: pathlib.Path, lines: list, timeout: int):
    """Cross-check host (DAVE_DOS_HOST=dosbox): one DOSBox-X session for all jobs."""
    (work / "GO.BAT").write_text("\r\n".join(lines) + "\r\n")
    (work / "dosbox.conf").write_text(
        "[sdl]\nautolock=false\n\n"
        "[dosbox]\nmemsize=16\n\n"
        "[cpu]\ncycles=max\n\n"
        "[autoexec]\n"
        f'mount c "{TOOLCHAIN_DIR}"\n'
        f'mount d "{work}"\n'
        "d:\nGO.BAT\nexit\n")
    subprocess.run([dosbox_exe(), "-conf", str(work / "dosbox.conf"), "-noconsole", "-exit"],
                   cwd=ROOT, timeout=timeout)
    if not (work / "DONE.TXT").exists():
        raise RuntimeError(f"DOSBox-X batch did not finish; see {work}")


def _collect(work: pathlib.Path, stems: dict) -> dict:
    out = {}
    for name, (stem, flags) in stems.items():
        obj = work / f"{stem}.OBJ"
        log = work / f"{stem}.LOG"
        asm_path = work / f"{stem}.ASM"
        out[name] = Result(
            name=name, flags=flags, stem=stem,
            obj=obj.read_bytes() if obj.exists() else None,
            log=log.read_text(errors="replace") if log.exists() else "",
            asm=asm_path.read_text(errors="replace") if asm_path.exists() else None)
    return out


def disassemble(code: bytes, base: int = 0, fixups=()) -> list:
    """[(offset, hex bytes, text)] of 16-bit code; fixup-covered offsets get a note."""
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
    fx = {f["offset"]: f for f in fixups}
    rows = []
    at = 0
    while at < len(code):
        insns = list(md.disasm(code[at:], base + at, count=1))
        if not insns:
            rows.append((base + at, code[at:at + 1].hex(), "db"))
            at += 1
            continue
        i = insns[0]
        note = ""
        for o in range(i.address - base, i.address - base + i.size):
            if o in fx:
                note += f"  ; fixup->{fx[o]['target']}"
        rows.append((i.address, i.bytes.hex(), f"{i.mnemonic} {i.op_str}{note}"))
        at += i.size
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", type=pathlib.Path)
    ap.add_argument("--flags", default=DEFAULT_FLAGS)
    ap.add_argument("--asm", action="store_true")
    args = ap.parse_args()
    jobs = [(p.stem, p.read_text(encoding="latin1"), args.flags) for p in args.sources]
    res = compile_many(jobs, asm=args.asm)
    for p in args.sources:
        r = res[p.stem]
        print(f"=== {p.name}  [{r.flags}]")
        if r.obj is None:
            print(r.log)
            continue
        mod = r.module()
        print("segments:", {k: len(v) for k, v in mod.segments.items()},
              "lengths:", mod.segment_lengths)
        print("publics:", [(x["name"], x["segment"], hex(x["offset"])) for x in mod.publics])
        for off, hx, txt in disassemble(r.text(), 0, mod.fixups_in("_TEXT")):
            print(f"  {off:04x}  {hx:14s} {txt}")
        if r.asm:
            print(r.asm)


if __name__ == "__main__":
    main()
