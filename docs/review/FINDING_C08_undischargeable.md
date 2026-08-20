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

NOT ESTABLISHED: the field name the host actually sends. Capturing one real
payload requires patching the installed hooks/dispatch.sh to tee stdin; the
auto-mode classifier denied that, and the published hooks doc truncates before
the PostToolUse tool_response schema.

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

## Fix direction (NOT yet applied — needs ground truth first)

Read the field the host actually sends. Do NOT loosen the predicate so that it
passes: converting a noisy gate into a silent one is strictly worse. If the
field is genuinely absent, the honest result is NOT-EVALUABLE surfaced loudly,
not a silent discharge and not a permanent block.
