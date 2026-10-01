---
description: Publish the approved Architecture Baseline and derive ROADMAP decomposition.
---

# Greenfield baseline and ROADMAP publication

Inputs: `$ARGUMENTS` supplies `canonical_prd` and authorization source.
For repository-native callers read `docs/governance-facts.md`.

Require the explicitly supplied human Architecture approval. For workflow
callers this is the preceding approved gate. For repository-native callers
validate `architecture` with `scripts/governance_facts.py require architecture`
before changing either artifact.
Because this step runs only after explicit approval, update
`architecture/baseline.md` from Draft to Approved. Preserve its approved
architecture content and revision identity; record the approval state
without inventing an approver identity. The Approved baseline is now the
sole TARGET Architecture source of truth.

Then create or update only `ROADMAP.md`, derived from the governed
Canonical PRD at the supplied `canonical_prd` and the Approved Architecture
Baseline. Make it the project Spec-of-Specs for Feature decomposition,
boundaries, dependencies and order, architecture responsibility, and
status. Each actionable entry must have a stable local ID, intended
outcome, scope boundary and relevant non-goals, assigned architecture
responsibility, meaningful dependencies/order constraints, one of
`planned`, `ready`, `active`, `blocked`, `deferred`, or `done`, and a link
to its Feature specification when one exists. Do not create Feature specs
merely to add a link.

Give each actionable entry a unique `<!-- roadmap-entry: ID -->` marker
and exactly one each of these lines: `Status:`, `Status reason:`,
`Depends on:`, and `Feature spec:`. Use `Depends on: none` for an entry
without normal dependencies and comma-separated stable IDs otherwise.
Use `Feature spec: none` until successful specification. Initialize
ordinary entries as `planned` with a specific reason, and preserve
genuinely `blocked` or explicitly `deferred` entries with their reasons.
Do not mark an entry `ready` until the approved PROJECT READY gate.
Add `Start requires: file:<project-relative-path>` only where the
approved ROADMAP explicitly requires an additional file-based start
condition; never invent one from a dependency alone.

ROADMAP dependencies must reflect product, authority, contract, lifecycle,
architecture-responsibility, or verification needs rather than shared-file
impact. Do not let ROADMAP approve new product scope or architecture.
Do not copy the PRD or baseline, create tasks, start Feature work, or
create any other artifact.

Use exactly one `Status: Approved` line on the baseline. Publication must
change only the approval bookkeeping of the approved architecture content.
Do not rerun decomposition over an active ROADMAP merely to refresh evidence;
structural changes require their existing governed decision.
