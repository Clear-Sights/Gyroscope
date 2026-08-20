"""The one mechanism: demand -> discharge -> reconciliation.

A PreToolUse deny records a DEMAND. A later call matching the clause's guard records a DISCHARGE.
At Stop, anything still open is unreconciled and blocks. That is the whole model; the nine things
that looked like separate Stop checks are one ledger read.

HONESTY BOUNDARY, stated where the mechanism is introduced rather than in a footnote: the ledger
is written by the same agent it constrains. The hash chain detects accidental corruption, a
truncated write, bit-rot. It does NOT detect deliberate forgery -- anyone who can append to
`closures.jsonl` can append a matching hash. This constrains an honest-but-forgetful agent, not a
forging one, and no mechanism inside this trust boundary can do better. Ventura's manifest records
the same limit for the same reason.

ABSENCE IS NOT A PASS. An empty ledger at Stop means nothing was recorded, which is not the same
as nothing being owed -- it is NOT-EVALUABLE. A shipped verifier once scored an absent check
better than an empty one, and that inversion is the defect this file refuses to repeat.

MEASURED SCOPING LIMIT (2026-08-14, observed, not theorised): a nested `claude -p` invocation
reported the SAME `session_id` as the session that launched it, with `agent_id` empty. Scope is
keyed on `(session_id, agent_id)`, so a nested run shares its parent's ledger and the parent can
be blocked at Stop by a demand the child raised. This is the pooling hazard a sibling plugin
already paid for; it fixed it by treating a main-thread Stop as structurally agentless and letting
an ambiguous id contribute nothing rather than borrow. The keying here is correct for the ids the
host supplies -- it cannot separate threads the host does not distinguish. Recorded rather than
papered over, because a scope that silently pools is worse than one that says it pools.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
from dataclasses import dataclass, asdict

# Obligations are UN-WINDOWED within a session: a promise does not expire because an hour passed.
# Events may be windowed for cost; demands never are.
OPEN, DISCHARGED = "open", "discharged"


def state_dir() -> pathlib.Path:
    """Own store, not a host-provided one -- no CLAUDE_PLUGIN_DATA equivalent exists on codex."""
    env = os.environ.get("GYROSCOPE_STATE_DIR")
    if env:
        return pathlib.Path(env)
    if os.environ.get("CODEX_PLUGIN_ROOT") or os.environ.get("CODEX_HOME"):
        return pathlib.Path.home() / ".codex" / "gyroscope_state"
    return pathlib.Path.home() / ".claude" / "gyroscope_state"


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def derive_id(session: str, agent: str, clause_id: str, subject: str) -> str:
    """Content-addressed, so re-stating one demand does not duplicate it.

    `subject` is the normalized thing at risk (a path, a ref, a command head) -- not the whole
    command, or two spellings of one demand would read as two.
    """
    return hashlib.sha256(_canon([session, agent, clause_id, subject]).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Demand:
    id: str
    session: str
    agent: str
    clause_id: str
    subject: str
    reason: str
    state: str = OPEN


class Ledger:
    """One path, one writer. Every append goes through `_append`; nothing else opens the file.

    Reconciliation is PER THREAD, never pooled: a main-thread Stop is structurally agentless, a
    subagent carries its own agent id, and an ambiguous id contributes nothing rather than
    borrowing another thread's demands. Pooling lets a sibling's dangling demand block every
    later Stop -- a measured defect in a sibling plugin, not a hypothetical.
    """

    def __init__(self, root: pathlib.Path | None = None):
        self.root = pathlib.Path(root) if root else state_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "obligations.jsonl"

    def _append(self, row: dict) -> None:
        prev = self._tail_hash()
        row = dict(row)
        row["prev"] = prev
        row["hash"] = hashlib.sha256((prev + _canon(row)).encode()).hexdigest()[:16]
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_canon(row) + "\n")

    def _tail_hash(self) -> str:
        last = ""
        for row in self._rows():
            last = row.get("hash", "")
        return last

    def _rows(self):
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # A malformed row is skipped, never fatal: this plugin fails OPEN, and a
                    # corrupt ledger must not wedge every session behind it.
                    continue

    def demand(self, d: Demand) -> bool:
        """Record a demand. Returns False if this exact demand is already open (idempotent)."""
        if d.id in self.open_ids(d.session, d.agent):
            return False
        self._append({"kind": "demand", **asdict(d)})
        return True

    def discharge(self, session: str, agent: str, demand_id: str, how: str) -> None:
        # A licence is a state TRANSITION, not an event log. Re-observing the same guard in
        # the same scope changes nothing, so keeping every observation only makes every later
        # read scan duplicate history -- measured, 40 identical `git status` calls wrote 120
        # rows through the dispatcher, and reads are linear in what was written.
        # The Rust dispatcher has always had this guard (`if self.licensed(..){return}`), so
        # until now the two implementations disagreed about ledger state while agreeing on
        # every verdict -- a divergence the equivalence gate cannot see, because it compares
        # decisions and not what they wrote.
        if self.is_licensed(session, agent, demand_id):
            return
        self._append({"kind": "discharge", "session": session, "agent": agent,
                      "id": demand_id, "how": how})

    def is_licensed(self, session: str, agent: str, demand_id: str) -> bool:
        """True once the guard call for this exact subject has been observed.

        This is the whole point of the mechanism and it is deliberately NOT `demand_id not in
        open_ids`: a demand that was never raised is also "not open", and treating that as a
        licence would let the costly act through on the strength of nothing ever having happened.
        Absence is not a licence; only an observed discharge is.
        """
        return any(
            row.get("kind") == "discharge" and row.get("id") == demand_id
            and row.get("session") == session and row.get("agent") == agent
            for row in self._rows()
        )

    def open_ids(self, session: str, agent: str) -> set[str]:
        opened, closed = set(), set()
        for row in self._rows():
            if row.get("session") != session or row.get("agent") != agent:
                continue
            if row.get("kind") == "demand":
                opened.add(row["id"])
            elif row.get("kind") == "discharge":
                closed.add(row["id"])
        return opened - closed

    def open_demands(self, session: str, agent: str) -> list[dict]:
        ids = self.open_ids(session, agent)
        seen, out = set(), []
        for row in self._rows():
            if row.get("kind") == "demand" and row.get("id") in ids and row["id"] not in seen:
                seen.add(row["id"])
                out.append(row)
        return out

    def verify_chain(self) -> str | None:
        """Re-derive the chain. Returns the first divergent hash, or None. Advisory only."""
        prev = ""
        for row in self._rows():
            body = {k: v for k, v in row.items() if k != "hash"}
            if hashlib.sha256((prev + _canon(body)).encode()).hexdigest()[:16] != row.get("hash"):
                return row.get("hash") or "<missing>"
            prev = row["hash"]
        return None
