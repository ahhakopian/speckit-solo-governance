---
description: "Verify governed completion and apply the authorized ROADMAP transition"
---

# Greenfield ROADMAP completion

Run as the mandatory `after_converge` hook, or explicitly for the current
Feature after Human Acceptance. `$ARGUMENTS` may specify `operation=complete`;
the default is `operation=hook`. Do not edit Feature artifacts, product scope,
the approved architecture, ROADMAP structure, ordering or dependencies.

1. Read effective configuration with
   `python3 .specify/extensions/greenfield-roadmap-lifecycle/scripts/roadmap_lifecycle.py config`.
   Invalid configuration blocks completion; do not substitute automatic mode.
2. Invoke the installed `speckit.greenfield-roadmap-lifecycle.verify` command
   using the normal agent invocation. Require its current successful result
   (`ready_for_acceptance: true`) and retain its flags/evidence only in this active response. Never synthesize
   PASS from an earlier approval or a clean Converge message alone.
3. When `completion_mode` is `human` and operation is `hook`, stop after
   successful verification with `HUMAN ACCEPTANCE REQUIRED`. ROADMAP remains
   active. The caller owns the prescribed Human Acceptance boundary. Do not
   request another approval from this hook and do not write an approval fact.
4. Otherwise invoke
   `python3 .specify/extensions/greenfield-roadmap-lifecycle/scripts/roadmap_lifecycle.py complete <ID>`
   with precisely the verifier's current flags and evidence paths. The script
   independently enforces configured Human Acceptance, identity, dependencies,
   tasks and evidence. It has no option to bypass human mode. Report its JSON
   result, including affected dependents. Missing or stale acceptance leaves
   ROADMAP unchanged.

Automatic mode retains existing post-Converge completion. Explicit human-mode
completion repeats verification against current content; unchanged acceptance
needs no additional human decision. Required UI/runtime review is owned by the
shared verifier and the existing Converge addendum.
