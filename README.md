# Gyroscope

**One question: is this costly call licensed by a cheap call already on record?**

Gyroscope denies a costly tool call until evidence — the *same* action, once its guard is on
record. A `PreToolUse` deny records a **demand**; a later call matching the clause's guard records
a **discharge**; at `Stop` anything still open blocks. A licence is an **observed discharge**,
never an absent demand.

This repository is the built runtime package, produced from the development repository's
packaging script (executable closure only — no development evidence). It contains two arms:

## `plugin/` — the hook arm

The dispatcher (`gyroscope/`), the shipped clause table (`gyroscope/clauses.json`, 24 admitted
clauses), the POSIX shim (`hooks/dispatch.sh`), and the hook manifests for both supported hosts.

The two hosts require **different manifest shapes**:

- **Claude Code** — `hooks/hooks.json` is already the right shape; the bundle registers via
  `.claude-plugin/plugin.json`. Zero extra action.
- **Codex** — copy `hooks/hooks.codex.json` to the location Codex reads (`.codex/hooks.json` in a
  project). A union file carrying both shapes was tested live and does not fire on Codex.

Every fingerprint is an exact predicate over command, tool, or path identity — no clause infers
intent from prose. The hook fails open by design: a wiring fault must not block the host.

Nine clauses in the shipped table carry `_quarantine_reason` / `_conservation` metadata; that is
the register's evidence-conservation record for rows measured NOT-EVALUABLE on the frozen corpus,
conserved rather than deleted. Retired clauses themselves are excluded from this package.

## `skill/` — the session arm

`SKILL.md` plus `hooks/gyroscope-sessionstart.sh` and `hooks/gyroscope-pretooluse.sh`, wired via
`hooks/settings.fragment.json`. This arm covers the guards that leave no mark in a call sequence
(clarify before committing to a plan, confirm a checker can fail, run the entrypoint a user runs);
`gyroscope-sessionstart.sh` prints `SKILL.md` into context at session start.

## Manual bypass

If serialized `tool_input` contains `gyroscope-allow:` followed by non-whitespace text,
`PreToolUse` returns an empty decision before evaluating any clause.

## License

Apache-2.0 — see [LICENSE](LICENSE).
