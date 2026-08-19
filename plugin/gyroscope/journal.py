"""gyroscope.journal -- the persisted record: what Gyroscope did, per session, per tool.

WHY THIS EXISTS. Gyroscope hooks PreToolUse, PostToolUse, Stop, SessionStart, SubagentStart and
SubagentStop -- six event families, every one of them evaluated against the clause table -- and
wrote nothing down unless a demand was actually raised. `obligations.jsonl` is a LEDGER, not a log:
it records outstanding obligations, so a session in which every clause passed leaves the state
directory empty, and so does a session in which the plugin never ran at all.

That means the question "did Gyroscope catch anything this session?" had no answer. Not "no" --
UNANSWERABLE, which is strictly worse, because absence-of-record is exactly what a healthy session,
a mis-wired plugin, and an uninstalled plugin all look like. This module's whole job is to make
those three distinguishable.

It is the same law this plugin already applies to its own clause table -- "absence must never read
as green", the reason `dispatch.main` refuses a zero-clause load -- turned around and applied to
the plugin itself. A gate that will not accept an unexplained silence from the session should not
be producing one about itself.

FOUR ROW KINDS, deliberately not five:

  * `session` -- ONE row the first time a session is seen, carrying the clause count. The liveness
    proof, and the reason the log answers "did it run" separately from "did it find anything". A
    row saying `clauses: 0` is a Gyroscope that checked nothing while everyone believes it is on.
  * `deny`    -- a PreToolUse refusal, naming the clause and the subject it is keyed on.
  * `block`   -- a Stop/SubagentStop reconciliation block, naming the unreconciled count.
  * `fault`   -- an event that could not be evaluated, and which way it fell.

There is deliberately NO row per allowed call: a sibling plugin measured that policy and found the
log ran 99%+ noise. A log nobody can read is a log nobody reads.

EVERY ROW NAMES ITS PLUGIN. Ward, Gyroscope and Makoto all register PreToolUse and all three can
deny; the host does not tell the user which one spoke. `plugin` is that name, and the deny reason
on the wire carries the same `gyroscope` prefix, so transcript and log can be joined afterwards.

FAILURE POSTURE: observability, never policy. Every entry point swallows everything. A gate that
denied because its logger could not write would be a worse defect than the missing log.
"""
from __future__ import annotations

import json
import os
import pathlib
from datetime import datetime, timezone

PLUGIN = "gyroscope"


def _root(root=None) -> pathlib.Path:
    if root is not None:
        return pathlib.Path(root)
    from .ledger import state_dir
    return state_dir()


def _append(row: dict, root=None) -> None:
    """Append one compact JSON line to `decisions.jsonl`.

    POSIX guarantees atomicity for short append-mode writes (<= PIPE_BUF); a row is far under, so
    concurrent hook processes cannot interleave. `ensure_ascii=True` deliberately -- unlike the
    ledger's canonical form, this writer must never be able to become the encoding failure it
    exists to record.
    """
    path = _root(root)
    path.mkdir(parents=True, exist_ok=True)
    with (path / "decisions.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")


def _row(event: dict, kind: str, **extra) -> dict:
    return {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "plugin": PLUGIN,
        "kind": kind,
        "session_id": str(event.get("session_id") or ""),
        "agent_id": str(event.get("agent_id") or ""),
        "tool_name": str(event.get("tool_name") or ""),
        "hook_event": str(event.get("hook_event_name") or ""),
        **extra,
    }


def note_session(event: dict, clause_count: int, root=None) -> None:
    """Record ONCE per session that Gyroscope was live, and with how many clauses.

    A marker file per session id is the whole mechanism. An unwritable marker degrades to
    re-noting -- noisy, still correct -- never to silence and never to raising.
    """
    try:
        session = str(event.get("session_id") or "")
        if not session:
            return
        path = _root(root)
        seen = path / "sessions"
        seen.mkdir(parents=True, exist_ok=True)
        key = "".join(c if c.isalnum() or c in "-_" else "_" for c in session)[:96]
        marker = seen / key
        if marker.exists():
            return
        marker.write_text("")
        _append(_row(event, "session", clauses=int(clause_count)), root=root)
    except Exception:
        pass


def note_deny(event: dict, clause_id: str, subject: str, reason: str, root=None) -> None:
    """Record a PreToolUse refusal, naming the clause and the subject it discharges on."""
    try:
        _append(_row(event, "deny", clause_id=clause_id, subject=subject[:200],
                     reason=reason[:400]), root=root)
    except Exception:
        pass


def note_block(event: dict, open_count: int, clause_ids, root=None) -> None:
    """Record a terminal reconciliation block."""
    try:
        _append(_row(event, "block", open_count=int(open_count),
                     clause_ids=[str(c) for c in list(clause_ids)[:10]]), root=root)
    except Exception:
        pass


def note_fault(event: dict, stage: str, detail: str, *, failed_closed: bool, root=None) -> None:
    """Record an event that could not be evaluated, and which way it fell.

    `failed_closed` is not decoration: it is what makes the suite's fail-direction policy auditable
    rather than merely documented. Gyroscope's answer is split by design -- carriage open, decision
    closed -- and this field is where that split becomes a fact somebody can count.
    """
    try:
        _append(_row(event, "fault", stage=stage, detail=detail[:400],
                     failed_closed=bool(failed_closed)), root=root)
    except Exception:
        pass


def note_repair(event: dict, repaired: int, root=None) -> None:
    """Record that the envelope carried bytes repaired before it could be read.

    Distinct from `fault`: the event WAS evaluated, on a repaired payload. Conflating them would
    inflate the count of unevaluated calls, the one number this log exists to keep honest.
    """
    try:
        _append(_row(event, "repair", repaired=int(repaired)), root=root)
    except Exception:
        pass
