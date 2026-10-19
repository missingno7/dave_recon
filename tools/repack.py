"""Pack an unpacked MZ image with the pinned LZEXE 0.91 under DOSBox-X.

    python tools/repack.py IN.EXE OUT.EXE
    python tools/repack.py --oracle    repack build/DAVE_unpacked.exe and compare
                                       with assets/DAVE.EXE (the packed original)

Verified 2026-10-19: LZEXE 0.91 is deterministic; packing the unpacked image
reproduces the original DAVE.EXE byte for byte (SHA-256 1ae77982...). So the
packed level of the reconstruction reduces to producing the unpacked image.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKER = json.loads((ROOT / "layout" / "packer.json").read_text())


def lzexe_path() -> pathlib.Path:
    p = ROOT / "toolchain" / "LZEXE" / "LZEXE.EXE"
    if not p.exists():
        raise SystemExit("toolchain/LZEXE/LZEXE.EXE missing; run tools/bootstrap.py")
    if hashlib.sha256(p.read_bytes()).hexdigest() != PACKER["sha256"]:
        raise SystemExit("toolchain/LZEXE/LZEXE.EXE does not match layout/packer.json")
    return p


def pack(unpacked: bytes) -> bytes:
    w = ROOT / "build" / "repack" / uuid.uuid4().hex[:10]
    w.mkdir(parents=True)
    try:
        (w / "IN.EXE").write_bytes(unpacked)
        shutil.copy(lzexe_path(), w / "LZEXE.EXE")
        (w / "GO.BAT").write_bytes(b"@ECHO OFF\r\nD:\r\nCD \\r\nLZEXE.EXE IN.EXE > LZ.LOG\r\nEXIT\r\n")
        (w / "dosbox.conf").write_text("[sdl]\nautolock=false\n\n[cpu]\ncycles=max\n\n[autoexec]\n"
                                       f'mount d "{w}"\nd:\nGO.BAT\nexit\n')
        subprocess.run([PACKER["dosbox"], "-conf", str(w / "dosbox.conf"), "-noconsole", "-exit"],
                       timeout=240)
        if not (w / "IN.OLD").exists():
            raise RuntimeError("LZEXE did not run: " + ((w / "LZ.LOG").read_text(errors="replace")
                                                        if (w / "LZ.LOG").exists() else "no log"))
        return (w / "IN.EXE").read_bytes()
    finally:
        shutil.rmtree(w, ignore_errors=True)


def main() -> int:
    if sys.argv[1:2] == ["--oracle"]:
        packed = pack((ROOT / "build" / "DAVE_unpacked.exe").read_bytes())
        orig = (ROOT / "assets" / "DAVE.EXE").read_bytes()
        print(f"repacked {len(packed)} B sha256 {hashlib.sha256(packed).hexdigest()[:16]} "
              f"{'== original DAVE.EXE' if packed == orig else 'DIFFERS from original'}")
        return 0 if packed == orig else 1
    pathlib.Path(sys.argv[2]).write_bytes(pack(pathlib.Path(sys.argv[1]).read_bytes()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
