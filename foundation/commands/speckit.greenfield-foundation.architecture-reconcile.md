---
description: Review required Architecture reconciliation and stop at Architecture HITL.
---

# Native Architecture reconciliation

Inputs: `$ARGUMENTS` supplies `canonical_prd` and `authorization=native`.
Read `docs/governance-facts.md`. Require native authorization and validate the
current approved Canonical PRD with `scripts/governance_facts.py require prd`.
The supplied `canonical_prd` must match the validated registry identity.
Require existing `architecture/baseline.md` and `ROADMAP.md`; missing or
escaping inputs block (use the shared helper's `project_file` validation).
Stale Architecture approval is the reason for review,
not authorization to adopt a change.

Invoke the existing Controlled Architecture Change process through its human
decision boundary:

1. Classify the required change as `BASELINE_CHANGE_REQUIRED` and keep affected
   downstream work stopped.
2. Identify the exact baseline statements affected by the current approved PRD,
   the binding need, realistic compatible alternatives and material consequences.
   Preserve the PRD's product authority; a PRODUCT GAP stops at that authority.
3. Identify affected ROADMAP entries and dependencies. Scope review to the
   required change and preserve unrelated entries. Show proposed Architecture
   revisions, ROADMAP impact and required downstream revalidation in the active
   response; do not introduce a separate change or review artifact.
4. Present the proposal, alternatives and consequences for an explicit human
   Architecture decision. Stop at Architecture HITL.

This entrypoint ends before the decision. Preserve the existing baseline,
ROADMAP, approval registry and downstream artifacts byte-for-byte. Do not
publish a change, record an Architecture approval, invoke Project Ready, resume
Feature work or release. The proposal in the response is not current approved
Architecture and must not be recorded as approval of the unchanged baseline.
Adoption, rejection handling and subsequent revalidation remain governed by
the existing Controlled Architecture Change process after the human decision.
