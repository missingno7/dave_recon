"""Copy pinned Turbo C++ tools/libraries from a locally supplied installation.

Mirrors empires_reconstruction's tools/setup_toolchain.py. layout/toolchain.json
starts unpinned (sha256: null) until a real installation path is supplied and
its files are hashed for the first time with --pin.

Usage:
    python tools/setup_toolchain.py --from <path-to-BIN-dir> [--lib-from <path-to-LIB-dir>] [--pin]
"""
import argparse
import hashlib
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCK_PATH = ROOT / "layout" / "toolchain.json"
TARGET = ROOT / "toolchain"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="source", type=pathlib.Path, required=True,
                         help="directory containing TCC.EXE / TASM.EXE")
    parser.add_argument("--lib-from", type=pathlib.Path, default=None,
                         help="directory containing CC.LIB; defaults to <source>/../LIB")
    parser.add_argument("--pin", action="store_true",
                         help="write freshly computed sha256 hashes into layout/toolchain.json "
                              "instead of verifying against existing ones (use once, for a trusted install)")
    args = parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text())
    library_dir = args.lib_from or (args.source.parent / "LIB")

    entries = [(entry, args.source / entry["path"]) for entry in lock["files"]]
    entries += [(entry, library_dir / entry["path"]) for entry in lock["libraries"]]

    for entry, source_path in entries:
        if not source_path.exists():
            raise SystemExit(f"missing expected toolchain file: {source_path}")
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if args.pin:
            entry["sha256"] = digest
        elif entry["sha256"] is None:
            raise SystemExit(f"{entry['path']} is unpinned in layout/toolchain.json; rerun with --pin first")
        elif digest != entry["sha256"]:
            raise SystemExit(f"wrong toolchain binary: {source_path} (sha256 {digest} != pinned {entry['sha256']})")

    if args.pin:
        lock["status"] = "pinned"
        LOCK_PATH.write_text(json.dumps(lock, indent=2) + "\n")
        print(f"pinned {len(entries)} toolchain file(s) into {LOCK_PATH.relative_to(ROOT)}")

    TARGET.mkdir(exist_ok=True)
    for entry, source_path in entries:
        shutil.copyfile(source_path, TARGET / entry["path"])
        print(f"installed {entry['path']} -> {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
