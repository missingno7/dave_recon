import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_probe  # noqa: E402


class StackCheckFlagTest(unittest.TestCase):
    """Confirms -N (stack overflow checking ON) matches the real game's
    _main prologue, per docs/flag-investigation.md."""

    def _compiled_text(self, flags):
        if not (ROOT / "toolchain" / "BIN" / "TCC.EXE").exists():
            self.skipTest("toolchain not installed locally")
        obj_path = compile_probe.run(ROOT / "tests" / "fixtures" / "probe2.c", "s", flags)
        import omf
        mod = omf.OmfReader().read(obj_path.read_bytes(), "probe2")
        return mod.segments["_TEXT"]

    def test_dash_N_emits_stack_check_stub_matching_real_main(self):
        code = self._compiled_text("-N")
        # push bp; mov bp,sp; sub sp,0x1a; cmp word ptr [fixup],sp; jb +3; call
        self.assertEqual(code[0:3], bytes.fromhex("558bec"))
        self.assertEqual(code[3:6], bytes.fromhex("83ec1a"))
        self.assertEqual(code[6:8], bytes.fromhex("3926"))  # cmp [xxxx],sp opcode+modrm
        self.assertEqual(code[10:12], bytes.fromhex("7203"))  # jb +3
        self.assertEqual(code[12], 0xE8)  # call

    def test_dash_N_dash_omits_stack_check_stub(self):
        code = self._compiled_text("-N-")
        self.assertEqual(code[0:6], bytes.fromhex("558bec83ec1a"))
        # No cmp/jb/call stack-check triplet: next bytes go straight to the
        # function body (mov ax,[bp+4] = 8B 46 04), not 39 26.
        self.assertNotEqual(code[6:8], bytes.fromhex("3926"))

    def test_real_main_prologue_matches_dash_N_structure(self):
        image = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()
        main_bytes = image[0x439:0x439 + 9]
        # push bp; mov bp,sp; cmp [fixup],sp; jb +3; call  (no sub sp: main has no locals)
        self.assertEqual(main_bytes[0:3], bytes.fromhex("558bec"))
        self.assertEqual(main_bytes[3:5], bytes.fromhex("3926"))
        self.assertEqual(main_bytes[7:9], bytes.fromhex("7203"))


if __name__ == "__main__":
    unittest.main()
