"""RLE tilesets (far segments 0x0C42 / 0x11EF): the game's own encoder (0x7F41)
reproduces both compressed streams exactly; PNG + JSON round trip; edit locality.

Skipped when build/DAVE_unpacked.exe is absent (python tools/bootstrap.py).
Decodes into a temporary directory; no graphics are stored in the repository.
"""
import json
import pathlib
import random
import struct
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import far_data  # noqa: E402
import pixels  # noqa: E402
import rle  # noqa: E402
import tilesets  # noqa: E402

EXE = ROOT / "build" / "DAVE_unpacked.exe"


class RleCodecTest(unittest.TestCase):
    def test_encoder_decoder_inverse_below_ff00(self):
        rnd = random.Random(7)
        for n in (1, 2, 3, 5, 130, 131, 300, 4000):
            src = bytes(rnd.choice(b"\0\0\0\x01\x02") for _ in range(n)) + bytes(260)
            got = rle.encode(src, n)
            out, _ = rle.decode(got["stream"], got["read"])
            self.assertEqual(out[:got["read"]], src[:got["read"]], n)
            self.assertGreaterEqual(got["read"], n + 1)   # always one byte past the buffer

    def test_renormalisation_duplicates_byte_ff00(self):
        src = bytes(range(256)) * 0x101 + bytes(16)
        got = rle.encode(src, 0x10010)
        self.assertEqual(got["normalised_at"], [0xFF00])
        out, _ = rle.decode(got["stream"], 0x10012)
        self.assertEqual(out[:0xFF01], src[:0xFF01])
        self.assertEqual(out[0xFF01], src[0xFF00])           # re-emitted
        self.assertEqual(out[0xFF02:0x10012], src[0xFF01:0x10011])

    @unittest.skipUnless(EXE.exists(), "build/DAVE_unpacked.exe not present")
    def test_codec_bytes_in_exe(self):
        exe = EXE.read_bytes()
        # decoder: lodsb; cmp al,0x80; jb run; sub al,0x7F (literal) ... add al,3 (run)
        self.assertEqual(exe[0x7F24:0x7F2B].hex(), "ac3c80720b2c7f")
        self.assertEqual(exe[0x7F34:0x7F36].hex(), "0403")
        # encoder: run byte = run-2 (0x7E65), literal byte = n+0x7F (0x7EA0), max literal 0x7E
        self.assertEqual(exe[0x7E65:0x7E67].hex(), "2c02")
        self.assertEqual(exe[0x7EA0:0x7EA2].hex(), "047f")
        self.assertEqual(exe[0x800D:0x8013].hex(), "36833ea7137e")


@unittest.skipUnless(EXE.exists(), "build/DAVE_unpacked.exe not present")
class TilesetsRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe = EXE.read_bytes()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dirs, cls.json, cls.blobs = {}, {}, {}
        for mode in tilesets.MODES:
            out = pathlib.Path(cls.tmp.name) / mode
            tilesets.materialise(mode, out, EXE)
            cls.dirs[mode] = out
            cls.json[mode] = json.loads((out / "tileset.json").read_text())
            cls.blobs[mode] = far_data.segment_bytes(cls.exe, f"tileset_{mode}")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_segments_from_relocations(self):
        segs = {s["name"]: (s["paragraph"], s["start"], s["end"]) for s in far_data.far_segments(self.exe)}
        self.assertEqual(segs["tileset_cga"], (0x0C42, 0xC620, 0x120F0))
        self.assertEqual(segs["tileset_vga"], (0x11EF, 0x120F0, 0x1C4E0))

    def test_format(self):
        cga, vga = self.json["cga"], self.json["vga"]
        self.assertEqual((len(cga["resources"]), cga["fixed_tiles"]), (239, 53))
        self.assertEqual((len(vga["resources"]), vga["fixed_tiles"]), (158, 53))
        self.assertEqual(cga["rle"]["overread_hex"], "9a")
        self.assertEqual(len(bytes.fromhex(vga["rle"]["overread_hex"])), 22)
        self.assertEqual(cga["rle"]["duplicated_source_bytes"], [])
        self.assertEqual(vga["rle"]["duplicated_source_bytes"], [0xFF00])
        self.assertEqual((cga["segment_padding_zero_bytes"], vga["segment_padding_zero_bytes"]), (11, 3))

    def test_header_length_is_the_encoder_count(self):
        for mode in tilesets.MODES:
            parts = tilesets.split_segment(self.blobs[mode])
            self.assertEqual(struct.unpack_from("<I", self.blobs[mode])[0], len(parts["tileset"]))

    def test_exact_round_trip(self):
        for mode in tilesets.MODES:
            self.assertEqual(tilesets.encode(self.json[mode], self.dirs[mode]), self.blobs[mode], mode)

    def test_game_view_is_the_decoder_output(self):
        # What the game's decoder produces equals our tileset, except for the
        # VGA byte duplicated by the encoder's 0xFF00 renormalisation.
        for mode in tilesets.MODES:
            tileset = tilesets.encode_tileset(self.json[mode]["resources"], mode, self.dirs[mode])
            game, _ = rle.decode(self.blobs[mode][4:], len(tileset))
            game = game[:len(tileset)]
            if mode == "cga":
                self.assertEqual(game, tileset)
            else:
                self.assertEqual(game, tileset[:0xFF01] + tileset[0xFF00:-1])

    def test_tile_pixel_edit(self):
        mode = "cga"
        d = self.json[mode]
        r = d["resources"][10]
        path = self.dirs[mode] / r["file"]
        orig = path.read_bytes()
        before = tilesets.encode_tileset(d["resources"], mode, self.dirs[mode])
        px = pixels.read_png(path, 16, 16)
        px[5][6] ^= 3
        pixels.write_png(px, path, pixels.CGA_PALETTE)
        try:
            after = tilesets.encode_tileset(d["resources"], mode, self.dirs[mode])
            seg = tilesets.encode(d, self.dirs[mode])
        finally:
            path.write_bytes(orig)
        off = struct.unpack_from("<I", before, 4 + 4 * 10)[0]
        self.assertEqual([i for i in range(len(after)) if after[i] != before[i]], [off + 5 * 4 + 1])
        # the recompressed segment decodes, with the game's decoder, to the edited tileset
        game, _ = rle.decode(seg[4:], len(after))
        self.assertEqual(game[:len(after)], after)


if __name__ == "__main__":
    unittest.main()
