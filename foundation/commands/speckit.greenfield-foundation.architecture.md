---
description: Derive and review a Draft Architecture Baseline from the approved PRD.
---

# Greenfield Architecture

Inputs: `$ARGUMENTS` supplies `canonical_prd` and authorization source.
For repository-native callers read `docs/governance-facts.md`.

Require current approved PRD authorization. A workflow caller supplies its
validated PRD approval; a repository-native caller must validate the `prd`
fact with `scripts/governance_facts.py require prd`. Derive and review the
TARGET Architecture from the governed Canonical PRD at
the supplied `canonical_prd`.

Create or update only `architecture/baseline.md`. Keep it visibly Draft;
it is not authoritative until the next human gate is approved and a later
step marks it Approved. Include a revision identity and enough information
to evaluate future Feature compatibility: system context and technical
boundaries; components and responsibilities; decision/state ownership;
communication, integration, and trust boundaries; validation and
authorization placement; important contracts and dependency directions;
persistence, lifecycle, migration, and compatibility rules; runtime and
deployment constraints; architectural cross-cutting constraints; and
architecture responsibility suitable for ROADMAP assignment.

Preserve the PRD exactly within its product authority. Do not silently
narrow, broaden, reinterpret, or contradict product scope, actors,
capabilities, authority, ownership, or boundaries. Distinguish evidence
from inference and avoid components or boundaries without a demonstrated
need. If a newly discovered PRODUCT GAP prevents correct derivation, do
not conceal it: keep any baseline Draft, report the blocker, and instruct
the operator to reject the approval gate and correct the Canonical PRD.

In the same step, conduct the Architecture Review. Check PRD coverage,
coherent responsibilities and contracts, authority and state ownership,
trust transitions and validation, dependencies, ROADMAP usability,
internal consistency, and implementability. Resolve ordinary reversible
design details in the draft. For every material durable or cross-Feature
decision, make realistic alternatives and consequences visible in both
the draft where operative and the active response. A recommendation may
be proposed, but it is not approved until the human gate. Do not select a
material decision silently.

Do not create an architecture-review report, ADR, traceability artifact,
Feature specification, or any file other than
`architecture/baseline.md`.

Use exactly one `Status: Draft` line for approval bookkeeping. Do not grant
Architecture approval from this command.
