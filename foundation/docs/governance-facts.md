# Repository-native Greenfield facts, version 1

This is the shared interface for Greenfield foundation and lifecycle callers.
It is independent of the bootstrap workflow. `scripts/governance_facts.py`
validates and fingerprints facts without writing them. The caller owns human
interaction and registry storage; no solo router or registry writer is shipped
here.

The default project-owned registry is `.specify/governance/hitl.json`. It must
survive component reinstall/removal. Approval is an explicit human declaration
bound to content, not cryptographic proof of an approver. These validators do
not infer approval from file existence, status text, process exit success or a
verification result alone.

## Registry shape

Exactly these root fields are accepted:

| Field | Value |
|---|---|
| `schema_version` | Integer `1` |
| `canonical_prd` | Canonical project-relative PRD file path |
| `prd_revision` | SHA-256 of the current fully reviewed PRD, or the already approved input |
| `product_gaps` | Current unresolved PRODUCT GAP objects; empty when none |
| `approvals` | Current approval objects; replace the same boundary/subject rather than appending history |

No run identity, workflow status, current stage, review history, pending action,
checkpoint or checklist-skipped record is permitted. A review fingerprint is
current decision evidence; it is not a stage cursor. The registry is not a
product authority: the PRD remains the only product source of truth.

Each approval has exactly:

| Field | Value |
|---|---|
| `boundary` | Lowercase boundary identifier |
| `subject` | `foundation`, or the exact ROADMAP Feature ID for Human Acceptance |
| `decision` | `approve` or `reject` |
| `human` | Boolean; authorization requires `true` |
| `verification` | `PROJECT READY` for Project Ready; `PASS` for other Greenfield approvals |
| `inputs` | Unique project-relative file paths |
| `fingerprint` | Fingerprint returned by the shared helper for these inputs and subject |

Other caller-owned HITL boundary identifiers may share this storage shape.
Greenfield validates semantics only for `prd`, `architecture`, `project-ready`
and `human-acceptance`. They must not be treated as remembered stages.

## Required authorities and freshness

`prd` binds exactly the Canonical PRD. An already approved Canonical PRD is an
input declaration: importing that explicit human declaration creates no new
PRD approval gate. Changed PRD content invalidates it. An unresolved PRODUCT
GAP blocks every Greenfield authorization.

`architecture` binds the PRD and `architecture/baseline.md`. It requires current
PRD approval. The exact single baseline bookkeeping line `Status: Draft` or
`Status: Approved` is excluded from hashing so publication can adopt the
approved draft without changing the authorized architecture content.

`project-ready` binds those authorities plus `ROADMAP.md` and
`.specify/memory/constitution.md`. It requires current PRD and Architecture
approval and exactly one `Status: Approved` baseline line. Its human approval
may be recorded only after the shared Project Ready procedure reports
`PROJECT READY`, with a native-produced/reconciled Constitution and no conflict.
The fact does not substitute for that semantic verification.

ROADMAP `Status:`, `Status reason:` and `Feature spec:` lines are excluded from
authority fingerprints. They are evaluator-owned bookkeeping. Entry identity,
scope, responsibilities, dependencies, order and start conditions remain bound.
Changing a lifecycle field does not itself grant authorization or bypass the
evaluator's status/prerequisite checks.

`human-acceptance` binds the foundation authorities, linked `spec.md`, adjacent
`plan.md` and `tasks.md`, and every required evidence file passed to completion.
It requires current foundation approvals. To avoid omissions, additions,
deletions and clean committed implementations escaping acceptance, version 1
also conservatively hashes the whole project file tree outside `.git`,
`.specify` and the evaluator's transient lock/temp files. Explicitly listed
inputs inside `.specify` are still hashed. Applicable UX authority elsewhere in
the project is therefore bound too. Repositories should keep transient build
outputs outside this acceptance tree when possible; a changed output inside
the tree invalidates acceptance. There is no persisted implementation manifest
or convergence result store.

The acceptance subject must match the evaluator-selected ROADMAP entry. The
evaluator independently checks linked spec identity, tasks, evidence and
prerequisites. Approval never replaces fresh installed governance reviews.

## Read-only helper interfaces

From a project root, using the installed helper:

```bash
python3 .specify/extensions/greenfield-foundation/scripts/governance_facts.py require prd
python3 .specify/extensions/greenfield-foundation/scripts/governance_facts.py require architecture
python3 .specify/extensions/greenfield-foundation/scripts/governance_facts.py require project-ready
python3 .specify/extensions/greenfield-foundation/scripts/governance_facts.py require human-acceptance --subject RM-01 --spec specs/001-feature/spec.md
```

All support `--project` and `--registry`. `fingerprint <boundary>` computes a
fingerprint using repeated `--input` paths and the same optional subject/spec.
It grants no approval. Python callers may use `fingerprint`, `validate_facts`
and `require_approval` directly. Missing, rejected, stale, incomplete or
ambiguous facts fail closed. Inputs cannot escape the project through paths or
symlinks. A selected native source never falls back to a workflow source.

## Current unresolved product decisions

Each `product_gaps` object has exactly the shared review fields `gap_id`,
`question`, `options`, `recommended_option`, `rationale`, plus
`discovered_on_revision` (SHA-256) and `status: unresolved`. IDs and questions
use the existing PRD submission validation and rediscovery rules.

`scripts/prd_governance.py` accepts `--prd`, `--facts`, `--submission` and
`--review-start-revision`, with optional `--project` and `--resolution`.
Submission is the existing `{verdict: CLEAN|PRODUCT_GAP, gaps: [...]}` contract.
Its output is the updated current registry object; it writes no file.

A transient resolution object contains exactly `gap_id`, `from_revision`,
`decision` and `human: true`. It names one currently unresolved question and
the previous reviewed PRD revision. The shared reconciliation rule clears that
gap only after the explicit decision changes the PRD and a full review of the
new revision no longer finds it. Unchanged content, a CLEAN claim alone, or a
replayed answer for another gap cannot clear it. Resolved gaps are removed;
there is no resolution or review history in native facts.

The bootstrap adapter uses the same submission/reconciliation functions while
retaining its existing run-local ledger, replay protection and workflow gates.
Its legacy history stays in the legacy transport, never in this registry.

## Optional checklist

An optional `speckit.checklist` invocation is governed by Feature applicability,
not by the existence of a solo caller. No checklist-skipped fact is allowed.
The existing Specify quality checklist and applicable acceptance checks remain
required under their existing rules.
