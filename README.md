# Gyroscope

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/gyroscope-hero-dark.png">
  <img src="docs/img/gyroscope-hero-light.png" alt="Gyroscope — do not let the session derail irreversibly">
</picture>

**One purpose: do not let the session derail irreversibly.**

## The problem

Some mistakes fix themselves if you just keep working. Others don't. An agent that force-pushes
over a remote branch it never fetched, deletes a build directory nobody inventoried, or declares
a task done while the tree is dirty has not just erred — it has destroyed the evidence needed to
notice the error. No later step corrects it, because the material a correction would need is
gone. The only exit is a restart that throws away everything the session accumulated.

What makes these failures dangerous is that they are the *default*. The cheap check that would
catch them — a `git fetch` before the force-push, a `git status` before declaring done — takes
effort and is exactly the kind of step a busy session forgets. Doing nothing produces the
unhealing outcome; only remembering produces the safe one. Gyroscope's internal name for that
shape is **asymmetry**: the harm needs no author, only the absence of one. The worst case is the
green check — greenness is what ends the run, so a wrong "it passed" doesn't merely fail, it
consumes the opportunity to notice.

## How it heals: reversal

Gyroscope swaps which outcome is free. The costly call is denied until the cheap check it
depends on is *observed on record*; once it is, the same call runs. Forgetting now produces the
safe outcome instead of the unhealing one:

| | the costly call | the cheap check |
|---|---|---|
| before | free — it just runs | takes effort, and is forgotten |
| after | costs one cheap call on record | free — denial is the resting state |

This is a repricing, not a prohibition: both outcomes stay reachable, the cost assignment is
swapped, nothing is added. And its failure mode is loud rather than silent — the thing you
wanted requires an artifact that is either there or is not.

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
