"""g_levels decoder/encoder round trip against build/DAVE_unpacked.exe.

Skipped when the unpacked specimen is absent (create it with
`python tools/lzexe_unpack.py assets/DAVE.EXE build/DAVE_unpacked.exe`).
No level data is stored in the repository; everything is re-derived.
"""
import json
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import levels  # noqa: E402

EXE = ROOT / "build" / "DAVE_unpacked.exe"
HAVE = EXE.exists()


@unittest.skipUnless(HAVE, "build/DAVE_unpacked.exe not present")
class LevelsRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe = EXE.read_bytes()
        cls.ds_off, cls.base, cls.stub = levels.find_levels_base(cls.exe)

    def test_base_derived_from_code(self):
        # DGROUP comes from C0S `mov dx,DGROUP`; g_levels from the asm init stub.
        self.assertEqual(levels.dgroup_paragraph(self.exe), 0x254D)
        self.assertEqual(self.ds_off, 0x173A)
        self.assertEqual(self.base, 0x26E0A)
        self.assertEqual(self.stub, 0x8516)

    def test_loader_uses_0x500_stride_and_0x100_tile_offset(self):
        # F_4E69: mov ax,[0x56F4]; mov dx,0x500; imul dx; mov dx,[0x13AC]; add dx,ax
        self.assertEqual(self.exe[0x4EE8:0x4EF6].hex(), "a1f456ba0005f7ea8b16ac1303d0")
        # tiles read at [g_level + si + 0x100], si < 0x3E8
        self.assertEqual(self.exe[0x4F61:0x4F65].hex(), "8a800001")
        self.assertEqual(self.exe[0x503C:0x5040].hex(), "81fee803")
        # neighbour reads at +1 / +0x64 / +0x65 (row stride 100) in F_3FD5
        self.assertEqual(self.exe[0x4056:0x4059].hex(), "8a4764")
        self.assertEqual(self.exe[0x4064:0x4067].hex(), "8a4765")

    def test_levels_fit_in_initialised_data(self):
        end = self.base + levels.NUM_LEVELS * levels.RECORD_SIZE
        self.assertLessEqual(end, len(self.exe))
        # CS.LIB's __atexitcnt (first library _DATA word) sits right after the array
        self.assertEqual(end - (0x254D * 16 + 0x200), 0x493A)

    def test_tiles_are_valid_egadave_fixed_tiles(self):
        for d in levels.decode_levels(self.exe):
            self.assertLessEqual(max(max(r) for r in d["tiles"]), 52, d["level"])

    def test_monster_levels_have_terminated_paths(self):
        # levels with monsters (per-level init table DS:0x496, active flags) end
        # their path with 0xEA; levels 1-2 have no monsters and unread paths.
        ds = 0x254D * 16 + 0x200
        for d in levels.decode_levels(self.exe):
            active = struct.unpack_from("<4H", self.exe, ds + 0x496 + d["index"] * 0x50)
            if any(active):
                self.assertIsNotNone(d["path"]["terminator_hex"], d["level"])

    def test_exact_round_trip_through_json(self):
        decoded = json.loads(json.dumps(levels.decode_levels(self.exe)))
        blob = levels.encode_levels(decoded)
        self.assertEqual(blob, self.exe[self.base:self.base + len(blob)])
        self.assertEqual(levels.patch_exe(self.exe, decoded), self.exe)

    def test_edit_is_localised(self):
        decoded = levels.decode_levels(self.exe)
        decoded[0]["tiles"][5][5] = 0x2F
        patched = levels.patch_exe(self.exe, decoded)
        diff = [i for i in range(len(self.exe)) if patched[i] != self.exe[i]]
        self.assertLessEqual(len(diff), 1)
        if diff:
            self.assertEqual(diff[0], self.base + 0x100 + 5 * 100 + 5)


if __name__ == "__main__":
    unittest.main()
