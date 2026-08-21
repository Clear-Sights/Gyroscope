"""Which rung a unit is dispatched to, and the proof that the route was live.

THE ALLOCATION. Codex is the workhorse: per dollar it buys far more capacity than the dear tiers,
so it holds every rung whose failure heals. Intelligence is the only edge worth paying for, and
only where the failure does NOT heal -- where the wrong move destroys the evidence it was wrong,
or cascades into work that inherits it. `prompts/routing.bindings.json` states that per rung as
`pays_for` and `heals`, and `_admit` refuses a table that pays for intelligence on a rung it also
declares healing. A ladder that can quietly buy the dear tier for work that self-corrects is not a
budget, it is a preference.

THE LADDER IS RANK, NEVER NAME. Nothing here compares a rung's name to decide order, and no rung
name appears in a conditional in this module. Rungs sort by their declared `rank`, and `_admit`
refuses a table whose ranks are not strictly increasing from zero. This is the difference between
a ladder you can extend by editing data and one you can only extend by editing code -- and a
hardcoded name is also how a renamed rung silently stops matching the branch that was routing to
it, while every test that spells the old name keeps passing.

TRIGGERS FALL UPWARD, NEVER DOWN. `rung_for` returns the highest of the rung a unit states and the
floor of every live trigger. So unhealing beats bulk, and no trigger can pull a unit down to a
cheaper rung than it declared. The case that forces the rule is `bulk_verification_of_trusted
_clauses`: it looks exactly like bulk -- many near-identical clauses, each individually cheap --
and it is not, because the output is a decision to TRUST. A clause wrongly waved through is then
relied on, and nothing downstream re-runs the check that would have caught it. Its floor is the
top rung, and a ladder that routes it by its bulk shape has bought capacity for the one unit where
capacity is not the edge.

REACHABILITY IS PROVED, NEVER ASSUMED. `plan` will not return a route it has not seen a live probe
for. The bindings file is a claim about which routes exist; a claim is not a destination that
answers. On a dead route the trigger and the tier go on the record and the unit reroutes exactly
ONE rung upward -- one, not straight to the top, because skipping the intermediate rungs spends the
dear tier on work that a cheaper live route would have held. When no rung above is reachable the
unit stops at the top rung as BLOCKING; it is never dispatched to a route observed dead, and it is
never quietly dropped.

FAILS CLOSED, matching `clauses.match`. A probe that cannot render an answer -- it raised, it timed
out, it returned neither true nor false -- is NOT-EVALUABLE, and NOT-EVALUABLE is not reachable.
The occasion did not stop existing because the measurement failed. It is recorded as `None` rather
than `False` so the record says "not measured" instead of asserting a dead route nobody observed.

NEVER SILENTLY RETRY A DEAD ROUTE. A `RouteMemo` carries buried rungs across plans in one process.
A rung already recorded dead is not probed again -- and the skip is itself recorded, citing the
attempt that buried it, so "we did not try this" never reads the same as "we tried and it worked".
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import pathlib
from typing import Any, Callable, Iterable


LIVE, BLOCKING = "LIVE", "BLOCKING"

# What a unit states when nothing else is known about it. Named here rather than spelled at each
# call site, because the caller that forgets it would otherwise pick its own default -- and the
# cheap default and the safe default are opposite directions on this ladder.
STATED = "stated"


class RoutingError(Exception):
    """Refusal to route, distinguished by code so a caller can tell a bad table from a bad unit."""

    def __init__(self, code: str, detail: Any):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class Rung:
    name: str
    rank: int
    capability: str
    heals: bool
    pays_for: str
    binding: dict[str, Any]
    effort_ladder: tuple[str, ...] = ()

    @property
    def effort(self) -> str | None:
        """The smallest dose this rung offers, or None when it offers exactly one setting.

        Smallest-first is the family's own rule for spending anything: enumerate the candidates in
        ascending order and take the first that clears the bar. Effort inside a rung is dose, not
        capability, so it never reorders the ladder -- escalating dose within a rung is the
        dispatcher's business and this module does not do it.
        """
        return self.effort_ladder[0] if self.effort_ladder else None


@dataclass(frozen=True)
class Ladder:
    rungs: tuple[Rung, ...]
    floors: dict[str, str]

    @property
    def top(self) -> Rung:
        return self.rungs[-1]

    def by_name(self, name: str) -> Rung:
        for rung in self.rungs:
            if rung.name == name:
                return rung
        raise RoutingError("RUNG-UNKNOWN", f"{name!r} is not a rung in this ladder")

    def above(self, rung: Rung) -> Rung | None:
        """Exactly one rung dearer, or None at the top. The only way this module moves upward."""
        index = self.rungs.index(rung)
        return self.rungs[index + 1] if index + 1 < len(self.rungs) else None


@dataclass(frozen=True)
class Attempt:
    """One route, and what was observed about it. Both halves of the record the policy asks for.

    `trigger` is WHY the unit was standing on this rung -- the trigger that lifted it there, or
    `STATED` when the unit's own declaration put it there and no trigger raised it. `rung` is the
    tier. Recording the tier without the trigger produces a log of dead routes that cannot be read
    back into a routing decision, which is the same as not recording it.
    """
    rung: str
    trigger: str
    reachable: bool | None
    detail: str = ""

    @property
    def dead(self) -> bool:
        """NOT-EVALUABLE counts as dead. Unproved is not permission to dispatch."""
        return self.reachable is not True


@dataclass(frozen=True)
class Route:
    unit: str
    status: str
    rung: str
    trigger: str
    binding: dict[str, Any] | None
    effort: str | None
    attempts: tuple[Attempt, ...]

    @property
    def blocking(self) -> bool:
        return self.status == BLOCKING

    def record(self) -> dict[str, Any]:
        """The serializable record. Every attempt, not just the one that answered."""
        return {
            "unit": self.unit,
            "status": self.status,
            "rung": self.rung,
            "trigger": self.trigger,
            "binding": self.binding,
            "effort": self.effort,
            "attempts": [
                {"rung": a.rung, "trigger": a.trigger, "reachable": a.reachable, "detail": a.detail}
                for a in self.attempts
            ],
        }


@dataclass
class RouteMemo:
    """Dead routes, remembered across plans in one process.

    Without this, "never silently retry a dead route" holds only inside a single `plan` call: the
    next unit starts at the bottom again and pays the same dead probe, and the run learns nothing
    from a failure it already observed. Remembering is the cheapest compounding artifact available
    here -- one dict, written at the moment the failure is in hand.

    Scope is deliberately a process and not a file. A file would outlive the condition that made
    the route dead, and a route recorded dead forever heals only by someone remembering to delete
    the record -- which is the failure this repository is about, pointed the other way.
    """
    buried: dict[str, Attempt] = field(default_factory=dict)

    def bury(self, attempt: Attempt) -> None:
        self.buried.setdefault(attempt.rung, attempt)

    def dead(self, rung: str) -> Attempt | None:
        return self.buried.get(rung)

    def records(self) -> list[dict[str, Any]]:
        return [
            {"rung": a.rung, "trigger": a.trigger, "reachable": a.reachable, "detail": a.detail}
            for a in sorted(self.buried.values(), key=lambda a: a.rung)
        ]


def _admit(data: dict[str, Any]) -> Ladder:
    """Admission, on the same principle as the clause table: refuse, never repair.

    A table that cannot be trusted to order itself is worse than no table, because the caller has
    no way to see that the ladder it is climbing is not the ladder that was written down.
    """
    raw = data.get("rungs")
    if not isinstance(raw, list) or not raw:
        raise RoutingError("LADDER-EMPTY", "a routing table with no rungs routes nothing")

    rungs: list[Rung] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise RoutingError("RUNG-INVALID", f"rung {index} is not an object")
        name, rank = item.get("name"), item.get("rank")
        # `bool` is an `int` in Python, so `rank: true` would otherwise admit as rank 1 and sort
        # somewhere plausible. A ladder is not a place to accept a value that merely looks numeric.
        if not isinstance(name, str) or not name:
            raise RoutingError("RUNG-UNNAMED", f"rung {index} declares no name")
        if not isinstance(rank, int) or isinstance(rank, bool):
            raise RoutingError("RUNG-RANK-INVALID", f"{name}: rank {rank!r} is not an integer")
        # Strictly increasing from zero, in file order. Not "sortable by rank": a table whose file
        # order and rank order disagree reads correctly to a person and routes by the other one.
        if rank != index:
            raise RoutingError(
                "LADDER-NOT-ORDERED",
                f"{name}: rank {rank} at position {index}; ranks run cheap->dear from 0 with no "
                f"gaps, and file order is the same order",
            )
        heals, pays_for = item.get("heals"), item.get("pays_for")
        if not isinstance(heals, bool):
            raise RoutingError("RUNG-HEALS-INVALID", f"{name}: heals {heals!r} is not a boolean")
        if pays_for not in ("capacity", "intelligence"):
            raise RoutingError("RUNG-PAYS-FOR-INVALID", f"{name}: pays_for {pays_for!r}")
        # The allocation rule, enforced rather than described. Intelligence is worth paying for
        # only where the failure does not heal; a rung that claims both is a budget with a hole in
        # it, and the hole is exactly the shape of every unit someone wanted to route upward.
        if pays_for == "intelligence" and heals:
            raise RoutingError(
                "RUNG-PAYS-FOR-HEALING-WORK",
                f"{name}: pays for intelligence on work it declares healing -- intelligence is the "
                f"edge worth buying only where the failure does not heal",
            )
        binding = item.get("binding")
        if not isinstance(binding, dict) or not binding:
            raise RoutingError("RUNG-UNBOUND", f"{name}: no binding, so nothing to dispatch to")
        ladder_field = item.get("effort_ladder", [])
        if not isinstance(ladder_field, list) or not all(
                isinstance(step, str) and step for step in ladder_field):
            raise RoutingError("RUNG-EFFORT-INVALID", f"{name}: effort_ladder {ladder_field!r}")
        capability = item.get("capability")
        if not isinstance(capability, str) or not capability:
            raise RoutingError("RUNG-NO-CAPABILITY", f"{name}: rungs are ordered by capability, "
                                                     f"so a rung that states none cannot be placed")
        rungs.append(Rung(name=name, rank=rank, capability=capability, heals=heals,
                          pays_for=pays_for, binding=binding,
                          effort_ladder=tuple(ladder_field)))

    names = [rung.name for rung in rungs]
    if len(set(names)) != len(names):
        raise RoutingError("RUNG-NAME-DUPLICATE", sorted({n for n in names if names.count(n) > 1}))

    floors: dict[str, str] = {}
    for index, item in enumerate(data.get("triggers") or []):
        if not isinstance(item, dict):
            raise RoutingError("TRIGGER-INVALID", f"trigger {index} is not an object")
        trigger, floor = item.get("name"), item.get("floor")
        if not isinstance(trigger, str) or not trigger:
            raise RoutingError("TRIGGER-UNNAMED", f"trigger {index} declares no name")
        if trigger in floors:
            raise RoutingError("TRIGGER-DUPLICATE", trigger)
        # A floor naming a rung that does not exist is the drift that matters most here: the
        # trigger keeps reading as a routing rule, and routes nothing.
        if floor not in names:
            raise RoutingError("TRIGGER-FLOOR-UNKNOWN", f"{trigger}: floor {floor!r} is no rung")
        floors[trigger] = floor
    return Ladder(rungs=tuple(rungs), floors=floors)


def packaged_path() -> pathlib.Path:
    """The copy that ships inside the plugin, one directory above the package."""
    return pathlib.Path(__file__).resolve().parent.parent / "prompts" / "routing.bindings.json"


def _account_dir() -> pathlib.Path:
    """Ported by shape from ledger.state_dir, never imported across that boundary."""
    if os.environ.get("CODEX_PLUGIN_ROOT") or os.environ.get("CODEX_HOME"):
        return pathlib.Path.home() / ".codex"
    return pathlib.Path.home() / ".claude"


def candidate_paths(cwd: pathlib.Path | None = None) -> list[pathlib.Path]:
    """Where a bindings table is looked for, dearest-authority first.

    First hit wins and the packaged copy is last, so a repository or an account that states its own
    ladder OVERRIDES the shipped one rather than merging into it. A merge would let a repository
    inherit a rung it never declared, and the rung it inherits is the one that decides what gets
    paid for.
    """
    paths: list[pathlib.Path] = []
    override = os.environ.get("GYROSCOPE_ROUTING_BINDINGS")
    if override:
        paths.append(pathlib.Path(override))
    root = pathlib.Path(cwd) if cwd is not None else pathlib.Path.cwd()
    paths.append(root / "prompts" / "routing.bindings.json")
    paths.append(_account_dir() / "routing.bindings.json")
    paths.append(packaged_path())
    return paths


def load_ladder(path=None, cwd: pathlib.Path | None = None) -> Ladder:
    """Load and admit one table. An explicit path that is absent is an error, never a fallback.

    Silently falling through from a path the caller NAMED to the packaged default is how a run
    reports that it honoured a configuration it never read.
    """
    if path is not None:
        return _admit(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))
    for candidate in candidate_paths(cwd):
        if candidate.is_file():
            return _admit(json.loads(candidate.read_text(encoding="utf-8")))
    raise RoutingError("LADDER-ABSENT", "no routing bindings on any candidate path")


def rung_for(ladder: Ladder, stated: str, triggers: Iterable[str] = ()) -> tuple[Rung, str]:
    """The rung a unit stands on, and the trigger that put it there.

    Triggers fall upward only: the answer is the highest of the stated rung and every live
    trigger's floor. With no trigger live the stated rung stands -- which is what "absent triggers
    fall up" means in the direction where nothing is absent.
    """
    if not isinstance(stated, str) or not stated:
        # Not defaulted in either direction. Defaulting down buys the cheap tier for work nobody
        # classified; defaulting up buys the dear one for all of it. Both are a decision the unit
        # was supposed to make, made silently somewhere else.
        raise RoutingError("UNIT-NO-RUNG", "a unit states its rung; this one states none")
    best, why = ladder.by_name(stated), STATED
    for trigger in triggers:
        floor = ladder.floors.get(trigger)
        if floor is None:
            raise RoutingError("TRIGGER-UNKNOWN", f"{trigger!r} is not a trigger in this table")
        candidate = ladder.by_name(floor)
        if candidate.rank > best.rank:
            best, why = candidate, trigger
    return best, why


def plan(
    unit: str,
    stated: str,
    probe: Callable[[Rung], bool | None],
    ladder: Ladder,
    triggers: Iterable[str] = (),
    memo: RouteMemo | None = None,
) -> Route:
    """Prove the route before dispatching to it, and reroute one rung upward when it is dead.

    `probe` answers whether ONE rung's binding is reachable right now: True, False, or None for a
    measurement that could not be taken. It is called at most once per rung per plan, and never at
    all for a rung the memo has already buried.

    The walk only ever climbs. When the top rung is dead too, the unit stops there as BLOCKING with
    no binding -- it is not dispatched to a route observed dead, and it is not dropped. A blocking
    route still carries every attempt, so the reason is in the same object as the refusal.
    """
    start, trigger = rung_for(ladder, stated, triggers)
    attempts: list[Attempt] = []
    rung: Rung | None = start
    while rung is not None:
        buried = memo.dead(rung.name) if memo is not None else None
        if buried is not None:
            # Recorded, not skipped in silence: a route nobody tried this time must not read the
            # same as one that answered. The citation is the earlier attempt, so the plan says
            # which observation it is standing on.
            attempts.append(Attempt(rung.name, trigger, buried.reachable,
                                    f"not probed again; buried by an earlier attempt "
                                    f"({buried.trigger}): {buried.detail}".rstrip(": ")))
            rung = ladder.above(rung)
            continue
        try:
            answer = probe(rung)
        except Exception as exc:  # noqa: BLE001 -- any probe fault is NOT-EVALUABLE, not a pass
            answer, detail = None, f"{type(exc).__name__}: {exc}"
        else:
            detail = "" if answer is True else ("probe returned false" if answer is False
                                                else "probe returned no measurement")
        attempt = Attempt(rung.name, trigger, answer if isinstance(answer, bool) else None, detail)
        attempts.append(attempt)
        if not attempt.dead:
            return Route(unit=unit, status=LIVE, rung=rung.name, trigger=trigger,
                         binding=dict(rung.binding), effort=rung.effort,
                         attempts=tuple(attempts))
        if memo is not None:
            memo.bury(attempt)
        rung = ladder.above(rung)
    top = ladder.top
    return Route(unit=unit, status=BLOCKING, rung=top.name, trigger=trigger, binding=None,
                 effort=None, attempts=tuple(attempts))
