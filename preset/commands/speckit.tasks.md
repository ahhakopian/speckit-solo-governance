## Greenfield Governance — Tasks Addendum

Apply this addendum in addition to the core command. Before generating or
revising `tasks.md`, determine whether the Feature materially changes a
user-facing surface or interaction. Read applicable project `DESIGN.md` rules,
the Feature's `spec.md` and `plan.md`, and
`specs/<feature>/ux-design.md` when present.

When `tasks.md` already exists, read the current task set before task generation
and reconcile it in place against the current approved Plan/UX. Preserve task
IDs for still-applicable work and preserve their completed checkbox markers;
do not renumber existing tasks or reset progress. Retain completed-work records
when a changed requirement supersedes them, and add new corrective work as
new unchecked tasks with unused IDs. Preserve implementation and evidence.
Core's mandatory `after_tasks` Feature Governance Guard must still run on the
reconciled task set before Tasks / Guard HITL; reconciliation grants no approval.

If the material change requires a new UX decision, treat the required
`ux-design.md` as Feature-local design authority. If it is missing, STOP task
generation and route the Feature back to Plan/UX shaping; do not invent the
interaction or proceed from capability-only wording. A generic pattern claim
does not excuse a missing design artifact. If `plan.md` instead records a valid
established-pattern reuse, use its exact pattern, authoritative source, and
coverage justification as applicable design authority without requiring a
redundant `ux-design.md`. If there is no material UI or interaction change, no
UX artifact is required.

Derive implementation tasks from each material interaction state and decision
in the applicable `ux-design.md` or exact established pattern, and derive
verification/evidence tasks for acceptance-relevant rendered states. Preserve
applicable project `DESIGN.md` rules. In `tasks.md`, retain enough concrete
design detail or precise references to the governing design decisions for
implementation and verification to follow them. Where applicable, preserve:
user-visible states; information hierarchy; primary, secondary, and destructive
action distinctions; action grouping and progressive disclosure; control model;
material command labels and semantics; state transitions; status/error behavior;
focus, keyboard, and accessibility requirements; responsive and non-obstruction
constraints; and acceptance-relevant rendered states.

Do not reduce concrete interaction design back to capability-only tasks such as
"add override / disable / re-enable / remove / delete controls". Task
decomposition must not make a new UX decision. If a required interaction is
undetermined or the cited pattern does not fully cover it, STOP and route back
to Plan/UX shaping before producing the affected tasks.
