"""The ladder, the fall upward, and the proof that a route was live before anything went to it.

Four properties carry the whole policy, and each has teeth below rather than a sentence:

  * ORDER IS RANK, NEVER NAME. A ladder whose names sort one way and whose ranks sort the other
    routes by rank, and a table that cannot order itself is refused instead of repaired.
  * TRIGGERS FALL UPWARD. The rung is the highest of the stated one and every live trigger's
    floor, so unhealing beats bulk and nothing can pull a unit down to a cheaper rung.
  * REACHABILITY IS PROVED. No route is returned that has not been observed live; a probe that
    renders no answer is NOT-EVALUABLE, and NOT-EVALUABLE is not permission.
  * A DEAD ROUTE IS NEVER SILENTLY RETRIED. It goes on the record with its trigger and its tier,
    the unit climbs exactly one rung, and a rung already buried is not probed again.

`TheChecksCanFail` plants a fault at each of those four seams and requires the NAMED test to go
red because of it. Without that, every assertion here would be satisfied by a suite that had
quietly stopped testing the thing it names -- which is the defect this repository exists to refuse,
and which a sibling check in this family shipped for real.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.plant_support import PLUGIN, smoke_replace

from gyroscope import routing
from gyroscope.routing import BLOCKING, LIVE, RouteMemo, RoutingError


BINDINGS = PLUGIN / "prompts" / "routing.bindings.json"
ROUTING_PY = PLUGIN / "gyroscope" / "routing.py"


def shipped() -> routing.Ladder:
    return routing.load_ladder(BINDINGS)


def table(rungs, triggers=()) -> routing.Ladder:
    """Build a ladder from tuples, so a test can state the shape it is testing and nothing else."""
    return routing._admit({
        "rungs": [
            {"name": name, "rank": rank, "capability": f"{name} capability", "heals": heals,
             "pays_for": pays, "binding": {"host": "test", "model": name}}
            for name, rank, heals, pays in rungs
        ],
        "triggers": [{"name": name, "floor": floor} for name, floor in triggers],
    })


def counting(answers):
    """A probe that answers per rung name and counts how many times each rung was asked.

    The count is the point: "never silently retry a dead route" is a claim about calls that did
    NOT happen, and the only way to test an absent call is to count.
    """
    calls: list[str] = []

    def probe(rung):
        calls.append(rung.name)
        answer = answers.get(rung.name, False)
        if isinstance(answer, Exception):
            raise answer
        return answer

    return probe, calls


class TheShippedTableAdmits(unittest.TestCase):
    """The table that ships is the one that gets used, so it is checked, not assumed."""

    def setUp(self) -> None:
        self.ladder = shipped()

    def test_the_ladder_runs_cheap_to_dear_with_no_gaps(self) -> None:
        self.assertEqual([0, 1, 2, 3, 4], [rung.rank for rung in self.ladder.rungs])
        self.assertEqual(["bulk", "moderate", "hard", "extreme", "pivotal"],
                         [rung.name for rung in self.ladder.rungs])

    def test_intelligence_is_bought_only_where_the_failure_does_not_heal(self) -> None:
        """The allocation, read back off the shipped file rather than off the prose about it."""
        for rung in self.ladder.rungs:
            if rung.pays_for == "intelligence":
                self.assertFalse(rung.heals, f"{rung.name} buys the dear tier for healing work")
        self.assertEqual(["extreme", "pivotal"],
                         [r.name for r in self.ladder.rungs if r.pays_for == "intelligence"])

    def test_codex_holds_every_rung_whose_failure_heals(self) -> None:
        """The workhorse claim, stated as a property of the bindings and not of the comment."""
        healing = [rung for rung in self.ladder.rungs if rung.heals]
        self.assertEqual(3, len(healing))
        for rung in healing:
            self.assertEqual("codex", rung.binding.get("host"), rung.name)
            self.assertEqual("capacity", rung.pays_for, rung.name)

    def test_bulk_is_the_one_rung_that_carries_sub_levels(self) -> None:
        """Dose lives inside the bulk rung; every other rung offers one setting.

        Asserted both directions. Only checking that bulk HAS a ladder would stay green if every
        rung grew one, and a ladder where dose is available everywhere is a ladder where dose can
        be raised instead of the rung -- which is the fall upward, defeated by a cheaper knob.
        """
        self.assertEqual(("low", "medium", "high"), self.ladder.by_name("bulk").effort_ladder)
        self.assertEqual("low", self.ladder.by_name("bulk").effort)
        for rung in self.ladder.rungs:
            if rung.name != "bulk":
                self.assertEqual((), rung.effort_ladder, rung.name)
                self.assertIsNone(rung.effort, rung.name)

    def test_bulk_verification_of_trusted_clauses_takes_the_top_rung(self) -> None:
        """The named exception, and the reason the fall-upward rule exists at all.

        It looks like bulk and it is not: the output is a decision to TRUST, and a clause wrongly
        waved through is then relied on by work that will never re-run the check. Its floor is the
        top rung, so a unit carrying it lands there even when it also states the cheapest one.
        """
        self.assertEqual("pivotal", self.ladder.floors["bulk_verification_of_trusted_clauses"])
        rung, why = routing.rung_for(self.ladder, "bulk",
                                     ["bulk", "bulk_verification_of_trusted_clauses"])
        self.assertEqual(self.ladder.top.name, rung.name)
        self.assertEqual("bulk_verification_of_trusted_clauses", why)

    def test_every_trigger_floor_names_a_rung_that_exists(self) -> None:
        names = {rung.name for rung in self.ladder.rungs}
        self.assertTrue(self.ladder.floors)
        for trigger, floor in self.ladder.floors.items():
            self.assertIn(floor, names, trigger)


class TheLadderIsRankNeverName(unittest.TestCase):
    """Order comes off `rank`. No rung name appears in a conditional in the module."""

    def test_a_ladder_whose_names_sort_against_its_ranks_still_routes_by_rank(self) -> None:
        """Names chosen so alphabetical order is the exact reverse of capability order.

        If anything in the resolver sorted or compared by name, `zulu` -- the CHEAPEST rung -- would
        come out on top and the dear tier would be bought for the cheapest work in the table.
        """
        ladder = table([("zulu", 0, True, "capacity"), ("mike", 1, True, "capacity"),
                        ("alpha", 2, False, "intelligence")],
                       [("up", "alpha")])
        self.assertEqual(["zulu", "mike", "alpha"], [r.name for r in ladder.rungs])
        self.assertEqual("alpha", ladder.top.name)
        rung, _ = routing.rung_for(ladder, "zulu", ["up"])
        self.assertEqual("alpha", rung.name)

    def test_a_table_whose_ranks_skip_is_refused(self) -> None:
        with self.assertRaises(RoutingError) as caught:
            table([("a", 0, True, "capacity"), ("b", 2, False, "intelligence")])
        self.assertEqual("LADDER-NOT-ORDERED", caught.exception.code)

    def test_a_table_whose_file_order_disagrees_with_its_ranks_is_refused(self) -> None:
        """A table that reads correctly to a person and routes by the other order."""
        with self.assertRaises(RoutingError) as caught:
            table([("a", 1, True, "capacity"), ("b", 0, False, "intelligence")])
        self.assertEqual("LADDER-NOT-ORDERED", caught.exception.code)

    def test_a_boolean_rank_is_refused_rather_than_read_as_one(self) -> None:
        """`bool` is an `int` in Python, so `rank: true` would otherwise sort somewhere plausible."""
        with self.assertRaises(RoutingError) as caught:
            routing._admit({"rungs": [
                {"name": "a", "rank": 0, "capability": "c", "heals": True,
                 "pays_for": "capacity", "binding": {"host": "t"}},
                {"name": "b", "rank": True, "capability": "c", "heals": False,
                 "pays_for": "intelligence", "binding": {"host": "t"}},
            ]})
        self.assertEqual("RUNG-RANK-INVALID", caught.exception.code)

    def test_a_rung_paying_for_intelligence_on_healing_work_is_refused(self) -> None:
        with self.assertRaises(RoutingError) as caught:
            table([("a", 0, True, "intelligence")])
        self.assertEqual("RUNG-PAYS-FOR-HEALING-WORK", caught.exception.code)

    def test_a_trigger_whose_floor_is_no_rung_is_refused(self) -> None:
        """The drift that matters most: the trigger still reads as a rule, and routes nothing."""
        with self.assertRaises(RoutingError) as caught:
            table([("a", 0, True, "capacity")], [("up", "nowhere")])
        self.assertEqual("TRIGGER-FLOOR-UNKNOWN", caught.exception.code)

    def test_an_unbound_rung_is_refused(self) -> None:
        with self.assertRaises(RoutingError) as caught:
            routing._admit({"rungs": [{"name": "a", "rank": 0, "capability": "c", "heals": True,
                                       "pays_for": "capacity", "binding": {}}]})
        self.assertEqual("RUNG-UNBOUND", caught.exception.code)


class TriggersFallUpward(unittest.TestCase):

    def setUp(self) -> None:
        self.ladder = shipped()

    def test_with_no_trigger_live_the_stated_rung_stands(self) -> None:
        rung, why = routing.rung_for(self.ladder, "moderate")
        self.assertEqual("moderate", rung.name)
        self.assertEqual(routing.STATED, why)

    def test_unhealing_beats_bulk(self) -> None:
        """The rule in one line: a bulk-shaped unit whose failure does not heal is not bulk work."""
        rung, why = routing.rung_for(self.ladder, "bulk", ["bulk", "unhealing"])
        self.assertEqual("pivotal", rung.name,
                         "unhealing did not beat bulk: the unit routed to the cheap rung")
        self.assertEqual("unhealing", why)

    def test_no_trigger_can_pull_a_unit_below_the_rung_it_states(self) -> None:
        """Downward is the direction that costs something, so it is closed rather than discouraged."""
        rung, why = routing.rung_for(self.ladder, "pivotal", ["bulk", "implementation"])
        self.assertEqual("pivotal", rung.name)
        self.assertEqual(routing.STATED, why)

    def test_the_highest_live_trigger_wins_and_names_itself(self) -> None:
        rung, why = routing.rung_for(self.ladder, "bulk",
                                     ["implementation", "cross_cutting", "difficult_judgment"])
        self.assertEqual("extreme", rung.name)
        self.assertEqual("cross_cutting", why)

    def test_the_three_default_placements_are_what_the_policy_says(self) -> None:
        """Bulk tests lowest, implementation the middle, difficult judgment the highest band below."""
        self.assertEqual("bulk", routing.rung_for(self.ladder, "bulk", ["bulk"])[0].name)
        self.assertEqual("moderate",
                         routing.rung_for(self.ladder, "bulk", ["implementation"])[0].name)
        judgment = routing.rung_for(self.ladder, "bulk", ["difficult_judgment"])[0]
        self.assertEqual("hard", judgment.name)
        self.assertLess(judgment.rank, self.ladder.top.rank)

    def test_a_unit_that_states_no_rung_is_refused_in_both_directions(self) -> None:
        """Not defaulted down and not defaulted up: either one is the unit's decision, made silently.

        Down buys the cheap tier for work nobody classified. Up buys the dear one for all of it,
        which is how a budget stops meaning anything. So it raises.
        """
        with self.assertRaises(RoutingError) as caught:
            routing.rung_for(self.ladder, "")
        self.assertEqual("UNIT-NO-RUNG", caught.exception.code)

    def test_an_unknown_trigger_is_refused_rather_than_ignored(self) -> None:
        """A misspelled trigger that is silently dropped routes the unit to its cheap stated rung."""
        with self.assertRaises(RoutingError) as caught:
            routing.rung_for(self.ladder, "bulk", ["unhealng"])
        self.assertEqual("TRIGGER-UNKNOWN", caught.exception.code)


class ReachabilityIsProvedBeforeDispatch(unittest.TestCase):

    def setUp(self) -> None:
        self.ladder = shipped()

    def test_a_live_route_carries_the_probe_that_proved_it(self) -> None:
        probe, calls = counting({"moderate": True})
        route = routing.plan("u", "moderate", probe, self.ladder)
        self.assertEqual(LIVE, route.status)
        self.assertEqual("moderate", route.rung)
        self.assertEqual({"host": "codex", "invoke": ["codex", "exec"]}, route.binding)
        self.assertEqual(["moderate"], calls)
        self.assertTrue(route.attempts[-1].reachable)

    def test_nothing_below_the_units_rung_is_ever_probed(self) -> None:
        """The walk only climbs, so a cheaper live route is never found by looking down for one."""
        probe, calls = counting({name: True for name in
                                 ("bulk", "moderate", "hard", "extreme", "pivotal")})
        route = routing.plan("u", "bulk", probe, self.ladder, ["cross_cutting"])
        self.assertEqual("extreme", route.rung)
        self.assertEqual(["extreme"], calls)

    def test_a_not_evaluable_probe_is_not_permission(self) -> None:
        """Fails closed, like `clauses.match`. An unproved route is not a reachable one."""
        probe, calls = counting({"hard": None, "extreme": True})
        route = routing.plan("u", "hard", probe, self.ladder)
        self.assertEqual("extreme", route.rung)
        self.assertEqual(["hard", "extreme"], calls)
        self.assertIsNone(route.attempts[0].reachable,
                          "a measurement that was never taken was recorded as one that was")
        self.assertTrue(route.attempts[0].dead)

    def test_a_probe_that_raises_is_not_evaluable_rather_than_a_crash(self) -> None:
        """A fault in the measurement is a fact about the measurement, not about the route."""
        probe, _ = counting({"hard": RuntimeError("no credential"), "extreme": True})
        route = routing.plan("u", "hard", probe, self.ladder)
        self.assertEqual("extreme", route.rung)
        self.assertIsNone(route.attempts[0].reachable)
        self.assertIn("RuntimeError: no credential", route.attempts[0].detail)


class OnFailureRerouteExactlyOneRung(unittest.TestCase):

    def setUp(self) -> None:
        self.ladder = shipped()

    def test_a_dead_bottom_rung_reroutes_exactly_one_rung_up(self) -> None:
        """One rung, not straight to the top.

        Jumping to the top on the first dead route spends the dear tier on work that the very next
        rung would have held -- and it would do so on every unit, because the condition that killed
        the cheapest route is usually not specific to that unit.
        """
        probe, calls = counting({"moderate": True})
        route = routing.plan("u", "bulk", probe, self.ladder)
        self.assertEqual(LIVE, route.status)
        self.assertEqual("moderate", route.rung)
        self.assertEqual(["bulk", "moderate"], calls)

    def test_each_failure_records_its_trigger_and_its_tier(self) -> None:
        """Both halves. A tier without its trigger cannot be read back into a routing decision."""
        probe, _ = counting({"pivotal": True})
        route = routing.plan("u", "bulk", probe, self.ladder, ["cross_cutting"])
        self.assertEqual([("extreme", "cross_cutting"), ("pivotal", "cross_cutting")],
                         [(a.rung, a.trigger) for a in route.attempts])
        self.assertEqual([False, True], [a.reachable for a in route.attempts])

    def test_the_record_serializes_every_attempt_not_only_the_one_that_answered(self) -> None:
        probe, _ = counting({"hard": True})
        record = routing.plan("u", "bulk", probe, self.ladder).record()
        json.dumps(record)
        self.assertEqual(["bulk", "moderate", "hard"], [a["rung"] for a in record["attempts"]])
        self.assertEqual("hard", record["rung"])


class NoRungReachableBlocksAtTheTop(unittest.TestCase):

    def setUp(self) -> None:
        self.ladder = shipped()
        self.probe, self.calls = counting({})
        self.route = routing.plan("u", "bulk", self.probe, self.ladder)

    def test_the_unit_stops_at_the_top_rung_as_blocking(self) -> None:
        self.assertEqual(BLOCKING, self.route.status)
        self.assertTrue(self.route.blocking)
        self.assertEqual(self.ladder.top.name, self.route.rung)

    def test_a_blocking_route_carries_no_binding_to_dispatch_to(self) -> None:
        """It is not dispatched to a route observed dead, and it is not dropped either."""
        self.assertIsNone(self.route.binding)
        self.assertIsNone(self.route.effort)

    def test_every_rung_from_the_units_own_upward_is_on_the_record(self) -> None:
        self.assertEqual(["bulk", "moderate", "hard", "extreme", "pivotal"],
                         [a.rung for a in self.route.attempts])
        self.assertEqual(["bulk", "moderate", "hard", "extreme", "pivotal"], self.calls)


class NeverSilentlyRetryADeadRoute(unittest.TestCase):

    def setUp(self) -> None:
        self.ladder = shipped()

    def test_no_rung_is_probed_twice_inside_one_plan(self) -> None:
        probe, calls = counting({})
        routing.plan("u", "bulk", probe, self.ladder)
        self.assertEqual(len(calls), len(set(calls)), f"a rung was re-probed: {calls}")

    def test_a_buried_rung_is_not_probed_again(self) -> None:
        """The memo is what makes the rule hold across units instead of only inside one plan."""
        memo = RouteMemo()
        first, calls_one = counting({"hard": True})
        routing.plan("one", "bulk", first, self.ladder, memo=memo)
        self.assertEqual(["bulk", "moderate", "hard"], calls_one)
        self.assertEqual(["bulk", "moderate"], sorted(memo.buried))

        second, calls_two = counting({"hard": True})
        route = routing.plan("two", "bulk", second, self.ladder, memo=memo)
        self.assertEqual(["hard"], calls_two,
                         "a route already observed dead was probed again")
        self.assertEqual("hard", route.rung)

    def test_a_skipped_rung_is_recorded_not_omitted(self) -> None:
        """"We did not try this" must never read the same as "we tried and it worked"."""
        memo = RouteMemo()
        routing.plan("one", "bulk", counting({"hard": True})[0], self.ladder, memo=memo)
        route = routing.plan("two", "bulk", counting({"hard": True})[0], self.ladder, memo=memo)
        skipped = [a for a in route.attempts if a.rung in ("bulk", "moderate")]
        self.assertEqual(2, len(skipped))
        for attempt in skipped:
            self.assertTrue(attempt.dead)
            self.assertIn("not probed again", attempt.detail)

    def test_a_buried_rung_is_never_returned_as_the_route(self) -> None:
        memo = RouteMemo()
        memo.bury(routing.Attempt("extreme", "cross_cutting", False, "dead"))
        probe, calls = counting({"extreme": True, "pivotal": True})
        route = routing.plan("u", "extreme", probe, self.ladder)
        self.assertEqual("extreme", route.rung, "control: reachable without the memo")
        route = routing.plan("u", "extreme", probe, self.ladder, memo=memo)
        self.assertEqual("pivotal", route.rung)
        self.assertNotIn("extreme", calls[1:])

    def test_the_memo_reports_what_it_buried(self) -> None:
        memo = RouteMemo()
        routing.plan("u", "bulk", counting({"pivotal": True})[0], self.ladder, memo=memo)
        rungs = [record["rung"] for record in memo.records()]
        self.assertEqual(["bulk", "extreme", "hard", "moderate"], rungs)
        json.dumps(memo.records())


class ResolutionOrder(unittest.TestCase):
    """A repository or an account that states its own ladder overrides the shipped one."""

    def test_the_order_is_override_then_repository_then_account_then_packaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["GYROSCOPE_ROUTING_BINDINGS"] = f"{tmp}/named.json"
            self.addCleanup(os.environ.pop, "GYROSCOPE_ROUTING_BINDINGS", None)
            paths = routing.candidate_paths(Path(tmp))
        self.assertEqual(Path(f"{tmp}/named.json"), paths[0])
        self.assertEqual(Path(tmp) / "prompts" / "routing.bindings.json", paths[1])
        self.assertEqual("routing.bindings.json", paths[2].name)
        self.assertEqual(routing.packaged_path(), paths[-1])

    def test_a_repository_table_wins_over_the_packaged_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "prompts"
            local.mkdir()
            (local / "routing.bindings.json").write_text(json.dumps({
                "rungs": [{"name": "only", "rank": 0, "capability": "c", "heals": True,
                           "pays_for": "capacity", "binding": {"host": "local"}}],
                "triggers": [],
            }), encoding="utf-8")
            ladder = routing.load_ladder(cwd=Path(tmp))
        self.assertEqual(["only"], [rung.name for rung in ladder.rungs])

    def test_a_named_path_that_is_absent_raises_rather_than_falling_back(self) -> None:
        """Falling through from a path the caller NAMED reports honouring a config never read."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                routing.load_ladder(Path(tmp) / "nothing.json")


class TheChecksCanFail(unittest.TestCase):
    """Plant a fault at each of the four seams and require the NAMED test to go red.

    `smoke_replace` runs the target GREEN on the unmutated file first, so a target that is red for
    some other reason cannot be mistaken for a seam that is covered.
    """

    def test_PLANT_reversing_the_fall_makes_triggers_fall_downward(self) -> None:
        smoke_replace(
            self, ROUTING_PY,
            b"if candidate.rank > best.rank:", b"if candidate.rank < best.rank:",
            "tests.test_routing.TriggersFallUpward.test_unhealing_beats_bulk",
            "unhealing did not beat bulk",
        )

    def test_PLANT_dropping_the_order_check_admits_an_unordered_ladder(self) -> None:
        smoke_replace(
            self, ROUTING_PY,
            b"        if rank != index:", b"        if False:",
            "tests.test_routing.TheLadderIsRankNeverName.test_a_table_whose_ranks_skip_is_refused",
            "RoutingError",
        )

    def test_PLANT_escalating_to_the_top_stops_being_one_rung(self) -> None:
        smoke_replace(
            self, ROUTING_PY,
            b"return self.rungs[index + 1] if index + 1 < len(self.rungs) else None",
            b"return self.rungs[-1] if index + 1 < len(self.rungs) else None",
            "tests.test_routing.OnFailureRerouteExactlyOneRung"
            ".test_a_dead_bottom_rung_reroutes_exactly_one_rung_up",
            "AssertionError",
        )

    def test_PLANT_treating_not_evaluable_as_permission_dispatches_to_an_unproved_route(self) -> None:
        smoke_replace(
            self, ROUTING_PY,
            b"return self.reachable is not True", b"return self.reachable is False",
            "tests.test_routing.ReachabilityIsProvedBeforeDispatch"
            ".test_a_not_evaluable_probe_is_not_permission",
            "AssertionError",
        )

    def test_PLANT_forgetting_the_memo_retries_a_dead_route(self) -> None:
        smoke_replace(
            self, ROUTING_PY,
            b"buried = memo.dead(rung.name) if memo is not None else None",
            b"buried = None",
            "tests.test_routing.NeverSilentlyRetryADeadRoute.test_a_buried_rung_is_not_probed_again",
            "a route already observed dead was probed again",
        )

    def test_PLANT_routing_the_trusted_clause_sweep_as_bulk_goes_red(self) -> None:
        """The seam in the shipped TABLE, not the code: the policy's own named exception."""
        smoke_replace(
            self, BINDINGS,
            b'{"name": "bulk_verification_of_trusted_clauses", "floor": "pivotal"',
            b'{"name": "bulk_verification_of_trusted_clauses", "floor": "bulk"',
            "tests.test_routing.TheShippedTableAdmits"
            ".test_bulk_verification_of_trusted_clauses_takes_the_top_rung",
            "AssertionError",
        )


if __name__ == "__main__":
    unittest.main()
