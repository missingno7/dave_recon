"""Pure helpers of the oracle and the route planner (no emulator needed)."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import oracle  # noqa: E402
import route  # noqa: E402


class RouteHelpers(unittest.TestCase):
    def test_keyboard_reader(self):
        # default bindings: Up 0x48, PgUp 0x49, Right 0x4D, Left 0x4B, Ctrl, Alt
        self.assertEqual(route.input_of([0x4D]), (route.E, 0, 0))
        self.assertEqual(route.input_of([0x48, 0x4D]), (route.NE, 0, 0))
        self.assertEqual(route.input_of([0x49, 0x4B]), (route.NE, 0, 0))   # a diagonal key wins
        self.assertEqual(route.input_of([0x1D, 0x38]), (route.NONE, 1, 1))

    @unittest.skipUnless((ROOT / "build" / "DAVE_unpacked.exe").exists(), "needs tools/bootstrap.py")
    def test_demo_lengths(self):
        # one tick per input byte, `0x20 n` = n + 1 idle ticks (UNDERSTANDING_LEDGER)
        self.assertEqual([len(route.demo_inputs(i)) for i in range(5)], [2324, 1176, 818, 583, 1300])

    def test_parse_moves(self):
        self.assertEqual(route.parse_moves("2x2 1/j 8"), [(2, 0, 0), (2, 0, 0), (1, 0, 1), (8, 0, 0)])

    def test_plan_events_wait_key(self):
        # a wait that the input does not end gets its key half a retrace before
        # the poll, and the key stays held into the next tick
        res = [{"retraces": 21, "first_poll": 20}, {"retraces": 1, "first_poll": -1},
               {"retraces": 1, "first_poll": -1}]
        ev, heads = route.plan_events(1000.0, 10.0, [(8, 0, 0)] * 3, res)
        self.assertEqual(ev, [(1195, "keydown", "right"), (1215, "keyup", "right")])
        self.assertEqual(heads, [1000.0, 1210.0, 1220.0, 1230.0])


class OracleHelpers(unittest.TestCase):
    def test_bios_pending(self):
        buf = bytearray(0x24)
        buf[0:2] = (0x1E).to_bytes(2, "little")      # head
        buf[2:4] = (0x22).to_bytes(2, "little")      # tail: two keys
        buf[4:6] = (0x4DE0).to_bytes(2, "little")
        buf[6:8] = (0x1E61).to_bytes(2, "little")
        self.assertEqual(oracle.bios_pending(bytes(buf)), [0x4DE0, 0x1E61])
        self.assertEqual(oracle.bios_pending(b""), [])

    def test_draw_routines_table(self):
        names = [r[0] for r in oracle.DRAW_ROUTINES]
        self.assertEqual(len(names), len(set(names)))
        for name, lo, hi, nargs, op, extra in oracle.DRAW_ROUTINES:
            self.assertLess(lo, hi, name)
            self.assertLessEqual(nargs, 5, name)       # ss:sp dump: return address + 5 words
        ops = {r[4] for r in oracle.DRAW_ROUTINES if r[4]}
        self.assertTrue({"DRAW_TILE", "DRAW_XOR_SPRITE", "DRAW_DAVE", "DRAW_PRINT_STRING"} <= ops)


if __name__ == "__main__":
    unittest.main()
