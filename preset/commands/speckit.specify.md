## Greenfield Governance — Specify Addendum

Apply this addendum in addition to the core command. A new Feature may be
specified only from a ready, unblocked `ROADMAP.md` entry. The only active-entry
exception is reconciliation of the same entry's existing linked `spec.md`.
Identify that entry
in `spec.md` and keep the Feature within its outcome, scope boundary,
architecture responsibility, dependencies, and the approved
`architecture/baseline.md`.

Before Core's pre-execution hooks or directory/template setup, resolve the supplied `roadmap_entry`
and explicit `SPECIFY_FEATURE_DIRECTORY` against ROADMAP and native Feature
context. For an active entry, require that the current native directory is
that explicit directory, its existing `spec.md` is the entry's unique Feature
spec link, and its exact `ROADMAP entry: <ID>` identifies that same active
entry. Any different entry, new directory/link, ambiguous context or done
entry is rejected. Do not reset status, allocate a Feature, run branch-creation
hooks, copy a fresh template over the Spec, or replace `.specify/feature.json`
in this case. Read the existing Spec before editing and reconcile it in place
against current governing authorities, retaining applicable local requirements
and the existing identity/link. Run the ordinary specification quality review
on the reconciled Spec. Preserve Plan, Tasks, task IDs/completed markers,
implementation and evidence. This exception does not change new-Feature rules
or reopen a done Feature.

Classify any material issue by the authority that must change, and stop rather
than resolving it in the Feature:

- New or changed product scope, capability, actor, authority, ownership, or
  product boundary: return it to the Canonical PRD.
- A material change to approved architecture: report
  `BASELINE_CHANGE_REQUIRED` and stop for Controlled Architecture Change.
- A change only to Feature decomposition, boundary, dependency, or ordering:
  escalate it to `ROADMAP.md`.

Only Feature-local detail that is consistent with all upstream authorities may
be added to `spec.md`.

Use the exact line `ROADMAP entry: <ID>` in `spec.md`. After the core command
has successfully written and validated the specification, invoke
`python3 .specify/extensions/greenfield-roadmap-lifecycle/scripts/roadmap_lifecycle.py
start <ID> <project-relative-path-to-spec.md>`. The evaluator verifies the
entry is uniquely ready, the spec names that ID exactly once, its quality
checklist has no open item, and its prerequisites still hold. Report the
result. For the same active entry and linked Spec, the existing evaluator
returns the idempotent active result without changing ROADMAP; specification
identity and quality validation above must still pass before invoking it.
A failed or ambiguous specification must not change ROADMAP. No
additional lifecycle hook is needed for `specify`.
