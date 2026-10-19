"""Symbol map: names -> addresses in the original image, for fixup verification.

Three sources, in priority order:

1. `layout/symbols.json` -- hand-curated names with evidence:
   {"code": {"_name": {"cs": 0x..., "evidence": "..."}},
    "data": {"_name": {"ds": 0x..., "size": n, "evidence": "..."}}}
2. Library publics derived mechanically: every KNOWN_LIBRARY region in
   layout/manifest.json whose id is LIB_<MODULE>_<HEX> (plus STARTUP_C0S)
   is matched to that module in the pinned CS.LIB / C0S.OBJ, and each of the
   module's _TEXT publics gets address region_start + public_offset.
3. Placeholder names that carry their own address:
     _F_XXXX  -> code at FILE offset 0xXXXX (the census id convention)
     _D_XXXX  -> data at DS offset 0xXXXX
   These let a candidate reference not-yet-named functions/globals while the
   matcher still verifies every reference byte-for-byte.

Segment paragraphs (load-module relative, as patched by MZ relocations):
_TEXT = 0, DGROUP = 0x254D (C0S's `mov dx, DGROUP`, relocation at lm 0x0001).
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import omf  # noqa: E402

HDR = 0x200
DGROUP_PARA = 0x254D
TEXT_PARA = 0x0000
CURATED = ROOT / "layout" / "symbols.json"


class SymbolMap:
    def __init__(self):
        self.code: dict[str, int] = {}     # name -> CS offset
        self.data: dict[str, int] = {}     # name -> DS offset
        self.origin: dict[str, str] = {}
        self._load_library()
        self._load_curated()

    def _load_curated(self):
        if not CURATED.exists():
            return
        doc = json.loads(CURATED.read_text(encoding="utf-8"))
        for name, e in doc.get("code", {}).items():
            self.code[name] = int(e["cs"], 0) if isinstance(e["cs"], str) else e["cs"]
            self.origin[name] = "curated"
        for name, e in doc.get("data", {}).items():
            self.data[name] = int(e["ds"], 0) if isinstance(e["ds"], str) else e["ds"]
            self.origin[name] = "curated"

    def _load_library(self):
        manifest = json.loads((ROOT / "layout" / "manifest.json").read_text())
        lib_path = ROOT / "toolchain" / "LIB" / "CS.LIB"
        c0s_path = ROOT / "toolchain" / "LIB" / "C0S.OBJ"
        if not lib_path.exists():
            return
        reader = omf.OmfReader()
        modules = {name.upper(): blob for name, blob in reader.split_library(lib_path.read_bytes())}
        for region in manifest["regions"]:
            if region["kind"] != "KNOWN_LIBRARY":
                continue
            if region["id"] == "STARTUP_C0S":
                mod = reader.read(c0s_path.read_bytes(), "C0S")
            else:
                m = re.match(r"LIB_(.+)_[0-9A-F]+$", region["id"])
                if not m:
                    continue
                key = m.group(1)
                blob = modules.get(key) or modules.get(key.replace("_", "")) or \
                    next((b for n, b in modules.items() if n.replace("_", "") == key.replace("_", "")), None)
                if blob is None:
                    continue
                mod = reader.read(blob, key)
            for pub in mod.publics:
                if pub["segment"] == "_TEXT":
                    self.code.setdefault(pub["name"], region["start"] - HDR + pub["offset"])
                    self.origin.setdefault(pub["name"], f"library:{region['id']}")

    def resolve_code(self, name: str):
        if name in self.code:
            return self.code[name]
        m = re.fullmatch(r"_F_([0-9A-Fa-f]{4,5})", name)
        if m:
            return int(m.group(1), 16) - HDR
        return None

    def resolve_data(self, name: str):
        if name in self.data:
            return self.data[name]
        m = re.fullmatch(r"_D_([0-9A-Fa-f]{4})", name)
        if m:
            return int(m.group(1), 16)
        return None


if __name__ == "__main__":
    s = SymbolMap()
    for n, a in sorted(s.code.items(), key=lambda kv: kv[1]):
        print(f"code {a:04x} {n:24s} {s.origin.get(n)}")
    for n, a in sorted(s.data.items(), key=lambda kv: kv[1]):
        print(f"data {a:04x} {n:24s} {s.origin.get(n)}")
