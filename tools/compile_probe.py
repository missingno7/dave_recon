"""Compile a small C source file with the pinned Turbo C++ toolchain via DOSBox-X.

This is the minimal reusable compile harness for the "historical compile
laboratory" (docs/vision.md phase 3): given a .C file, produce the .OBJ TCC
emits, for OMF inspection/comparison. No cached .OBJ is ever reused — each
call runs a fresh DOSBox-X session.

Usage:
    python tools/compile_probe.py path/to/probe.c [--model s|c|m|l|h] [--flags "..."]

Default model is "s" (small): docs/startup-binding-evidence.json proves the
game's own C0 startup module is Turbo C++ 1.00's small-model C0S.OBJ (every
byte differing from that raw library object is explained by a linker
fixup, uniquely among all 5 memory models). Compact ("c") was only ever an
untested starting guess borrowed from the sibling empires_reconstruction
project (which targets a different game/compiler) and must not be used as
the default here.

Writes build/<stem>/PROBE.OBJ (or FAILED.TXT + BUILD.LOG on failure) and
prints the OMF THEADR comment (compiler self-identification string) plus a
segment/public summary via tools/omf.py.
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import omf  # noqa: E402

TOOLCHAIN = json.loads((ROOT / "layout" / "toolchain.json").read_text())

MODEL_FLAG = {"c": "-mc", "s": "-ms", "m": "-mm", "l": "-ml", "h": "-mh"}


def run(source: pathlib.Path, model: str, extra_flags: str):
    stem = source.stem.upper()[:8]
    work = ROOT / "build" / f"probe_{source.stem}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copyfile(source, work / f"{stem}.C")

    # -N (stack overflow checking ON) is an empirically confirmed match: the
    # real _main @ file offset 0x439 opens with 55 8B EC 39 26 9A 00 72 03 E8
    # (push bp; mov bp,sp; cmp [stackbase],sp; jb +3; call <stack-overflow
    # handler>), which is exactly Turbo C++ 1.00's -N stack-check stub with
    # zero locals (no `sub sp,N` between the frame setup and the check).
    # Confirmed by compiling tests/fixtures/probe2.c with -N and comparing
    # instruction-for-instruction (see docs/flag-investigation.md). Do not
    # revert this to -N- without fresh evidence.
    flags = f"-c {MODEL_FLAG[model]} -1- -f- -N {extra_flags}".strip()
    bat = work / "GO.BAT"
    bat.write_text(
        "@ECHO OFF\r\n"
        "D:\r\nCD \\\r\n"
        "SET INCLUDE=C:\\INCLUDE\r\n"
        f"C:\\BIN\\TCC.EXE {flags} -IC:\\INCLUDE {stem}.C > BUILD.LOG\r\n"
        f"IF EXIST {stem}.OBJ (ECHO SUCCESS > SUCCESS.TXT) ELSE (ECHO FAILED > FAILED.TXT)\r\n"
        "EXIT\r\n"
    )
    conf = work / "dosbox.conf"
    conf.write_text(
        "[sdl]\nautolock=false\n\n"
        "[cpu]\ncycles=max\n\n"
        "[autoexec]\n"
        f'mount c "{ROOT / "toolchain"}"\n'
        f'mount d "{work}"\n'
        "d:\nGO.BAT\nexit\n"
    )

    dosbox = TOOLCHAIN["dosbox_default"]
    subprocess.run([dosbox, "-conf", str(conf), "-noconsole", "-exit"], cwd=ROOT, timeout=60)

    obj_path = work / f"{stem}.OBJ"
    if not obj_path.exists():
        log = (work / "BUILD.LOG")
        raise SystemExit(f"compile failed; see {log}\n{log.read_text(errors='replace') if log.exists() else ''}")
    return obj_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("--model", default="s", choices=list(MODEL_FLAG))
    parser.add_argument("--flags", default="")
    args = parser.parse_args()

    obj_path = run(args.source, args.model, args.flags)
    data = obj_path.read_bytes()
    mod = omf.OmfReader().read(data, obj_path.stem)

    print(f"OBJ: {obj_path.relative_to(ROOT)} ({len(data)} bytes)")
    print(f"segments: { {k: len(v) for k, v in mod.segments.items()} }")
    print(f"publics: {mod.publics}")


if __name__ == "__main__":
    main()
