# Gyroscope C08-check-can-fail is structurally undischargeable

Severity: CRITICAL (Asymmetric — does not heal; terminal; governs every other clause)
Found: 2026-08-20, session 4804b891-21d2-51c5-87e1-950a8fc81aa6
Component: Gyroscope / plugin/clauses/C08-check-can-fail.json

## Claim

The C08 clause can be demanded but never discharged against a real Claude Code
host event. It therefore blocks every Stop, forever, regardless of what the
model does.

## Evidence (executed queries against /root/.claude/gyroscope_state/obligations.jsonl)

- C08 demand rows this session: 110
- C08 discharge rows, any agent, any subject, ever: 0
- Contrast, same ledger, same session: A02=34, C09=15, T02=7, U20=4,
  U13=2, U09=2, D01=1, A01=1, U03=1 discharges.
- Of the 24 clauses in the table, C08 is the ONLY one whose discharged_by.on
  reads a `tool_response.*` field, and the ONLY one discharging at PostToolUse.
  All 23 others read `tool_input.command` (19) or `tool_name` (4).

## Two-sided demonstration

All five open subjects were run to genuine failure as DIRECT Bash tool calls
(not nested in a driver script, so the hook observes them), against a real
planted failing test in an idle dev twin:

  cd /home/user/makoto-dev; export PYTHONPATH=...; python3 -m pytest ... -> exit 1
  cd /home/user/makoto-dev; export PYTHONPATH=...; python  -m pytest ... -> exit 1
  cd /home/user/makoto-dev; export PYTHONPATH=...; pytest        ...     -> exit 1
  cd /home/user/Ward-Dev;   export PYTHONPATH=...; python3 -m unittest ... -> exit 1
  cd /home/user/Ward-Dev;   export PYTHONPATH=...; python  -m unittest ... -> exit 1

After all five: is_licensed == False for all five derived ids; ledger holds a
`demand` row for each and zero `discharge` rows.

## Mechanism

hooks.json registers PostToolUse with matcher `Bash|Read`, and _watch_standing
runs on every event, so the dispatcher IS invoked. The guard predicate is
  {"kind": "nonzero", "event": "PostToolUse", "on": "tool_response.exit_code"}
and it never matches. The host's PostToolUse payload for Bash does not appear
to carry `tool_response.exit_code` under that spelling.

## Root cause (ESTABLISHED, from 1984 recorded tool results)

The host never sends `tool_response.exit_code`, under that or any spelling.
Measured over this session's transcript (2,279 toolUseResult records: 1,985
dict, 175 str, 119 list), across 67 distinct keys:

- A SUCCEEDING Bash call yields a dict whose keys are exactly
  `(stdout, stderr, interrupted, isImage, noOutputExpected)`, sometimes plus
  `gitOperation`, `backgroundTaskId`, or `returnCodeInterpretation`. There is
  no numeric exit-code member.
- A FAILING Bash call does not yield a dict at all. It yields a STRING of the
  form `"Error: Exit code 2\n<output>"`.

So on success the key is absent, and on failure `tool_response` is not an
object at all and cannot be traversed. `_get(event, "tool_response.exit_code")`
resolves to nothing in both directions, which is why the guard has never once
fired.

## Fix

    "discharged_by": {
      "kind": "regex", "event": "PostToolUse", "tools": ["Bash"],
      "on": "tool_response",
      "pattern": "^Error: Exit code [1-9][0-9]*\\b",
      "key_from": { ...unchanged... }
    }

`regex` on an arbitrary dotted event path is already a supported kind, so this
needs no engine change.

Also correct plugin/clauses/SCHEMA.md, which lists
`{"kind": "nonzero", "on": "tool_response.exit_code"}` among the supported
fingerprint kinds. The schema enshrines the field that does not exist, so the
next clause author reproduces this bug by following the documentation.

## Why it passed its own tests

Gyroscope-Dev/plugin/tests/test_cross_event_key.py:47 constructs the payload
it tests against:

    out["tool_response"] = {"exit_code": exit_code}

The test manufactures the very field whose existence is in question, so it is
green while the clause has never discharged once against a real event. This is
the "test never reaches live wiring" category — inside the gate that exists to
enforce that category.

## Why this is Asymmetric

Left alone it heals only by restart or not at all: the demand rows accumulate,
every Stop blocks, and the documented remedy (plant an input, run the checker
until nonzero) provably does not work. The natural end state is the gate being
switched off, which silently removes all 24 clauses' coverage at once.

## Status: FIXED (2026-08-20)

Applied in `plugin/clauses/C08-check-can-fail.json` (+ rebuilt `clauses.json`),
`plugin/clauses/SCHEMA.md`, and `plugin/tests/test_cross_event_key.py`.

The predicate was NOT loosened. It reads the field the host actually sends, and
the success payload still cannot discharge it. Two-sided proof, run against the
real engine (`gyroscope.clauses.discharges`) on both true host shapes:

| event payload                                   | fixed clause | old spelling |
|-------------------------------------------------|--------------|--------------|
| `"Error: Exit code 2\nFAILED tests/test_x.py"`  | **True**     | False        |
| `{"stdout": "2 passed", "stderr": "", ...}`     | False        | False        |
| `"Error: Exit code 0"`                          | False        | —            |
| `"Error: Exit code 130"`                        | True         | —            |

The old spelling returns False in BOTH directions on the same events: the defect
reproduced on demand rather than merely argued.

Non-string safety: `_base_predicate` returns False for a non-`str` value under
`kind: "regex"`, so the success dict is rejected by type before the pattern is
ever applied — no traversal, no exception.

The test that manufactured the field was corrected, not deleted. It tests
cross-event KEY correlation, which is a real property; it now correlates over
the payload the host actually emits, and its own
`test_the_key_equality_check_can_fail` still plants a fault in `dispatch.py` and
proves the test goes red.

### What does NOT change

A live session that already accumulated undischargeable demand rows is not
retroactively cleared by this fix — the open rows persist in
`obligations.jsonl`. The fix stops new sessions from entering the state; it is
not a migration.
