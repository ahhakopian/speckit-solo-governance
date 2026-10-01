## Greenfield Governance — Plan Addendum

Apply this addendum in addition to the core command. Before tasks are produced,
evaluate the proposed design against the approved
`architecture/baseline.md` and the originating `ROADMAP.md` entry's
architecture responsibility and dependencies. Record exactly one architecture
compatibility result: `COMPATIBLE` or `BASELINE_CHANGE_REQUIRED`.

Use `COMPATIBLE` only when the design preserves the Canonical PRD, conforms to
the approved baseline, remains within the ROADMAP entry, respects its declared
dependencies, and introduces no unapproved material architecture decision.

If correct delivery needs a material baseline change, record
`BASELINE_CHANGE_REQUIRED` and stop planning and task generation until the
Controlled Architecture Change lifecycle completes. If the conflict changes
product authority, scope, ownership, or a product boundary, stop and route it
to the Canonical PRD; do not conceal it as an architecture change.

After the existing pre-plan governance and before technical planning, ask:
**Does this Feature require a new UX decision?** Determine first whether the
Feature materially changes a user-facing surface or interaction; merely
touching frontend code is not sufficient.

1. If there is no material UI change, continue ordinary SpecKit planning;
   no `ux-design.md` is required.
2. If an established UX/UI pattern fully determines the change, identify and
   reuse it. In `plan.md`, name the exact pattern and its authoritative source,
   and explain how it fully determines the affected states and interactions.
   A generic claim such as "reuse the compact panel pattern" is insufficient
   when the Feature introduces states, commands, destructive actions,
   interaction hierarchy, or control composition that the cited pattern does
   not determine. Only then continue without shaping or `ux-design.md`.
3. Otherwise invoke: **Use the installed Impeccable shape capability, bounded
   to the current Feature and affected surfaces.** If the named capability is
   unavailable or cannot run, stop planning and report the missing capability;
   do not perform availability detection or substitute generic UX reasoning.
4. Classify each shaping outcome by authority. Route product meaning or scope
   to its owning product authority. If shaping introduces or changes
   user-observable Feature behavior, stop technical planning until `spec.md` is
   reconciled and revalidated. Do not copy a purely presentational decision
   into `spec.md`.

For a material UI or interaction change that is not fully determined by an
established pattern, record the concrete Feature-local interaction design in
`specs/<feature>/ux-design.md` before technical planning continues. Define,
where applicable: affected surfaces; user-visible states; information hierarchy;
primary, secondary, and destructive actions; action grouping and progressive
disclosure; control model (such as toggle, menu, or button); user-facing command
semantics and labels where they affect understanding; transitions between states;
error/status presentation; focus, keyboard, and accessibility expectations;
responsive and non-obstruction constraints; and acceptance-relevant rendered
states. Make the interaction decisions concrete enough that implementation need
not invent them. Capability-level wording such as "override / disable /
re-enable / remove / delete" does not satisfy this requirement for a management
surface with new states or actions.

Create or update project-level `DESIGN.md` only when shaping produces a reusable
cross-Feature UX/UI rule. Record Feature-local interaction decisions in
`ux-design.md`, not `DESIGN.md`. An optional surface artifact may retain durable
surface-local presentation details, but does not replace required
`ux-design.md`. Continue with ordinary SpecKit planning only after these
conditions are satisfied. Impeccable shaping does not replace SpecKit planning,
tasks, or implementation.
