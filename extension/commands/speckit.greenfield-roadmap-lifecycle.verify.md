---
description: "Verify governed Feature completion without changing ROADMAP"
---

# Greenfield completion verification

Run for the explicitly identified current Feature, from the completion hook or
a direct caller. Do not mutate ROADMAP or grant Human Acceptance. Existing
required tests/runtime checks may produce their normal verification evidence.

1. Identify exactly one current Feature specification and its `ROADMAP entry: ID`
   line. If identity is missing or ambiguous, stop without changing ROADMAP.
2. Read the native converge outcome emitted immediately before this hook. Only
   `converged` (zero appended tasks) is clean. Independently check current
   implementation against the Canonical PRD, approved Architecture Baseline,
   and originating ROADMAP scope, responsibility, and dependencies. Apply the
   Greenfield final compatibility and conditional UX/UI rules, including
   required rendered evidence and specialist reviews for material UI. Require
   `COMPATIBLE`. The converge addendum's reported classification is supporting
   context, not a substitute for this current check. If either result is
   missing or uncertain, report that exact blocker and leave status `active`.
3. Rerun the **installed** Feature Governance review against the current
   Feature twice, once for the post-tasks checkpoint and once for the
   pre-implement checkpoint. Require the exact leading line
   `FEATURE_GOVERNANCE: PASS` on both fresh results. Rerun the installed MVP
   complexity preflight and post-implementation simplification review against
   the current artifacts; require each to report
   `MVP_COMPLEXITY_GUARD: PASS`. Missing commands, unavailable capabilities,
   `BLOCK`, `EXCEPTION_REQUIRED`, or ambiguous output block completion. Do not
   substitute a Greenfield review for any installed guard.
4. Inspect the current `tasks.md`, applicable acceptance checks, actual
   implementation, and required test/runtime evidence. Run the verification
   required by the Feature and relevant governance. Identify at least one
   existing project-relative evidence file. For material UI, include the
   current rendered evidence required by Greenfield convergence. Confirm that
   there is no unresolved product, architecture, Feature Governance, MVP, or
   Greenfield finding. A fixable missing check leaves the Feature active;
   request human input only for a genuinely new governed decision.
5. Only after all checks pass, invoke
   `python3 .specify/extensions/greenfield-roadmap-lifecycle/scripts/roadmap_lifecycle.py verify <ID>`
   with `--converge clean`, `--compatibility COMPATIBLE`,
`--feature-after-tasks PASS`, `--feature-before-implement PASS`,
`--mvp-before-implement PASS`, `--mvp-after-implement PASS`,
`--verification PASS`, `--blockers none`, and one or more
`--evidence <project-relative-path>` arguments.
   Use ordinary shell quoting for paths. Report the evaluator's JSON, the exact
   flags and evidence paths in the active response for the completion caller.
   This output is transient; do not create a guard-result or convergence ledger.

If any check fails, do not supply a PASS flag. Report the exact blocker and
leave ROADMAP unchanged. A rerun repeats the current checks. If a current native
Converge outcome is missing, BLOCK and tell the caller to invoke existing
Converge before retrying; do not invoke it from this verification command,
because automatic completion hooks may mutate ROADMAP. Do not recover a stored
stage result. Required UX/UI checks remain mandatory.
