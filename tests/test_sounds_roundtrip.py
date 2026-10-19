"""SPK sound bank (far segment 0x1C2E) decode/encode round trip and edit locality.

Skipped when build/DAVE_unpacked.exe is absent (python tools/bootstrap.py).
No sound data is stored in the repository; everything is re-derived.
"""
import json
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import far_data  # noqa: E402
import sounds  # noqa: E402

EXE = ROOT / "build" / "DAVE_unpacked.exe"


@unittest.skipUnless(EXE.exists(), "build/DAVE_unpacked.exe not present")
class SoundsRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe = EXE.read_bytes()
        cls.seg = far_data.segment(cls.exe, "sounds")
        cls.blob = cls.exe[cls.seg["start"]:cls.seg["end"]]
        cls.d = json.loads(json.dumps(sounds.decode(cls.blob)))

    def test_segment_from_relocations(self):
        self.assertEqual((self.seg["paragraph"], self.seg["start"], self.seg["end"]),
                         (0x1C2E, 0x1C4E0, 0x1D780))
        # F_519B: g_sound_data = MK_FP(0x1C2E,0) -- `mov ax,0x1C2E` at lm 0x4FDD is relocated
        self.assertIn(0x4FDD, far_data.levels.relocation_sites(self.exe))

    def test_format(self):
        self.assertEqual(len(self.d["sounds"]), 63)
        named = [s["name"] for s in self.d["sounds"] if s["name"] != "->UNUSED<-"]
        self.assertEqual(len(named), 12)
        self.assertEqual(self.d["sounds"][6]["name"], "GotTrophy")   # play_sound(7) on the trophy
        self.assertEqual(self.d["segment_padding_zero_bytes"], 12)
        self.assertEqual(struct.unpack_from("<I", self.blob, 4)[0], 4756)

    def test_exact_round_trip(self):
        self.assertEqual(sounds.encode(self.d), self.blob)

    def test_generator_matches(self):
        self.assertEqual(sounds.generate(), self.blob)

    def test_divisor_edit_is_localised(self):
        d = json.loads(json.dumps(self.d))
        k = 3
        old = d["sounds"][6]["divisors"][k]
        d["sounds"][6]["divisors"][k] = old ^ 0x0101
        new = sounds.encode(d)
        data_off = struct.unpack_from("<H", self.blob, 0x10 + 6 * 16)[0]
        diff = [i for i in range(len(new)) if new[i] != self.blob[i]]
        self.assertEqual(diff, [data_off + 2 * k, data_off + 2 * k + 1])

    def test_priority_edit_is_localised(self):
        d = json.loads(json.dumps(self.d))
        d["sounds"][1]["priority"] += 1
        new = sounds.encode(d)
        self.assertEqual([i for i in range(len(new)) if new[i] != self.blob[i]], [0x10 + 16 + 2])


if __name__ == "__main__":
    unittest.main()
