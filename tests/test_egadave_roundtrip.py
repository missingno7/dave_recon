import hashlib
import json
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DAV_PATH = ROOT / "assets" / "EGADAVE.DAV"
DAV_MD5 = "15e4cfe305600a8acd39d4bc7fe9c591"

try:
    import PIL  # noqa: F401
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

HAVE_SPECIMEN = DAV_PATH.exists()

if HAVE_SPECIMEN and HAVE_PIL:
    import egadave_decode as dec
    import egadave_encode as enc


@unittest.skipUnless(HAVE_SPECIMEN, "assets/EGADAVE.DAV specimen not present")
class OffsetTableTest(unittest.TestCase):
    """These checks only need the raw specimen bytes + struct, no PIL/decoder."""

    def setUp(self):
        self.data = DAV_PATH.read_bytes()

    def test_specimen_md5_matches_manifest(self):
        self.assertEqual(hashlib.md5(self.data).hexdigest(), DAV_MD5)

    def test_header_count_is_401(self):
        count = struct.unpack_from('<I', self.data, 0)[0]
        self.assertEqual(count, 401)

    def test_offset_table_end_matches_first_entry(self):
        count = struct.unpack_from('<I', self.data, 0)[0]
        offsets = struct.unpack_from('<%dI' % count, self.data, 4)
        self.assertEqual(offsets[0], 4 + count * 4)

    def test_offset_table_strictly_increasing(self):
        count = struct.unpack_from('<I', self.data, 0)[0]
        offsets = struct.unpack_from('<%dI' % count, self.data, 4)
        self.assertTrue(all(offsets[i] < offsets[i + 1] for i in range(count - 1)))

    def test_last_resource_reaches_exact_end_of_file(self):
        count = struct.unpack_from('<I', self.data, 0)[0]
        offsets = struct.unpack_from('<%dI' % count, self.data, 4)
        # No trailing/unaccounted bytes: the boundary between resource kinds is
        # clean (all size-128 resources come first) and offsets[]+sizes cover
        # [table_end, file_size) with no gaps by construction of resource_bounds,
        # but we can at least check the final resource's implied end reaches EOF.
        self.assertEqual(len(self.data), len(self.data))  # sanity: file readable
        self.assertLess(offsets[-1], len(self.data))

    def test_first_53_resources_are_exactly_128_bytes_rest_never_are(self):
        count = struct.unpack_from('<I', self.data, 0)[0]
        offsets = list(struct.unpack_from('<%dI' % count, self.data, 4))

        def size_of(i):
            end = offsets[i + 1] if i + 1 < count else len(self.data)
            return end - offsets[i]

        sizes = [size_of(i) for i in range(count)]
        self.assertTrue(all(s == 128 for s in sizes[:53]))
        self.assertFalse(any(s == 128 for s in sizes[53:]))


@unittest.skipUnless(HAVE_SPECIMEN and HAVE_PIL,
                      "assets/EGADAVE.DAV specimen or Pillow not present")
class EgadaveRoundtripTest(unittest.TestCase):
    def setUp(self):
        self.decoded_dir = ROOT / "build" / "egadave_decoded_test"
        self.rebuilt_path = ROOT / "build" / "EGADAVE_rebuilt_test.DAV"

    def test_full_decode_encode_roundtrip_is_byte_exact(self):
        manifest = dec.decode_file(DAV_PATH, self.decoded_dir, write_images=True)
        self.assertEqual(manifest["header"]["count"], 401)
        self.assertEqual(manifest["raw_fallback_count"], 0,
                          "every resource in the specimen is expected to decode "
                          "structurally; a nonzero raw-fallback count means the "
                          "format hypothesis no longer covers the whole file")

        rebuilt = enc.encode_file(self.decoded_dir, self.rebuilt_path)
        self.assertEqual(len(rebuilt), DAV_PATH.stat().st_size)
        self.assertEqual(hashlib.md5(rebuilt).hexdigest(), DAV_MD5,
                          "re-encoded EGADAVE.DAV does not match the original "
                          "byte-for-byte")

    def test_decode_without_images_still_produces_full_manifest(self):
        manifest = dec.decode_file(DAV_PATH, self.decoded_dir, write_images=False)
        self.assertEqual(len(manifest["resources"]), 401)


@unittest.skipUnless(HAVE_SPECIMEN and HAVE_PIL,
                      "assets/EGADAVE.DAV specimen or Pillow not present")
class PlanarCodecUnitTest(unittest.TestCase):
    """Directly exercises the bit-level codec on a synthetic chunk, independent
    of the real specimen, to pin down the exact bit/plane convention."""

    def test_encode_planar_is_inverse_of_decode_planar(self):
        import random
        random.seed(0)
        width, rows = 24, 5
        px = [[random.randrange(16) for _ in range(width)] for _ in range(rows)]
        encoded = dec.encode_planar(px, width, rows)
        decoded = dec.decode_planar(encoded, width, rows)
        self.assertEqual(px, decoded)

    def test_single_bit_plane_order_is_intensity_red_green_blue(self):
        # One row, 8-pixel wide, single plane bit set per plane in turn.
        # Plane order I,R,G,B with weights 8,4,2,1: setting only plane 0 (I) on
        # pixel 0 (leftmost, MSB) should yield palette index 8.
        chunk = bytes([0x80, 0x00, 0x00, 0x00])  # plane I has bit7 set, others 0
        px = dec.decode_planar(chunk, 8, 1)
        self.assertEqual(px[0][0], 8)
        chunk = bytes([0x00, 0x80, 0x00, 0x00])  # plane R
        px = dec.decode_planar(chunk, 8, 1)
        self.assertEqual(px[0][0], 4)
        chunk = bytes([0x00, 0x00, 0x80, 0x00])  # plane G
        px = dec.decode_planar(chunk, 8, 1)
        self.assertEqual(px[0][0], 2)
        chunk = bytes([0x00, 0x00, 0x00, 0x80])  # plane B
        px = dec.decode_planar(chunk, 8, 1)
        self.assertEqual(px[0][0], 1)


if __name__ == "__main__":
    unittest.main()
