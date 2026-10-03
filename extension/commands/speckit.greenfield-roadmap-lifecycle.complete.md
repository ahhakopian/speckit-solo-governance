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
   For `operation=hook`, read the native Converge outcome from this active
   response before invoking completion verification. If it is `tasks_appended`,
   invoke `roadmap_lifecycle.py hook <ID> --converge tasks_appended` using the
   installed script path above, report its unchanged active result, and return
   control to the caller's repository-derived task routing. Do not invoke the
   clean-completion verifier, request acceptance, or execute Complete on this
   branch. Missing/uncertain outcomes block; only `converged` continues below.
   Explicit `operation=complete` still requires clean convergence and all checks.
2. Invoke the installed `speckit.greenfield-roadmap-lifecycle.verify` command
   using the normal agent invocation. Require its current successful result
   (`ready_for_acceptance: true`) and retain its flags/evidence only in this active response. Never synthesize
   PASS from an earlier approval or a clean Converge message alone.
3. For operation `hook`, invoke the installed evaluator's `hook <ID>` with
   precisely the verifier's current flags and evidence. In human mode it
   repeats the clean-completion checks and validates current Human Acceptance
   against that evidence. If `human_acceptance_required` is true, report
   `HUMAN ACCEPTANCE REQUIRED` to the caller's prescribed boundary. If false,
   return the verified result without another acceptance stop so the caller
   can invoke separately authorized `operation=complete`. ROADMAP remains
   active in either human-mode case. Do not request approval or write a fact
   from this hook. In automatic mode this operation applies existing completion.
   Report its result and end this hook invocation.
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
