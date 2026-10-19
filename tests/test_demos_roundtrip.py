"""Attract-mode demos (far segment 0x0B31) decode/encode round trip and edit locality.

Skipped when build/DAVE_unpacked.exe is absent (python tools/bootstrap.py).
"""
import json
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import demos  # noqa: E402
import far_data  # noqa: E402

EXE = ROOT / "build" / "DAVE_unpacked.exe"


@unittest.skipUnless(EXE.exists(), "build/DAVE_unpacked.exe not present")
class DemosRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe = EXE.read_bytes()
        cls.seg = far_data.segment(cls.exe, "demos")
        cls.blob = cls.exe[cls.seg["start"]:cls.seg["end"]]
        cls.d = json.loads(json.dumps(demos.decode(cls.blob)))
        cls.offsets = struct.unpack_from("<5I", cls.blob, 4)

    def test_segment_from_relocations(self):
        self.assertEqual((self.seg["paragraph"], self.seg["start"], self.seg["end"]),
                         (0x0B31, 0xB510, 0xC620))

    def test_reader_code(self):
        # F_4A27: cmp byte es:[bx],0x20 ... cmp byte es:[bx],0x30; and ax,0xF (direction)
        self.assertEqual(self.exe[0x4A71:0x4A75].hex(), "26803f20")
        self.assertEqual(self.exe[0x4A97:0x4A9B].hex(), "26803f30")
        self.assertEqual(self.exe[0x4AC1:0x4AC4].hex(), "250f00")

    def test_format(self):
        self.assertEqual(len(self.d["demos"]), 5)
        self.assertEqual([x["start_level_index"] for x in self.d["demos"]], [2, 1, 3, 8, 4])
        self.assertEqual(self.d["segment_padding_zero_bytes"], 10)
        for x in self.d["demos"]:
            self.assertEqual(len(bytes.fromhex(x["unread_after_end_hex"])), 1)

    def test_exact_round_trip(self):
        self.assertEqual(demos.encode(self.d), self.blob)

    def test_generator_matches(self):
        self.assertEqual(demos.generate(), self.blob)

    def test_start_level_edit_is_localised(self):
        d = json.loads(json.dumps(self.d))
        d["demos"][2]["start_level_index"] = 9
        new = demos.encode(d)
        self.assertEqual([i for i in range(len(new)) if new[i] != self.blob[i]], [self.offsets[2]])

    def test_event_edit_is_localised(self):
        d = json.loads(json.dumps(self.d))
        ev = d["demos"][0]["events"]
        k = ev.index("E x15")
        start = self.offsets[0] + 1 + len(demos.encode_stream(ev[:k])) - 1   # minus the 0x30
        ev[k] = "W+alt x15"
        new = demos.encode(d)
        diff = [i for i in range(len(new)) if new[i] != self.blob[i]]
        self.assertEqual(diff, list(range(start, start + 15)))
        self.assertTrue(all(new[i] == 0x46 for i in diff))   # W = 6, button 2 = bit 6


if __name__ == "__main__":
    unittest.main()
