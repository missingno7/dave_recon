"""The semantic inventory (PORT_ROADMAP M2.1) is current, complete and consistent.

tools/semantic_inventory.py --check regenerates docs/semantic-inventory.{json,md}
and fails if they are stale or if a mechanical cross-check fails (the
source-derived call graph against the binary call graph, the source headers'
addresses against the census, every DGROUP reference of the binary sweep
covered by a data entry, the BSS holes unreferenced). The tests below add the
completeness and status rules.
"""
import json
import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import semantic_inventory as si  # noqa: E402


class SemanticInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = si.build()
        cls.entries = cls.doc["entries"]
        cls.by_id = {e["id"]: e for e in cls.entries}

    def test_check_passes(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "semantic_inventory.py"), "--check"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_counts(self):
        kinds = [e["kind"] for e in self.entries]
        self.assertEqual(kinds.count("c_function"), 90)
        self.assertEqual(kinds.count("asm_procedure"), 60)
        self.assertEqual(kinds.count("far_data"), 7)

    def test_every_declared_object_has_an_entry(self):
        header = (ROOT / "src" / "DAVE.H").read_text(encoding="latin-1")
        for m in re.finditer(r"^extern\s+.*?(\w+)\s*(?:\[[^\]]*\])*\)?\(?\)?;", header, re.M):
            self.assertIn("data:" + m.group(1), self.by_id, m.group(0))
        bss = json.loads((ROOT / "layout" / "bss-map.json").read_text())
        for u in bss["units"]:
            for e in u["entries"]:
                if e["kind"] == "variable":
                    ent = self.by_id["data:" + e["name"]]
                    self.assertEqual(int(ent["identity"]["ds"], 16), e["ds"], e["name"])
                    self.assertEqual(ent["identity"]["size"], e["size"], e["name"])

    def test_statuses_and_roles(self):
        for e in self.entries:
            self.assertIn(e["status"], si.STATUSES, e["id"])
            self.assertTrue(e["purpose"] and e["purpose"] != "TODO", e["id"])
            self.assertTrue(e["evidence"], e["id"])
            if e["kind"] in ("global", "far_data"):
                self.assertIn(e["role"], si.ROLES, e["id"])

    def test_understood_needs_evidence_beyond_the_definition(self):
        """`understood` code is exact recovered source plus an explanation; an
        understood data object is either used (mechanical readers/writers) or
        explained as dead / padding / runtime."""
        for e in self.entries:
            if e["status"] != "understood":
                continue
            if e["kind"] in ("c_function", "asm_procedure"):
                self.assertTrue(any(x.startswith("EXACT") for x in e["evidence"]), e["id"])
            elif e["kind"] == "global":
                r = e["relations"]
                used = r["readers"] or r["writers"] or r["written_through_pointer_by"] or r["address_taken_by"]
                inert = e["role"] in ("runtime", "layout_artifact") or e["identity"]["type"] == "padding" \
                    or e["identity"]["type"] == "string pool" or "image" in e["name"]
                self.assertTrue(used or inert or e["name"] in ("g_levels", "g_vga_palette"), e["id"])

    def test_unreachable_code_is_marked_dead(self):
        for e in self.entries:
            if e["kind"] in ("c_function", "asm_procedure") and not e["reachable"]:
                self.assertFalse(e["relations"]["callers"] and any(
                    self.by_id.get("c:" + c, self.by_id.get("asm:" + c, {})).get("reachable")
                    for c in e["relations"]["callers"]), e["id"])
                self.assertTrue(any("unreachable" in x or "Dead" in e["purpose"] or "dead" in x.lower()
                                    for x in e["evidence"]) or "Dead" in e["purpose"], e["id"])

    def test_known_relations(self):
        """Spot checks of the mechanical relations against facts read from the code."""
        r = self.by_id["data:g_dave_state"]["relations"]
        self.assertEqual(set(r["writers"]), {"check_collisions", "check_warp_transition", "handle_death",
                                             "load_level", "move_dave", "process_input", "update_jetpack"})
        self.assertIn("move_dave", self.by_id["c:main"]["relations"]["callees"])
        self.assertIn("WaitVBL", self.by_id["c:move_dave"]["relations"]["callees"])
        self.assertEqual(self.by_id["data:g_actors"]["relations"]["fields"]["type"]["readers"], [])
        self.assertEqual(self.by_id["data:g_demo_recording"]["relations"]["writers"], [])
        self.assertIn("pick_up_items", self.by_id["data:g_level"]["relations"]["written_through_pointer_by"])
        self.assertIn("DrawLevelView", self.by_id["data:g_current_level"]["relations"]["readers"])
        self.assertFalse(self.by_id["asm:Random"]["reachable"])


if __name__ == "__main__":
    unittest.main()
