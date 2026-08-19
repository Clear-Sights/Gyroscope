"""A licence is a state transition, not an event log.

Re-observing the same guard in the same scope changes no ledger state, so retaining every
observation only makes every later read scan duplicate history. Measured through the dispatcher
before the fix: 40 identical `git status --porcelain` calls wrote 120 rows -- three per call,
one per clause the guard discharges -- and each subsequent read is linear in what was written.

The Rust dispatcher has always carried this guard (`if self.licensed(s,a,id){return}`), so until
now the two implementations agreed on every VERDICT while disagreeing about what they WROTE. The
equivalence gate compares decisions, not their side effects, so it could not see that: 4401 calls
and 0 divergences held throughout.
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import unittest

from gyroscope import clauses as C, dispatch
from gyroscope.ledger import Demand, Ledger, derive_id
from tests.plant_support import smoke_replace


def rows_written(state: str) -> int:
    return sum(len([line for line in path.read_text().splitlines() if line.strip()])
               for path in pathlib.Path(state).rglob("*.jsonl"))


class RepeatedGuardsDoNotGrowTheLedger(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.state = self._temp.name
        os.environ["GYROSCOPE_STATE_DIR"] = self.state

    def test_TEETH_forty_identical_guards_write_one_row_per_clause(self) -> None:
        table = C.load_dir(C.default_dir())
        event = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                 "tool_input": {"command": "git status --porcelain"},
                 "session_id": "s", "agent_id": "a"}
        for _ in range(40):
            dispatch.pre_tool_use(table, Ledger(), event)
        written = rows_written(self.state)
        self.assertLessEqual(written, 10,
                             f"{written} rows for 40 identical guards; the ledger is an "
                             "obligation register, not an observation log")

    def test_TEETH_a_repeat_discharge_is_a_no_op(self) -> None:
        ledger = Ledger()
        demand_id = derive_id("s", "a", "T01", "x")
        ledger.demand(Demand(demand_id, "s", "a", "T01", "x", "guard first"))
        ledger.discharge("s", "a", demand_id, "observed")
        first = rows_written(self.state)
        for _ in range(20):
            ledger.discharge("s", "a", demand_id, "observed again")
        self.assertEqual(first, rows_written(self.state))
        # The licence itself must survive: skipping the write must not skip the state.
        self.assertNotIn(demand_id, ledger.open_ids("s", "a"))

    def test_the_check_can_fail(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        path = root / "gyroscope" / "ledger.py"
        smoke_replace(self, path,
                      b"        if self.is_licensed(session, agent, demand_id):\n            return\n",
                      b"", "tests.test_ledger_growth.RepeatedGuardsDoNotGrowTheLedger."
                      "test_TEETH_a_repeat_discharge_is_a_no_op", root,
                      "AssertionError: 2 != 22")


if __name__ == "__main__":
    unittest.main()
