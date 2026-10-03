# SpecKit Greenfield Governance

This add-on distributes the policy in
[`docs/greenfield-governance-policy.md`](docs/greenfield-governance-policy.md)
through native SpecKit components.

- `foundation/` is the `greenfield-foundation` Extension: shared PRD,
  Architecture, ROADMAP and native Constitution/Project Ready procedures.
- `workflow/` is the `greenfield-bootstrap` Workflow package, including its
  run-local PRD transport adapter. It invokes the installed foundation commands.
  Initial readiness requires the Greenfield lifecycle Extension.
- `preset/` is the thin `greenfield-governance` Preset for `specify`,
  `clarify`, `plan`, `tasks`, `implement`, and `converge`.
- `extension/` owns the ROADMAP status evaluator and one mandatory
  `after_converge` hook.
- `bundle.yml` composes those components with the existing
  `feature-governance` Preset and `feature-governance-guard` Extension.

The Bundle owns only installable components. Canonical PRD,
`architecture/baseline.md`, `ROADMAP.md`, the Constitution, and `specs/**` are
project-owned and are not bundle assets.

MVP Governance remains an independently installed governance layer and is not
distributed or owned by this Bundle.

## Repository-native prerequisites

The shared fact contract is
[`foundation/docs/governance-facts.md`](foundation/docs/governance-facts.md).
The default project-owned registry is `.specify/governance/hitl.json`. Greenfield
ships read-only consumers and validation, not a solo router or registry writer.
It consumes an already approved Canonical PRD input without another PRD gate.
Only current human approvals and unresolved PRODUCT GAP decision facts belong
in the registry; workflow state and history are rejected.

Foundation command IDs are `speckit.greenfield-foundation.prd`,
`architecture`, `roadmap`, and `project-ready` under that same prefix. Native
installation generates integration-specific commands/skills from these sources.
The PRD command accepts `operation=review|reconcile`; Project Ready accepts
`operation=constitution|verify|prepare`. Workflow transport remains in its
existing adapter; these procedures do not discover runs.

From an initialized project with Feature Governance and MVP Governance already
installed, install these prerequisites independently of bootstrap:

```bash
specify extension add --dev ~/tools/speckit-greenfield-governance/foundation --priority 20
specify extension add --dev ~/tools/speckit-greenfield-governance/extension --priority 20
specify preset add --dev ~/tools/speckit-greenfield-governance/preset --priority 20
```

No bootstrap Workflow or Bundle is required for a repository-native caller.
Existing bootstrap installations must install the new foundation Extension
before updating the Workflow. Bundle 0.8.1 includes foundation 0.2.0, lifecycle
0.2.1, Greenfield preset 0.4.2 and bootstrap 0.5.0; Feature components remain
1.0.1 and MVP remains independently installed. This source release is tagged
`v0.8.1`.

The evaluator accepts exactly one initial authorization source:

```bash
# Existing workflow transport:
python3 .specify/extensions/greenfield-roadmap-lifecycle/scripts/roadmap_lifecycle.py initial RUN_ID
# Repository-native authorization (no workflow directory required):
python3 .specify/extensions/greenfield-roadmap-lifecycle/scripts/roadmap_lifecycle.py initial --registry .specify/governance/hitl.json
```

Both use the same promotion logic. Missing or stale native authorization never
falls back to workflow state.

Native installation scaffolds
`.specify/extensions/greenfield-roadmap-lifecycle/greenfield-roadmap-lifecycle-config.yml`:

```yaml
completion_mode: automatic
approval_registry: .specify/governance/hitl.json
```

Set `completion_mode: human` explicitly for human-authorized completion.
Existing configuration is preserved by native reinstall; absent configuration
retains automatic behavior. Invalid configuration blocks completion. In human
mode, Feature start also checks current native Project Ready authorization.

`speckit.greenfield-roadmap-lifecycle.verify` performs existing acceptance and
governance checks without ROADMAP mutation. For clean convergence the mandatory
completion hook calls it in both modes. A native `tasks_appended` outcome returns
without clean-completion verification and leaves the Feature active for the
caller's governed task/review/implementation routing. Human mode leaves the
Feature active; the hook requests the acceptance boundary only when current
acceptance is missing or stale. After current Human Acceptance,
invoke `speckit.greenfield-roadmap-lifecycle.complete` with `operation=complete`.
It repeats verification and the evaluator itself requires current acceptance,
including when called directly. There is no bypass flag. The script's `verify`
operation accepts the same check/evidence arguments as `complete` and writes
neither ROADMAP nor a lock or receipt. Its `config` operation is read-only.

Human Acceptance conservatively binds project files outside VCS/package metadata
as described in the contract. Changes there, including regenerated outputs,
can invalidate it. No guard or convergence results are persisted. Existing
rendered UX/UI evidence and review obligations are unchanged. Optional
`speckit.checklist` is applicability-driven; a native caller introduces no
checklist gate or checklist-skipped state. Specify's quality checklist remains
part of its existing contract.

Specify also permits the narrow same-active-entry, same-linked-Spec
reconciliation case using the explicit existing native Feature directory.
It preserves lifecycle identity and downstream artifacts; done entries and
different/new links remain excluded. Existing Plan and Tasks reconciliation
preserves implementation/evidence and applicable task IDs/completion markers.
No approval or stage-completion record is inferred from reconciliation.

## Regression checks

Run with Python exposing the installed SpecKit 0.16.2 package:

```bash
python -B -m unittest discover -s tests -v
```

Tests use disposable fixtures and mocked agent dispatch. Existing workflow
compatibility tests exercise the engine only inside those fixtures; they do not
start or resume an installed project's workflow.

## ROADMAP lifecycle

Greenfield Governance applies `planned → ready` after the final Greenfield
Bootstrap PROJECT READY gate or equivalent current repository-native human
approval authorizes the published ROADMAP,
`ready → active` after successful `speckit.specify`, and `active → done` after
clean, compatible `speckit.converge` plus fresh Feature Governance and MVP
Governance checks, complete tasks, and required verification. It then
reassesses direct dependents. `done` means governed Feature completion; product
release is separate. MVP Governance must be installed for completion. Existing
Feature and MVP hooks are unchanged. Automatic completion remains the default;
explicit human mode additionally requires current Human Acceptance before DONE.

Each actionable ROADMAP entry needs the following lifecycle fields; normal
dependencies require the predecessor to be `done`. Include `Start requires`
only when the ROADMAP explicitly requires an extra file-based condition.

```md
<!-- roadmap-entry: RM-01 -->
### RM-01: Establish the service contract
Status: planned
Status reason: awaiting PROJECT READY
Depends on: none
Feature spec: none

<!-- roadmap-entry: RM-02 -->
### RM-02: Use the service contract
Status: planned
Status reason: waiting for RM-01
Depends on: RM-01
Feature spec: none
Start requires: file:contracts/service-v1.md
```

The status evaluator writes only lifecycle fields. Missing or ambiguous
evidence leaves status unchanged and reports the blocker. The post-converge
hook reruns the installed guards against current artifacts; it does not claim
to retain historical guard results.

## PRD convergence in bootstrap

Every bootstrap step declares the same `timeout: 900` (15 minutes), including
nested steps and both PRD gate branches. The extracted prompt steps retain short installed-command
invocations so their timeout enforcement is preserved. SpecKit 0.16.2 enforces this timeout for
shell and prompt steps; a timeout fails the run and retains state for native
resume. Its command, gate, and control-flow implementations do not enforce the
declared timeout, so this release cannot guarantee a runtime deadline for those
step types.

`greenfield-bootstrap` records each full PRD review as structured run-local
state bound to the SHA-256 of the current Canonical PRD. A material `PRODUCT
GAP` stays unresolved through repeated reviews of unchanged content. Resume
the same run with a self-contained `prd_decision` and optional `prd_comment`;
bootstrap applies that decision to the Canonical PRD and reviews the new
revision. The validator suppresses replayed decisions and requires a real PRD
change plus a clean review to resolve the selected gap. Architecture begins
only when the latest review is clean, no gap remains unresolved, and explicit
approval is bound to that exact revision. Run-local JSON retains review,
resolution, and approval evidence; the human gate shows only the decision.

## Conditional UX/UI lifecycle

UX/UI governance applies only to a Feature that materially changes a
user-facing surface or interaction; touching frontend code alone does not
trigger it. Before technical planning, the Feature asks whether it requires a
new UX decision. An established pattern is identified and reused without
shaping only when `plan.md` names the exact reusable pattern, its authoritative
source, and why it fully determines the affected states and interactions.
Generic pattern references do not cover newly introduced states, commands,
destructive actions, hierarchy, or control composition. Otherwise the
`speckit.plan` addendum instructs the agent to use the installed Impeccable
shape capability, bounded to the current Feature and
affected surfaces. If the capability is unavailable or cannot run, planning
stops and reports the missing capability rather than substituting generic UX
reasoning.
Availability is implicit in that named-capability invocation; the overlay adds
no custom availability detection.

If shaping changes user-observable Feature behavior, `spec.md` must be
reconciled and revalidated before planning continues. Presentation-only choices
do not belong in `spec.md`. When the change needs new interaction decisions,
shaping records them in `specs/<feature>/ux-design.md` before technical planning.
The Feature-local artifact defines the affected surfaces, states, hierarchy,
actions and grouping, disclosure, controls, meaningful labels, transitions,
error/status presentation, accessibility and keyboard behavior, responsive
constraints, and acceptance-relevant rendered states as applicable. It must be
concrete enough for implementation to follow without inventing UX. No UX
artifact is required for a backend/non-UI Feature or a material UI change fully
determined by the cited established pattern.

At `speckit.tasks`, the Feature design or exact pattern recorded by Plan becomes
task input. Tasks retain concrete interaction decisions and include verification
or evidence work for acceptance-relevant rendered states. If a material change
needs `ux-design.md` and it is missing, Tasks stops and returns to Plan/UX
shaping. At `speckit.implement`, implementation reads the applicable `DESIGN.md`
and Feature design or recorded pattern directly; `tasks.md` cannot replace that
authority. Technical choices may vary within the approved interaction design.
Missing design authority or a newly discovered UX decision stops affected
implementation and returns the Feature to Plan/UX shaping. A capability list
alone does not authorize a control model or management UI layout.

During convergence, materially implemented UI needs current rendered evidence
in the target runtime. When `ux-design.md` applies, that evidence must cover its
affected user-facing states and rendered Impeccable critique is mandatory. It
checks conformance to `ux-design.md` and applicable `DESIGN.md` rules, plus the
rendered interaction and visual hierarchy. Without `ux-design.md`, critique
remains risk-based. Impeccable audit remains risk-based in either case. A
material critique finding blocks Converge until the affected UI is corrected,
the rendered state is rechecked, and critique is rerun. If the approved
`ux-design.md` itself needs revision, Converge returns to Plan/UX shaping.
An unavailable required capability blocks Converge. For browser-based surfaces,
rendered browser evidence satisfies the target-runtime evidence requirement.

Impeccable must be exposed as an installed Codex skill. Its review snapshots
are evidence, not governance authority. `DESIGN.md` owns reusable project-wide,
cross-Feature UX/UI rules only; it is not mandatory for every UI Feature.
`specs/<feature>/ux-design.md` owns concrete Feature-local interaction design
when new UX decisions are required. Optional surface artifacts hold durable
surface-local presentation details without a better authority and cannot replace
required Feature-local design. No UX review report is required. This overlay
adds no UX/UI extension, hook, workflow, command, or aggregator.

## Installation from GitHub

For repository-native Solo use, clone this repository and install its existing
Foundation Extension, ROADMAP Lifecycle Extension, and Greenfield Preset into
an initialized SpecKit project. Feature Governance and MVP Governance remain
separate prerequisites. This path uses SpecKit's native local component
installation and requires no release, tag, catalog, Bundle, or Workflow.

```bash
mkdir -p ~/src
git clone --depth 1 https://github.com/ahhakopian/speckit-solo-governance.git ~/src/speckit-solo-governance

specify extension add --dev ~/src/speckit-solo-governance/foundation --priority 20
specify extension add --dev ~/src/speckit-solo-governance/extension --priority 20
specify preset add --dev ~/src/speckit-solo-governance/preset --priority 20
```

The existing bootstrap Workflow and Bundle remain available for workflow-based
Greenfield projects. Their published distribution continues to require the
release artifacts and catalogs described below.

## Component resolution and publication

SpecKit 0.16.2 resolves Bundle component IDs through native primitive catalogs
or already-installed components; `bundle.yml` deliberately does not contain
relative paths or a custom installer. Publishing requires immutable GitHub
release artifacts and matching native catalog entries for the Workflow,
Greenfield Foundation Extension, Greenfield Preset, Greenfield lifecycle Extension,
Feature Governance Preset, and Feature Governance Extension,
then a Bundle release artifact and bundle-catalog entry.
