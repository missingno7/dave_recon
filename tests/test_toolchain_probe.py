import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_probe  # noqa: E402
import omf  # noqa: E402


class ToolchainProbeTest(unittest.TestCase):
    """Confirms the pinned Turbo C++ toolchain self-identifies as TC 1.00,
    matching the runtime string embedded in build/DAVE_unpacked.exe."""

    def test_compiler_self_identifies_as_turbo_cpp_1_00(self):
        toolchain = json.loads((ROOT / "layout" / "toolchain.json").read_text())
        if toolchain.get("status") != "pinned":
            self.skipTest("toolchain not pinned locally")

        # -N- (stack checking off) isolates this test from the flag-
        # investigation default (-N, see docs/flag-investigation.md) so it
        # only asserts compiler identity, not codegen flag behavior.
        obj_path = compile_probe.run(ROOT / "tests" / "fixtures" / "probe1.c", "s", "-N-")
        data = obj_path.read_bytes()

        # THEADR (0x80) record: length-prefixed name, then a COMENT (0x88)
        # record containing the compiler's self-identification string.
        self.assertIn(b"Borland Turbo C++ 1.00", data)

        mod = omf.OmfReader().read(data, "probe1")
        self.assertEqual(mod.segment_lengths["_TEXT"], 13)
        self.assertEqual(mod.publics, [{"name": "_add", "segment": "_TEXT", "offset": 0}])


if __name__ == "__main__":
    unittest.main()
