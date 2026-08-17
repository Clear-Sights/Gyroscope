# Gyroscope

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/gyroscope-hero-dark.png">
  <img src="docs/img/gyroscope-hero-light.png" alt="Gyroscope — do not let the session derail irreversibly">
</picture>

**One purpose: do not let the session derail irreversibly.**

The drift it opposes is the one where the DEFAULT is the unhealing issue. Not where an act
is dangerous, not where something ends badly — where *doing nothing* lands you somewhere that
does not heal. `rm -rf build/` is a moment; the state it leaves is one where the evidence of what
was there is gone, and you cannot correct what you cannot reconstruct. The worst of it is when
the correct path is unreachable without reversing the default — a green check is the pure case:
greenness is what ends the run, so investigating requires first reversing "it's green."

## How it heals: reversal

Gyroscope reverses that default. Where the session would otherwise capsize — the costly act just
runs, the cheap guard is forgotten — it makes denial the resting state, so what happens when
nobody acts is the safe fate instead of the unhealing one. The method is a repricing, not a
prohibition:

| | the costly call | the guard |
|---|---|---|
| before | free — it just runs | takes effort, and is forgotten |
| after | costs one cheap call on record | free — denial is the resting state |

Same object, two reachable fates, the cost assignment swapped, nothing added. Forgetting now
produces the safe outcome, so the rule is not defeated by ordinary forgetting, and its failure
mode is loud rather than silent: the thing you wanted requires an artifact that is either there
or is not.

## The shape: a gyroscope, not rifling

A session is a flow — the default toward *proceed, it looks complete, keep going* reasserts at
every turn, not once at entry, so a single cut at the entrance is spent by turn three. What holds
a flow is a counterweight: spun up once, continuously present, opposing drift with matched force
at every moment, requiring no attention and no trigger. That is why Gyroscope is a hook and not
an installer, why it registers on every event rather than at session start, and why there is a
ledger: the ledger is the stored state that keeps the counterweight spun up across turns.

## The mechanism

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/ledger-flow-dark.png">
  <img src="docs/img/ledger-flow-light.png" alt="A costly call is denied and recorded as a demand; the cheap guard discharges it; the same call then executes; Stop blocks while demands stay open">
</picture>

A `PreToolUse` deny records a **demand**; a later call matching the clause's guard records a
**discharge**; at `Stop` anything still open blocks. A licence is an **observed discharge**,
never an absent demand — absence is NOT-EVALUABLE, never a pass.

This package carries two arms:

- **`plugin/`** — the dispatcher (`gyroscope/`), the shipped clause table
  (`gyroscope/clauses.json`, 24 admitted clauses), the POSIX shim (`hooks/dispatch.sh`), and hook
  manifests for both supported hosts. Every fingerprint is an exact predicate over command, tool,
  or path identity — no clause infers intent from prose. Carriage fails OPEN: a wiring fault must
  not block the host.
- **`skill/`** — `SKILL.md` plus session hooks, wired via `hooks/settings.fragment.json`. This
  arm covers the guards that leave no mark in a call sequence (clarify before committing to a
  plan, confirm a checker can fail, run the entrypoint a user runs);
  `gyroscope-sessionstart.sh` prints `SKILL.md` into context at session start.

### Install

- **Claude Code** — `hooks/hooks.json` is already the right shape; the bundle registers via
  `.claude-plugin/plugin.json`. Zero extra action.
- **Codex** — copy `hooks/hooks.codex.json` to the location Codex reads (`.codex/hooks.json` in a
  project). A union file carrying both shapes was tested live and does not fire on Codex.

### Manual bypass

If serialized `tool_input` contains `gyroscope-allow:` followed by non-whitespace text,
`PreToolUse` returns an empty decision before evaluating any clause. The code does not require
the marker to occupy its own line.

## Why this is not a Ward check

Ward's verdict is a pure function of one event. For a matching costly call, Gyroscope's decision
is a function of `(event, ledger)`: it is denied before the clause's guard discharge and admitted
afterward. Gyroscope does not substitute a safer action and does not remove a fate — it changes
whether the *same* call executes now or waits until its licensing evidence exists.

## Honest limitations

- **Behaviour change is unmeasured.** Mechanism tests pass; the three-arm battery that would
  measure whether the plugin changes agent behaviour is designed, not run.
- **The ledger constrains an honest-but-forgetful agent, not a forging one.** Its hash chain
  detects altered rows and broken or missing hashes, but not deletion of a valid tail; a writer
  able to forge rows can recompute hashes.
- **No live-host result is recorded here.** Manifest generation and the unit suite do not prove a
  live Claude Code or Codex installation.
- **Licences are per clause and session/agent thread or per operand** — not per filesystem
  target, ref, or command.
- **Nine clauses carry `_quarantine_reason`/`_conservation` metadata** — the register's
  evidence-conservation record for rows measured NOT-EVALUABLE on the frozen corpus, conserved
  rather than deleted. Retired clauses themselves are excluded from this package.

## License

Apache-2.0 — see [LICENSE](LICENSE).
