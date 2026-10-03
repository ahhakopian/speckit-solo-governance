## Greenfield Governance — Converge Addendum

Apply this addendum in addition to the core command. Perform the final
compatibility check across these three levels:

1. Feature-local artifacts and implementation;
2. the approved `architecture/baseline.md`;
3. the originating `ROADMAP.md` entry's architecture responsibility and
   dependencies.

Report the result of each level and whether the implementation preserves the
Canonical PRD. Report a final classification of `COMPATIBLE` or
`BASELINE_CHANGE_REQUIRED`.

Release may proceed only when all three levels pass, the Canonical PRD is
preserved, and the final classification is `COMPATIBLE`. A
`BASELINE_CHANGE_REQUIRED` result blocks release until Controlled Architecture
Change completes and the Feature reconverges. Route a product conflict to the
Canonical PRD rather than resolving it in convergence.

Also determine from both Feature intent and the actual implementation whether
user-facing UI was materially changed. For material UI, require current
rendered evidence in the target runtime for the affected flow or states and
representative viewport or device classes as appropriate. For browser-based
surfaces, rendered browser evidence satisfies this requirement. Evaluate only
against applicable authority: reconciled `spec.md`, relevant upstream product
constraints, applicable `DESIGN.md`, applicable
`specs/<feature>/ux-design.md`, the exact established-pattern authority
recorded in `plan.md` when applicable, and applicable surface-specific decisions.
Do not turn this focused check into a full product re-audit.

When `specs/<feature>/ux-design.md` applies, current rendered evidence must
cover its affected user-facing states. Choose specialist review as follows:

- Invoke: **Use the installed Impeccable critique capability for the affected Feature and surfaces.** when `ux-design.md` applies, UX/interaction quality is materially at risk, or the change is a substantial new or redesigned surface. With an applicable `ux-design.md`, critique of the current rendered implementation is mandatory regardless of risk classification. Focus on conformance to that artifact and applicable `DESIGN.md` rules, and on whether the rendered interaction and visual hierarchy are acceptable.
- When accessibility, responsiveness, theming, performance, or implementation
  integrity is materially at risk, or the change is a substantial new or
  redesigned surface, invoke: **Use the installed Impeccable audit capability for the affected Feature and surfaces.** An applicable `ux-design.md` alone does not require audit.

If a required named capability is unavailable or cannot run, stop convergence
and report the missing capability; do not perform availability detection or
substitute generic UX reasoning. Material findings block convergence until
resolved. For a material critique finding, fix the affected UI implementation
or design-conformance issue, recheck the affected rendered state, and rerun
critique before Converge can succeed. If critique shows that the approved
`ux-design.md` itself needs revision, stop Converge and return to Plan/UX
shaping; do not redesign the interaction inside Converge. After other material
fixes, reverify the affected behavior. Polish is optional and finding-driven.
Do not require a review artifact merely to prove that review occurred. The
UX/UI conditions must pass before returning the existing final `COMPATIBLE`
classification.

Report the native outcome (`converged` or `tasks_appended`) and exactly one
Greenfield classification (`COMPATIBLE` or `BASELINE_CHANGE_REQUIRED`). Do not
modify ROADMAP in this command: the Greenfield-owned mandatory hook evaluates
completion from current artifacts, its own current compatibility check, and
fresh installed governance reviews.

For `tasks_appended`, the mandatory hook returns without clean-completion
verification and leaves the Feature active. Return control to the caller so
the changed task set goes through governed Tasks reconciliation, its mandatory
Guard, approval, Readiness and implementation again. Do not continue to Human
Acceptance or Complete. Preserve all existing task IDs and completion markers,
implementation and evidence; Core's append-only corrective-task contract applies.

Completion verification is reusable and does not mutate ROADMAP. With explicit
`completion_mode: human`, the hook leaves the Feature active for Human
Acceptance when current acceptance is missing or stale. Current acceptance
allows the hook to return without another acceptance stop; only separately
authorized completion applies DONE. Automatic
completion remains the default. All compatibility and UX/UI conditions above
remain unchanged in either mode.
