import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import recover_startup_binding as rsb  # noqa: E402


class StartupLibraryTest(unittest.TestCase):
    """Confirms the C0S.OBJ (small model) startup module is the unique exact
    (modulo fixups) match for the game's entry point, and that no other
    memory model's startup object matches as well."""

    def test_small_model_is_unique_exact_match(self):
        if not (ROOT / "toolchain" / "LIB" / "C0S.OBJ").exists():
            self.skipTest("toolchain not installed locally")
        image = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()
        load_module = image[512:]

        results = {}
        for model, fname in rsb.MODELS:
            results[model] = rsb.compare(load_module, ROOT / "toolchain" / "LIB" / fname)

        winners = [m for m, r in results.items() if r["exact_match_modulo_fixups"]]
        self.assertEqual(winners, ["small"])
        self.assertEqual(results["small"]["unexplained_diffs"], [])


if __name__ == "__main__":
    unittest.main()
