"""Prepare a fresh checkout (or git worktree) for building and matching.

Idempotent. Does three things, verifying hashes at every step:

1. Installs the pinned Turbo C++ 1.00 toolchain into toolchain/ (BIN/, LIB/,
   INCLUDE/) from a local extracted copy. Source directory, first hit wins:
   $DAVE_TOOLCHAIN_SRC, then C:/tools/borland-turbo-c++-1.00/files (see that
   directory's provenance.json: archive.org item borland-turbo-c-plus-plus).
   Every file listed in layout/toolchain.json is checked against its sha256.
2. Copies the original game files into assets/ if missing, from
   $DAVE_ASSETS or D:/Prog/dave_recon/assets (the primary checkout), and
   checks them against docs/specimen-manifest.json's sizes/hashes.
3. Unpacks assets/DAVE.EXE to build/DAVE_unpacked.exe and checks its md5
   against layout/manifest.json.

Usage: python tools/bootstrap.py
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCK = json.loads((ROOT / "layout" / "toolchain.json").read_text())
TOOLCHAIN = ROOT / "toolchain"
DEFAULT_TOOLCHAIN_SRC = pathlib.Path("C:/tools/borland-turbo-c++-1.00/files")
DEFAULT_ASSETS = pathlib.Path("D:/Prog/dave_recon/assets")
TASM20_SHA256 = "672cc3814fb66fcb73550aa5ad98049bb52ebcd66c66dcdedbe81d83335e62ff"  # Turbo Assembler 2.0

ASSET_SHA256 = {
    "DAVE.EXE": "1ae779823df27f2c6ae03b2e7d2a8c154d4189a5074d444827783fb2f1f92a0a",
    "EGADAVE.DAV": "0eb13af0a62aa6a4c49eb2b18619dc73300ab6d433cbd78c7d845e8b3e088552",
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_files():
    for entry in LOCK["files"]:
        yield pathlib.Path("BIN") / entry["path"], entry["sha256"]
    for model in LOCK["libraries_by_model"].values():
        for part in model.values():
            yield pathlib.Path("LIB") / part["path"], part["sha256"]


def install_toolchain():
    src = pathlib.Path(os.environ.get("DAVE_TOOLCHAIN_SRC", DEFAULT_TOOLCHAIN_SRC))
    if not (TOOLCHAIN / "BIN" / "TCC.EXE").exists():
        if not src.exists():
            raise SystemExit(f"no toolchain source at {src}; set DAVE_TOOLCHAIN_SRC")
        for sub in ("BIN", "LIB", "INCLUDE"):
            shutil.copytree(src / sub, TOOLCHAIN / sub, dirs_exist_ok=True)
    for rel, digest in pinned_files():
        if sha256(TOOLCHAIN / rel) != digest:
            raise SystemExit(f"toolchain/{rel} does not match its pinned sha256")
    lz_src = pathlib.Path(os.environ.get("DAVE_LZEXE_SRC", "C:/tools/lzexe-0.91/files")) / "LZEXE.EXE"
    lz_dst = TOOLCHAIN / "LZEXE" / "LZEXE.EXE"
    packer = json.loads((ROOT / "layout" / "packer.json").read_text())
    if not lz_dst.exists() and lz_src.exists():
        lz_dst.parent.mkdir(exist_ok=True)
        shutil.copyfile(lz_src, lz_dst)
    if lz_dst.exists() and sha256(lz_dst) != packer["sha256"]:
        raise SystemExit("toolchain/LZEXE/LZEXE.EXE does not match layout/packer.json")
    # TASM for inline-asm compiles (TCC restarts through TASM; tools/tcc.py)
    tasm_src = pathlib.Path(os.environ.get("DAVE_TASM_SRC",
                            "C:/tools/tasm-2.00/files/disk01/expanded/TASM")) / "TASM.EXE"
    tasm_dst = TOOLCHAIN / "TASM20" / "TASM.EXE"
    if not tasm_dst.exists() and tasm_src.exists():
        tasm_dst.parent.mkdir(exist_ok=True)
        shutil.copyfile(tasm_src, tasm_dst)
    if not tasm_dst.exists() or sha256(tasm_dst) != TASM20_SHA256:
        raise SystemExit("toolchain/TASM20/TASM.EXE missing or not TASM 2.0 (set DAVE_TASM_SRC)")
    print("toolchain: ok" + ("" if lz_dst.exists() else " (LZEXE missing: packing tests skip)"))


def install_assets():
    src = pathlib.Path(os.environ.get("DAVE_ASSETS", DEFAULT_ASSETS))
    (ROOT / "assets").mkdir(exist_ok=True)
    for name, digest in ASSET_SHA256.items():
        dst = ROOT / "assets" / name
        if not dst.exists():
            shutil.copyfile(src / name, dst)
        if sha256(dst) != digest:
            raise SystemExit(f"assets/{name} is not the pinned specimen")
    print("assets: ok")


def unpack():
    manifest = json.loads((ROOT / "layout" / "manifest.json").read_text())
    out = ROOT / "build" / "DAVE_unpacked.exe"
    out.parent.mkdir(exist_ok=True)
    if not out.exists():
        subprocess.run([sys.executable, str(ROOT / "tools" / "lzexe_unpack.py"),
                        str(ROOT / "assets" / "DAVE.EXE"), str(out)], check=True)
    if hashlib.md5(out.read_bytes()).hexdigest() != manifest["unpacked_original"]["md5"]:
        raise SystemExit("build/DAVE_unpacked.exe does not match the pinned unpacked image")
    print("unpacked image: ok")


if __name__ == "__main__":
    install_toolchain()
    install_assets()
    unpack()
