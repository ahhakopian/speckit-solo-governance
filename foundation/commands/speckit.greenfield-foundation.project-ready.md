---
description: Prepare the native Constitution and verify PROJECT READY.
---

# Greenfield Project Ready

Inputs: `$ARGUMENTS` supplies `canonical_prd`, authorization source and
`operation=constitution|verify|prepare` (default `prepare`).
For repository-native callers read `docs/governance-facts.md`, require current
`prd` and `architecture` authorization and an explicitly Approved baseline.
This command does not grant Project Ready approval or promote ROADMAP.

## Constitution (operation=constitution or prepare)

Invoke the installed native `speckit.constitution` command using its normal
agent invocation, with precisely this governed request:

Create or update the project Constitution using the governed Canonical PRD at the supplied canonical_prd, the Approved Architecture Baseline at architecture/baseline.md, and ROADMAP.md as context. Include only durable cross-cutting invariants that genuinely govern multiple Features. Do not copy or replace product scope, actors, capabilities, authority, ownership, or product boundaries from the PRD; architecture components, contracts, state ownership, trust boundaries, or topology from the baseline; or Feature decomposition, dependencies, order, responsibility, or status from ROADMAP.md. Write only the native .specify/memory/constitution.md output and do not start Feature work.

## Verification (operation=verify or prepare)

Perform a read-only PROJECT READY verification. Read the governed
Canonical PRD at the supplied `canonical_prd`,
`architecture/baseline.md`, `ROADMAP.md`, and
`.specify/memory/constitution.md`.

Report `PROJECT READY` only if the PRD gate has no PRODUCT GAP, the
baseline is explicitly Approved and compatible with the PRD, ROADMAP.md is
actionable and dependency-aware and derived from both authorities, the
Constitution contains only cross-cutting invariants and was produced by
native SpecKit, and no unresolved conflict exists among these sources.
Otherwise report `BLOCKED`, identify each blocking issue and its owning
source, and instruct the operator to reject the final gate. Do not modify
or create any file.
Begin the response with exactly `PROJECT READY` on its own line when
verification passes, or `BLOCKED` on its own line otherwise. The final
gate must be rejected when this step reports BLOCKED.

Optional `speckit.checklist` is not required merely because a solo route
exists. Do not persist a checklist-skipped fact. This does not waive existing
specification quality checks or applicable acceptance checks.
