"""Runs the Turbo C++ 1.00 codegen catalog (tools/codegen_lab/run.py).

Every case in tools/codegen_lab/cases/ is compiled (all in one DOSBox-X
session) with the recommended flag line and checked against its stated
expectation: real-function cases must reproduce their range of
build/DAVE_unpacked.exe modulo fixups, probe cases their recorded bytes, and
every @contrast flag must break the expectation. Skipped when the toolchain
or DOSBox-X is not installed.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "codegen_lab"))

import tcc_batch  # noqa: E402
import bss_order  # noqa: E402


class CodegenCatalogTest(unittest.TestCase):
    def test_all_cases(self):
        if not tcc_batch.toolchain_available():
            self.skipTest("toolchain/DOSBox-X not installed (run tools/bootstrap.py)")
        if not (ROOT / "build" / "DAVE_unpacked.exe").exists():
            self.skipTest("build/DAVE_unpacked.exe missing (run tools/bootstrap.py)")
        import run as catalog
        cases = catalog.load_cases()
        self.assertGreater(len(cases), 0)
        report, _ = catalog.run(cases)
        failures = {name: errs for name, errs in report if errs}
        self.assertEqual(failures, {}, "codegen catalog cases failed")


class BssOrderKeyTest(unittest.TestCase):
    """Pure-python checks of the fitted _BSS sort key (no toolchain needed)."""

    def test_known_keys(self):
        self.assertEqual(bss_order.bss_key("a"), 97)
        self.assertEqual(bss_order.bss_key("count"), 19)
        self.assertEqual(bss_order.bss_key("tie_a"), bss_order.bss_key("tie_z"))

    def test_layout_aligns_non_char(self):
        lay = bss_order.bss_layout([("c_two", 1, True), ("c_one", 1, True), ("tie_c", 2, False)])
        self.assertEqual([(o, n) for o, n, _ in lay], [(0, "c_one"), (1, "c_two"), (2, "tie_c")])


if __name__ == "__main__":
    unittest.main()
