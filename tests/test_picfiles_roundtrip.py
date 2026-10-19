"""Config-screen picfiles (far segments 0x1D58/0x1E84/0x20CC): PNG + JSON round trip.

Skipped when build/DAVE_unpacked.exe is absent (python tools/bootstrap.py).
Decodes into a temporary directory; no graphics are stored in the repository.
"""
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import far_data  # noqa: E402
import picfiles  # noqa: E402
import pixels  # noqa: E402

EXE = ROOT / "build" / "DAVE_unpacked.exe"


@unittest.skipUnless(EXE.exists(), "build/DAVE_unpacked.exe not present")
class PicfilesRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe = EXE.read_bytes()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dirs, cls.json, cls.blobs = {}, {}, {}
        for mode in picfiles.MODES:
            out = pathlib.Path(cls.tmp.name) / mode
            picfiles.materialise(mode, out, EXE)
            cls.dirs[mode] = out
            cls.json[mode] = json.loads((out / "picfile.json").read_text())
            cls.blobs[mode] = far_data.segment_bytes(cls.exe, f"picfile_{mode}")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_segments_from_relocations(self):
        segs = {s["name"]: (s["paragraph"], s["end"] - s["start"]) for s in far_data.far_segments(self.exe)}
        self.assertEqual(segs["picfile_cga"], (0x1D58, 4800))
        self.assertEqual(segs["picfile_ega"], (0x1E84, 9344))
        self.assertEqual(segs["picfile_vga"], (0x20CC, 18432))

    def test_format(self):
        for mode, d in self.json.items():
            self.assertEqual(d["font"]["chars"], 128, mode)
            self.assertEqual([p["name"] for p in d["pictures"]],
                             ["CGA", "EGA", "VGA", "noEGA", "noVGA", "nosound", "SPKR", "kbd",
                              "joy1", "joy2", "mouse", "nojoy", "nomouse"], mode)
            self.assertTrue(all(p["height"] == 24 for p in d["pictures"]))
        self.assertEqual(self.json["ega"]["header"]["charptr"], "A200:0000")   # EGA VRAM
        self.assertEqual(self.json["ega"]["planes_in_file"], 4)

    def test_exact_round_trip(self):
        for mode in picfiles.MODES:
            self.assertEqual(picfiles.encode(self.json[mode], self.dirs[mode]), self.blobs[mode], mode)

    def _edit_pixel(self, mode, pic, x, y, value):
        d = self.json[mode]
        e = d["pictures"][pic]
        m = picfiles.MODES[mode]
        w = e["width_bytes"] * 8 // m["bpp"]
        path = self.dirs[mode] / e["file"]
        orig = path.read_bytes()
        px = pixels.read_png(path, w, e["height"])
        old = px[y][x]
        px[y][x] = value
        pal = pixels.CGA_PALETTE if mode == "cga" else pixels.ega_palette()
        pixels.write_png(px, path, pal)
        try:
            new = picfiles.encode(d, self.dirs[mode])
        finally:
            path.write_bytes(orig)
        return old, [i for i in range(len(new)) if new[i] != self.blobs[mode][i]]

    def test_vga_pixel_edit_is_one_byte(self):
        d = self.json["vga"]
        old, diff = self._edit_pixel("vga", 5, 3, 7, 0)
        if old == 0:
            old, diff = self._edit_pixel("vga", 5, 3, 7, 1)
        pics_at = 0x100 + 128 * 64
        self.assertEqual(diff, [pics_at + 5 * 32 * 24 + 7 * 32 + 3])

    def test_ega_pixel_edit_touches_one_plane(self):
        # flip bit 2 (red) of pixel (9, 4) of picture 6: only plane 2 changes
        e = self.json["ega"]["pictures"][6]
        path = self.dirs["ega"] / e["file"]
        old = pixels.read_png(path, 32, 24)[4][9]
        _, diff = self._edit_pixel("ega", 6, 9, 4, old ^ 4)
        plane = 0x8E * 16
        self.assertEqual(diff, [0x100 + 2 * plane + 1024 + 6 * 4 * 24 + 4 * 4 + 1])


if __name__ == "__main__":
    unittest.main()
