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

## Why a gyroscope

A session is a flow — the default toward *proceed, it looks complete, keep going* reasserts at
every turn, not once at entry, so one instruction at the entrance is spent by turn three. What
holds a flow is a gyroscope: spun up once and then continuously present, opposing drift with
matched force at every moment, requiring no attention and no trigger. It does not choose the
direction — it prevents tumbling off the axis you set. That is why this is a hook registered on
every event rather than something that runs at session start, and why there is a ledger: the
ledger is the stored state that keeps the gyroscope spun up across turns, so each turn inherits
the opposition instead of re-earning it.

## The mechanism

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/ledger-flow-dark.png">
  <img src="docs/img/ledger-flow-light.png" alt="A costly call is denied and recorded as a demand; the cheap guard discharges it; the same call then executes; Stop blocks while demands stay open">
</picture>

A `PreToolUse` deny records a **demand**; a later call matching the clause's guard records a
**discharge**; at `Stop` anything still open blocks. That is the whole model — the nine things
that looked like separate Stop checks are one ledger read
([`gyroscope/ledger.py`](plugin/gyroscope/ledger.py) states this where the mechanism is defined).
A licence is an **observed discharge**, never an absent demand — the absence of evidence is never
treated as permission. Four properties of the ledger, each stated in the code it constrains:

- **Obligations are un-windowed within a session.** A promise does not expire because an hour
  passed; events may be windowed for cost, demands never are.
- **Absence is not a pass.** An empty ledger at Stop means nothing was recorded, which is not the
  same as nothing being owed — it is NOT-EVALUABLE. A shipped verifier once scored an *absent*
  check better than an empty one, and that inversion is the defect the ledger refuses to repeat:
  with the clause directory emptied, `rm -rf build/` was ALLOWED and Stop returned `{}` — a clean
  bill of health from a gate that checked nothing — so a zero-clause load now blocks Stop rather
  than passing it.
- **The hash chain detects corruption, not forgery.** The ledger is written by the same agent it
  constrains. The chain detects accidental corruption, a truncated write, bit-rot; it does NOT
  detect deliberate forgery — anyone who can append to the ledger can append a matching hash. No
  mechanism inside this trust boundary can do better.
- **A measured scoping limit (2026-08-14, observed, not theorised).** A nested `claude -p`
  invocation reported the SAME `session_id` as the session that launched it, with `agent_id`
  empty. Scope is keyed on `(session_id, agent_id)`, so a nested run shares its parent's ledger
  and the parent can be blocked at Stop by a demand the child raised. The keying is correct for
  the ids the host supplies — it cannot separate threads the host does not distinguish. Recorded
  rather than papered over, because a scope that silently pools is worse than one that says it
  pools.

This package carries two arms:

- **`plugin/`** — the dispatcher (`gyroscope/`), the shipped clause table
  (`gyroscope/clauses.json`, 24 admitted clauses), the POSIX shim (`hooks/dispatch.sh`), and hook
  manifests for both supported hosts. Every fingerprint is an exact predicate over command, tool,
  or path identity — no clause infers intent from prose. The hook fails open: if the dispatcher
  cannot run, it stays silent rather than blocking the host.
- **`skill/`** — `SKILL.md` plus session hooks, wired via `hooks/settings.fragment.json`. This
  arm covers the guards that leave no mark in a call sequence (clarify before committing to a
  plan, confirm a checker can fail, run the entrypoint a user runs);
  `gyroscope-sessionstart.sh` prints `SKILL.md` into context at session start.

### Install

- **Claude Code** — `hooks/hooks.json` is already the right shape; the bundle registers via
  `.claude-plugin/plugin.json`. Zero extra action.
- **Codex** — copy `hooks/hooks.codex.json` to the location Codex reads (`.codex/hooks.json` in a
  project).

### Manual bypass

If serialized `tool_input` contains `gyroscope-allow:` followed by non-whitespace text,
`PreToolUse` returns an empty decision before evaluating any clause.

## Honest limitations

Limits before capability claims — read these before the clause table below.

- **The ledger constrains an honest-but-forgetful agent, not a forging one.** Its hash chain
  detects altered rows and broken or missing hashes, but not deletion of a valid tail; a writer
  able to forge rows can recompute hashes.
- **A licence is scoped to its clause and session** — one observed guard licenses later
  matching calls for that clause anywhere in the same session, not just against the same file,
  branch, or command.
- **A discharge records that the guard was invoked, not that it succeeded.** Except for
  `C08-check-can-fail`, which requires an observed nonzero exit from the checker, discharge
  predicates match the guard's command text at `PreToolUse`/`PostToolUse` — a guard command that
  fails, or names a tool this repository does not have, still discharges.
- **It does not judge prose.** Every fingerprint is an exact predicate over command, tool, or
  path identity; a clause that would need to infer intent from a command string is not admitted.
- **The denial is verified; the behaviour change is not.** "Prevented" here means exactly one
  thing: a matching costly call is denied before it executes, and that firing is deterministic —
  the corpus replay below proves the dispatcher denies at or before the derailment event in every
  authored fixture. What remains unmeasured is what a live agent does *after* the denial: whether
  it discharges the guard and retries, or routes around it. Built and mechanism-verified is not
  live-model measured; the replay proves where the dispatcher fires, not what an agent does about
  it.

## What Gyroscope writes down

`obligations.jsonl` is a **ledger**, not a log: it records outstanding obligations, so a session in
which every clause passed leaves nothing behind — and so does a session in which the plugin never
ran. "Did Gyroscope catch anything?" therefore had no answer at all. Not "no": *unanswerable*,
which is indistinguishable from never-installed, and which is the same absence-reads-as-green
failure this plugin refuses to accept from a session.

`gyroscope/journal.py` closes that. It appends to `decisions.jsonl` beside the ledger: one
`session` row the first time a session is seen, carrying the loaded **clause count** — a row saying
`clauses: 0` is a gate that checked nothing while everyone believes it is on — plus one row per
`deny`, per terminal `block` (including clean reconciliations, which are a positive result a
fires-only log would erase), per `fault`, and per repaired envelope. There is deliberately no row
per allowed call.

Every row names `plugin`, `session_id`, `agent_id` and `tool_name`, and every deny and block on the
wire is now prefixed `gyroscope:`. Three plugins register `PreToolUse` and the host shows the user
a reason but never a source.

`fault` rows carry `failed_closed`, which makes Gyroscope's split direction — carriage open,
decision closed — checkable against the record rather than against its docstrings. See
[Courthouse docs/FAIL-DIRECTION.md](https://github.com/Clear-Sights/Courthouse/blob/main/docs/FAIL-DIRECTION.md).

## Where a unit gets dispatched: the rung ladder

The clause table decides whether a costly call may run. It says nothing about *who runs it*, and
that is a second unhealing default: work routed to a tier that cannot hold it fails in a way
nobody observes, because the output still looks like output. `plugin/gyroscope/routing.py` and
`plugin/prompts/routing.bindings.json` are the routing half.

**The allocation.** Codex is the workhorse: per dollar it buys far more capacity than the dear
tiers, so it holds every rung whose failure heals — a wrong bulk unit is caught by the check that
was going to run anyway, and redoing it costs another cheap unit. Intelligence is the only edge
worth paying for, and only where the failure does *not* heal. The ladder states that per rung as
`heals` and `pays_for`, and admission refuses a table that pays for intelligence on work it also
calls healing.

| rung | rank | capability | heals | pays for |
|---|---|---|---|---|
| `bulk` | 0 | mechanical breadth; many near-identical units, each cheap to redo | yes | capacity |
| `moderate` | 1 | implementation against a settled design | yes | capacity |
| `hard` | 2 | hard or novel; the judgment is the work | yes | capacity |
| `extreme` | 3 | extreme or cross-cutting; the blast radius leaves the subsystem | **no** | intelligence |
| `pivotal` | 4 | PIVOTAL and reasoning-heavy; what the rest of the run inherits | **no** | intelligence |

Order comes off `rank`, never off a name: no rung name appears in a conditional in the module, and
a table whose file order and rank order disagree is refused rather than silently sorted. Effort
sub-levels (`low`/`medium`/`high`) live inside the `bulk` rung only — dose is not capability, so it
never reorders the ladder, and it is spent smallest-first.

**Triggers fall upward.** A unit states its rung; the rung it actually stands on is the highest of
that and every live trigger's floor. So unhealing beats bulk, and nothing can pull a unit down to a
cheaper rung than it declared. The case that forces the rule is bulk verification of clauses that
are being *trusted*: it has exactly the shape of bulk work — many near-identical items, each
individually cheap — and it is not, because the output is a decision to trust. A clause wrongly
waved through is then relied on by work that will never re-run the check, so its floor is the top
rung. A unit that states no rung is refused in both directions rather than defaulted: defaulting
down buys the cheap tier for work nobody classified, defaulting up buys the dear one for all of it.

**Prove the route before dispatching to it.** The bindings file is a claim about which routes
exist, and a claim is not a destination that answers — nothing in it has been probed. `plan()` will
not return a route it has not just seen a live probe for. A probe that renders no answer is
NOT-EVALUABLE, and NOT-EVALUABLE is not permission, the same direction `clauses.match` fails.

On a dead route the trigger *and* the tier go on the record and the unit reroutes exactly **one**
rung upward — one, not straight to the top, because skipping the intermediate rungs spends the dear
tier on work a cheaper live route would have held, and the condition that killed the cheapest route
is rarely specific to one unit. When no rung above is reachable the unit stops at the top rung as
`BLOCKING` with no binding: never dispatched to a route observed dead, never quietly dropped.

**A dead route is never silently retried.** A `RouteMemo` carries buried rungs across plans in one
process, so a failure observed once is not paid for again by the next unit — and the skip is itself
recorded, citing the attempt that buried it, so *we did not try this* never reads the same as *we
tried and it worked*. The memo is process-scoped on purpose: a file would outlive the condition
that made the route dead, and a route recorded dead forever heals only if someone remembers to
delete the record.

Resolution is first-hit-wins and does not merge: `$GYROSCOPE_ROUTING_BINDINGS`, then
`<cwd>/prompts/routing.bindings.json`, then the account directory, then the packaged copy. A merge
would let a repository inherit a rung it never declared, and the rung it inherits is the one that
decides what gets paid for.

**Limits.** This is a resolver, not a dispatcher: it chooses a rung and hands back a binding, and
nothing here executes anything or measures whether the tier it chose was the right one. No clause
was added to the table for it — the shipped `clauses.json` is generated from `plugin/clauses/` in
the development repository, and hand-adding a row here would fork the artifact from its source of
truth. `tests/test_routing.py` plants a fault at each of the four seams above and requires the
named test to go red because of it.

## The shipped clause table

The dispatcher loads `plugin/gyroscope/clauses.json` — 24 admitted clauses, every one carrying
positive and negative fixtures checked at load. Two tiers, split by whether the guard is a
universal command or names environment-specific tooling.

### Portable (guards are universal commands)

| ID | Costly fate | Guard |
| --- | --- | --- |
| `A01` | `git push` with nothing on record about what is staged | `git status` first |
| `A02` | bulk delete (`rm -rf`, `find -delete`, `git clean -f`) over a set never listed | `ls`, `find` (without `-delete`), `du`, or `git status` first |
| `A03` | `git push --force` over a ref never fetched (`--force-with-lease` is exempt) | `git fetch` first |
| `C03-verify-what-returns` | Stop after delegated work returned, with no returned artifact read | a `Read` after dispatch, before stopping |
| `C08-check-can-fail` | Stop after a checker ran whose PASS may be cited as evidence | an observed **nonzero** exit from the same normalized checker invocation |
| `C09-checker-excludes-self` | infer process presence from `ps \| grep` where the checker can match itself | a listing that excludes the shell/checker PID (`grep -v $$`, awk `!=`) |
| `D01` | dispatch work to a subagent with no ground probed | a `Read`, `Glob`, or `Grep` first |
| `P01` | present a plan with nothing read from this repository | a `Read`, `Glob`, or `Grep` first |
| `P02` | present a plan whose ambiguities were settled by guessing | one `AskUserQuestion` first |
| `T01` | Stop with `git status` never run this session | `git status` at least once |
| `T02` | Stop after a push whose landing was never checked | `git fetch` or `git ls-remote` after pushing |
| `U03` | use a PID in a signal operation (`kill`, `pkill`, `killall`) | `ps` or `pgrep` first |
| `U06` | `curl -X POST/PUT/PATCH/DELETE` to an external service | an authenticated read canary (`curl -H 'Authorization: ...'`) |
| `U08` | create a signed git commit (`-S`/`--gpg-sign`) | a signer canary (`gpg --clearsign` / `--detach-sign`) |
| `U09` | `git switch`/`checkout` of a ref not known to exist | `git rev-parse --verify REF`, or creating it (`-b`/`-B`, `git branch REF`) |
| `U10` | traverse structured JSON blind (`jq .field` with no assertion) | a `jq` structure assertion (`-e`, `keys`, `type`, `has(...)`) on the same file |
| `U12` | apply a patch to unread context | `rg`/`grep` for the patch context first |
| `U13` | apply a `.patch`/`.diff` file unchecked | `git apply --check PATCH` first |
| `U19` | in-place text rewrite (`sed -i`, `perl -pi`) | `rg`/`grep` the pattern, or `cmp`/checksum the file first |
| `U20` | destructive behavior-changing mutation (`rm`, `git reset --hard`, `truncate`) | an independent behavior observer (the relevant test or probe) first |
| `U24` | publish/release (`npm publish`, `twine upload`, `cargo publish`) | the suite with warnings promoted to errors |

### Environment-specific (guards or fingerprints name repo-local tooling)

| ID | Costly fate | Guard |
| --- | --- | --- |
| `U01` | launch a nested worker (`dispatch.sh`) | `python3 tools/probe_child_capability.py --writable-home --response-transport --result-write` |
| `U02` | re-launch a nested-worker target (`dispatch.sh TARGET`) | `python3 tools/probe_child_capability.py --target TARGET --after-failure --require-change` |
| `U25` | run a scanner (`python3 *scan*.py`, scanner test suites) as an acceptance check | its prefix-distractor regression test first |

What happens when the named tooling does not exist in the current repository — read from the
dispatch code, not guessed:

- **The demand is raised anyway.** `pre_tool_use` demands whenever a clause's fingerprint matches,
  with no check that the guard is runnable here; an open demand then blocks at Stop.
- **In practice `U01`/`U02` are scoped out by their own fingerprints**, which match a
  `dispatch.sh` invocation — a repository without that launcher never triggers them.
- **`U25` is demanded anyway.** Its fingerprint is generic (any `python3 …scan….py`, or a
  `npm/go/cargo test … scanner` invocation), so a new adopter running any scanner script is denied
  and, undischarged, Stop-blocked — dischargeable only by a test invocation whose command text
  contains `prefix` or `distractor`. Per the discharge limit above, the ledger records that such a
  command was *invoked*, not that the named regression test exists or passed.

Two clause IDs in the generated [`plugin/SKILL.md`](plugin/SKILL.md) — `U05` ("mutate a filesystem
target", guarded by `test -w`) and `U18` ("write, move, or delete a filesystem target", guarded by
`realpath`/`readlink -f`) — read as colliding: their costly-fate domains overlap almost entirely.
Stated honestly rather than resolved: **neither ID is present in the shipped 24-clause bundle**
(nor are `U07`, `U11`, `U14`, `U15`, `U17`), so the dispatcher never evaluates them; the overlap
exists only in the generated skill text, which lags the shipped table. The table above is derived
from `clauses.json`, the artifact the dispatcher actually loads.

## Evidence

`python3 eval/replay.py` from the repository root replays recorded sessions through the real
dispatcher: three derailments (a push with no status on record, a force-push with no fetch, a
"done" claim over a dirty tree) each denied at or before the event where the session went wrong,
a recovery session where the same denied call passes after its guard, and a benign control that
stays silent — 5/5, standard library only, exit 0 iff every session meets its expectation.

## Why this is not a deny list

[Ward](https://github.com/Clear-Sights/Ward), a sibling plugin, is a deny list: its verdict is a
pure function of one event. For a matching costly call, Gyroscope's decision
is a function of `(event, ledger)`: it is denied before the clause's guard discharge and admitted
afterward. Gyroscope does not substitute a safer action and does not remove a fate — it changes
whether the *same* call executes now or waits until its licensing evidence exists.

## Siblings

Gyroscope is one of three engines that split one taxonomy — act, sequence, statement — and share
nothing else. All three install from the [Courthouse](https://github.com/Clear-Sights/Courthouse)
marketplace: `claude plugin marketplace add Clear-Sights/Courthouse`.

| Engine | Judges | One line |
|---|---|---|
| [**Ward**](https://github.com/Clear-Sights/Ward) | the pending **act** | nothing outright bad happens |
| **Gyroscope** (this repo) | the **sequence** | a session neither capsizes nor gets lost |
| [**Makoto**](https://github.com/Clear-Sights/Makoto) | the **statement** | words aren't empty |

## License

Apache-2.0 — see [LICENSE](LICENSE).
