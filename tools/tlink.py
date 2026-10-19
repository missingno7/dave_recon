"""Run the pinned TLINK (Turbo C++ 1.00) under DOSBox-X.

    from tlink import link
    exe, map_text, log = link([obj1, obj2], work=pathlib.Path("build/link"),
                              options="/m", startup="C0S", libs=["CS"])

Objects are copied into the work directory under their own 8.3 names; the
startup object and libraries come from toolchain/LIB. A response file is
used so long object lists work, and stdin is never needed (TLINK prompts on
errors would otherwise hang DOSBox; a timeout kills it).
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLCHAIN = json.loads((ROOT / "layout" / "toolchain.json").read_text())


def link(objs, work: pathlib.Path, options: str = "/m", startup: str = "C0S",
         libs=("CS",), out: str = "OUT", timeout: int = 60):
    work = pathlib.Path(work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    names = []
    for o in objs:
        o = pathlib.Path(o)
        shutil.copyfile(o, work / o.name.upper())
        names.append(o.stem.upper())
    objs_part = " ".join([f"C:\\LIB\\{startup}"] + names)
    libs_part = " ".join(f"C:\\LIB\\{l}" for l in libs)
    # TLINK response file: objs, exe, map, libs
    rsp = f"{options} {objs_part}\r\n{out}\r\n{out}\r\n{libs_part}\r\n"
    (work / "LINK.RSP").write_bytes(rsp.encode("ascii"))
    (work / "GO.BAT").write_bytes(
        ("@ECHO OFF\r\nD:\r\nCD \\\r\nC:\\BIN\\TLINK.EXE @LINK.RSP > LINK.LOG\r\nEXIT\r\n").encode("ascii"))
    conf = work / "dosbox.conf"
    conf.write_text("[sdl]\nautolock=false\n\n[cpu]\ncycles=max\n\n[autoexec]\n"
                    f'mount c "{ROOT / "toolchain"}"\n'
                    f'mount d "{work}"\n'
                    "d:\nGO.BAT\nexit\n")
    try:
        subprocess.run([TOOLCHAIN["dosbox_default"], "-conf", str(conf), "-noconsole", "-exit"],
                       cwd=ROOT, timeout=timeout)
    except subprocess.TimeoutExpired:
        pass
    exe = work / f"{out}.EXE"
    mp = work / f"{out}.MAP"
    log = work / "LINK.LOG"
    return (exe if exe.exists() else None,
            mp.read_text(errors="replace") if mp.exists() else "",
            log.read_text(errors="replace") if log.exists() else "")
