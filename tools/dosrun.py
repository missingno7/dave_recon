"""Run a DOS command-line tool (TCC, TASM, TLINK, LZEXE) under MS-DOS Player.

MS-DOS Player (C:/tools/nmlgcdos/msdos.exe, SHA-256 pinned below; see
C:/tools/CATALOG.md) executes a DOS program directly from a Windows console:
no emulator boot, no config file, ~0.3 s per tool run instead of ~2 s under
DOSBox-X. It inherits the Windows environment, so PATH (for TCC's restart
through TASM) is passed as an ordinary environment variable.

DOSBox-X stays the host for the behavioural oracle (tools/oracle.py), which
needs emulated video/timer hardware and emulated time; the build tools only
need DOS file services and are byte-identical under either host
(tests/test_build.py, tools/verify_sources.py).

    from dosrun import run
    rc, out = run(["TCC.EXE", "-c", "X.C"], cwd=work, tool_dirs=[...])
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess

MSDOS = pathlib.Path(os.environ.get("DAVE_MSDOS", "C:/tools/nmlgcdos/msdos.exe"))
MSDOS_SHA256 = "f7f6cb0a3e816c5edb13112d327c1bddbf7463fe7bf9a005ca1eb5317751bd02"
_checked = False


def available() -> bool:
    global _checked
    if not MSDOS.exists():
        return False
    if not _checked:
        if hashlib.sha256(MSDOS.read_bytes()).hexdigest() != MSDOS_SHA256:
            raise SystemExit(f"{MSDOS} is not the pinned MS-DOS Player build")
        _checked = True
    return True


def use_msdos() -> bool:
    """MS-DOS Player is the build-tool host unless DAVE_DOS_HOST=dosbox
    (kept as a cross-check host) or it is not installed."""
    return os.environ.get("DAVE_DOS_HOST", "msdos") != "dosbox" and available()


def run(argv, cwd: pathlib.Path, tool_dirs=(), timeout: int = 120):
    """Run argv[0] (a DOS executable path) with argv[1:] in `cwd`.
    `tool_dirs` are prepended to PATH (Windows paths). Returns (rc, output)."""
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(pathlib.Path(d)) for d in tool_dirs] + [env.get("PATH", "")])
    p = subprocess.run([str(MSDOS), "-e"] + [str(a) for a in argv], cwd=cwd, env=env,
                       capture_output=True, timeout=timeout)
    out = (p.stdout + p.stderr).decode("latin1", errors="replace")
    return p.returncode, out
