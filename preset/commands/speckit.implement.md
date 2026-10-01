## Greenfield Governance — Implement Addendum

Apply this addendum in addition to the core command. Before implementing a
material user-facing UI or interaction change, read and obey applicable project
`DESIGN.md` rules and the Feature-local interaction authority: either
`specs/<feature>/ux-design.md` or the exact established pattern and
authoritative source recorded with coverage justification in `plan.md`.
`tasks.md` decomposes this design; it does not replace or override it. If tasks
conflict with or omit material design decisions, reconcile the tasks against
their authority through the existing task workflow before implementing the
affected work.

Implementation may choose technical realization details that do not change the
approved interaction design. It MUST NOT independently introduce or change the
interaction model; user-visible states; information hierarchy or action
grouping; primary, secondary, or destructive action treatment; control
composition; material command semantics or labels; or state transitions.
Capability wording such as "override / disable / re-enable / remove / delete"
does not authorize implementation to choose a button-per-command management UI.

If the Feature materially requires a new UX decision but its required
`ux-design.md` is missing, or if a claimed established pattern lacks an exact
authoritative source and coverage of the affected interactions, STOP the
affected implementation and route back to Plan/UX shaping. If correct
implementation discovers any new or changed UX decision not determined by the
existing design authority, STOP the affected implementation and route back to
Plan/UX shaping; do not resolve it silently in code.
