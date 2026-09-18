import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import coordinates as coord  # noqa: E402


class CoordinateConversionTest(unittest.TestCase):
    def test_file_to_load_module_and_back_roundtrips(self):
        f = coord.FileOffset(0x439)
        lm = f.to_load_module()
        self.assertEqual(lm.value, 0x239)
        self.assertEqual(lm.to_file().value, 0x439)

    def test_offset_inside_header_has_no_load_module_offset(self):
        with self.assertRaises(ValueError):
            coord.FileOffset(0x1FF).to_load_module()

    def test_plain_int_wrappers_match_dataclass_api(self):
        self.assertEqual(coord.file_offset_to_load_module(0x439), 0x239)
        self.assertEqual(coord.load_module_to_file_offset(0x239), 0x439)


class MainEntryPointCoordinateTest(unittest.TestCase):
    """Regression test for the _main coordinate bug: an early pass computed
    file offset 0x639 by (correctly) resolving the call target to 0x439 and
    then (incorrectly) adding the 0x200 MZ header size a second time. These
    numbers are taken directly from build/DAVE_unpacked.exe and must never
    silently drift back to double-counting the header."""

    CALL_OPCODE_FILE_OFFSET = 0x2FC
    CALL_DISP16 = 0x013A
    EXPECTED_TARGET_FILE_OFFSET = 0x439
    EXPECTED_TARGET_LOAD_MODULE_OFFSET = 0x239
    WRONG_DOUBLE_COUNTED_OFFSET = 0x639  # must never be produced again

    def setUp(self):
        self.image = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()

    def test_call_instruction_bytes_match_known_encoding(self):
        # E8 3A 01  =  CALL rel16 +0x013A
        opcode = self.image[self.CALL_OPCODE_FILE_OFFSET]
        disp_bytes = self.image[self.CALL_OPCODE_FILE_OFFSET + 1: self.CALL_OPCODE_FILE_OFFSET + 3]
        self.assertEqual(opcode, 0xE8)
        self.assertEqual(int.from_bytes(disp_bytes, "little"), self.CALL_DISP16)

    def test_call_resolves_to_file_offset_0x439_not_0x639(self):
        target = coord.resolve_self_relative_call(self.CALL_OPCODE_FILE_OFFSET, self.CALL_DISP16)
        self.assertEqual(target.value, self.EXPECTED_TARGET_FILE_OFFSET)
        self.assertNotEqual(target.value, self.WRONG_DOUBLE_COUNTED_OFFSET)

    def test_resolved_target_load_module_offset_is_0x239(self):
        target = coord.resolve_self_relative_call(self.CALL_OPCODE_FILE_OFFSET, self.CALL_DISP16)
        self.assertEqual(target.to_load_module().value, self.EXPECTED_TARGET_LOAD_MODULE_OFFSET)

    def test_bytes_at_resolved_target_are_the_known_main_prologue(self):
        target = self.EXPECTED_TARGET_FILE_OFFSET
        prologue = self.image[target: target + 3]
        # push bp; mov bp, sp
        self.assertEqual(prologue, bytes.fromhex("558bec"))

    def test_double_counted_offset_is_not_a_plausible_function_start(self):
        # The historically-wrong address (0x639) must not itself look like a
        # valid function prologue, as an extra guard against reintroducing
        # the bug and having it look accidentally plausible again.
        misaddressed = self.image[self.WRONG_DOUBLE_COUNTED_OFFSET: self.WRONG_DOUBLE_COUNTED_OFFSET + 3]
        self.assertNotEqual(misaddressed, bytes.fromhex("558bec"))


if __name__ == "__main__":
    unittest.main()
