"""tools/omf_writer.py writes objects that tools/omf.py (and TLINK) read back.

Round trip: segments with data and declared length, a group, publics,
externals and every fixup kind come back unchanged through OmfReader; a
LEDATA longer than one record is split and reassembled.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import omf  # noqa: E402
from omf_writer import OmfWriter, dump  # noqa: E402


class OmfWriterTest(unittest.TestCase):
    def build(self):
        w = OmfWriter("PROBE")
        text = w.segment("_TEXT", "CODE", align="byte", data=bytes(range(16)) * 2)
        data = w.segment("_DATA", "DATA", align="word", data=bytes(3000))
        bss = w.segment("_BSS", "BSS", align="word", length=0x120)
        far = w.segment("BLOB5_FAR", "FAR_DATA", align="para", data=b"\x01\x02\x03")
        w.group("DGROUP", [data, bss])
        w.public(text, "_f", 4)
        w.public(data, "_tab", 0x10)
        w.public(far, "_blob", 0)
        w.fixup(text, 2, "offset16", ("segment", data))
        w.fixup(text, 6, "base16", ("group", 1))
        w.fixup(text, 9, "offset16", ("external", "_g"))
        w.fixup(text, 12, "pointer32", ("segment", far))
        w.fixup(text, 20, "offset16", ("external", "_h"), self_relative=True)
        w.fixup(data, 2050, "offset16", ("segment", data))
        return w.to_bytes()

    def test_round_trip(self):
        mod = omf.OmfReader().read(self.build(), "probe")
        self.assertEqual(mod.segment_bytes("_TEXT"), bytes(range(16)) * 2)
        self.assertEqual(mod.segment_bytes("_DATA"), bytes(3000))
        self.assertEqual(mod.segment_length("_BSS"), 0x120)
        self.assertEqual(mod.segment_bytes("BLOB5_FAR"), b"\x01\x02\x03")
        pubs = {(p["name"], p["segment"], p["offset"]) for p in mod.publics}
        self.assertEqual(pubs, {("_f", "_TEXT", 4), ("_tab", "_DATA", 0x10), ("_blob", "BLOB5_FAR", 0)})
        fx = {(f["segment"], f["offset"], f["loc"], f["target_kind"], f["target"], f["self_relative"])
              for f in mod.fixups}
        self.assertEqual(fx, {
            ("_TEXT", 2, "offset16", "segment", "_DATA", False),
            ("_TEXT", 6, "base16", "group", "DGROUP", False),
            ("_TEXT", 9, "offset16", "external", "_g", False),
            ("_TEXT", 12, "pointer32", "segment", "BLOB5_FAR", False),
            ("_TEXT", 20, "offset16", "external", "_h", True),
            ("_DATA", 2050, "offset16", "segment", "_DATA", False),
        })

    def test_dump_lists_segdefs(self):
        text = "\n".join(dump(self.build()))
        self.assertIn("SEGDEF BLOB5_FAR    class FAR_DATA   para  public  len 0x0003", text)
        self.assertIn("GRPDEF DGROUP = _DATA, _BSS", text)


if __name__ == "__main__":
    unittest.main()
