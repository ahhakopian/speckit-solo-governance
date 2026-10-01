"""SpecKit 0.16.2 PRD governance regression tests using its real workflow engine."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from specify_cli.workflows.base import RunStatus, StepResult, StepStatus
from specify_cli.workflows.engine import WorkflowDefinition, WorkflowEngine, validate_workflow
from specify_cli.workflows.expressions import evaluate_expression
from specify_cli.workflows.steps.prompt import PromptStep

WORKFLOW = Path(__file__).resolve().parents[1] / "workflow" / "workflow.yml"


def gap(gap_id: str) -> dict:
    return {
        "gap_id": gap_id,
        "question": f"What should happen for {gap_id}?",
        "options": ["Use the originating context.", "Use every eligible context."],
        "recommended_option": 1,
        "rationale": "Keep the behavior scoped until a broader rule is specified.",
    }


class PrdConvergenceTests(TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.prd = self.project / "prd.md"
        self.engine = WorkflowEngine(self.project)
        self.events: list[str] = []
        self.overrides: list[dict | None] = []
        self.apply_prompts: list[str] = []

        source = WorkflowDefinition.from_yaml(WORKFLOW)
        self.assertEqual(validate_workflow(source), [])
        data = deepcopy(source.data)
        data["steps"] = data["steps"][:2]
        self.workflow = WorkflowDefinition(data, source_path=WORKFLOW)

        def fake_prompt(_step: PromptStep, config: dict, context: object) -> StepResult:
            step_id = config["id"]
            self.events.append(step_id)
            if step_id == "apply-prd-resolution":
                rendered = evaluate_expression(config["prompt"], context)
                self.apply_prompts.append(rendered)
                decision = context.steps["prepare-prd-review"]["output"]["data"]["decision"]
                before = self.prd.read_text(encoding="utf-8")
                if decision:
                    issue, separator, answer = decision.partition(":")
                    if separator and issue in {"gap-one", "gap-two"} and answer.strip() and answer.strip() != "NO_EDIT":
                        marker = f"Decision {issue}: {answer.strip()}"
                        if marker not in before:
                            self.prd.write_text(before + marker + "\n", encoding="utf-8")
                return StepResult(status=StepStatus.COMPLETED)
            if step_id == "govern-prd":
                if self.overrides:
                    submission = self.overrides.pop(0)
                else:
                    current = self.prd.read_text(encoding="utf-8")
                    issues = [name for name, marker in (("gap-one", "GAP_ONE"), ("gap-two", "GAP_TWO"))
                              if marker in current and f"Decision {name}:" not in current]
                    submission = {"verdict": "PRODUCT_GAP" if issues else "CLEAN",
                                  "gaps": [gap(name) for name in issues]}
                run_dir = self.project / ".specify" / "workflows" / "runs" / context.run_id
                if submission is not None:
                    (run_dir / "prd-review-submission.json").write_text(json.dumps(submission), encoding="utf-8")
                self.events.append("review:" + (submission["verdict"] if submission else "missing"))
                return StepResult(status=StepStatus.COMPLETED, output={"stdout": ""})
            if step_id == "derive-review-architecture":
                return StepResult(status=StepStatus.COMPLETED)
            self.fail(f"Unexpected prompt: {step_id}")

        prompt_patch = patch.object(PromptStep, "execute", fake_prompt)
        prompt_patch.start()
        self.addCleanup(prompt_patch.stop)

    def start(self, content: str):
        self.prd.write_text(content, encoding="utf-8")
        return self.engine.execute(self.workflow, {"canonical_prd": "prd.md", "integration": "auto"})

    def resume(self, state, **inputs):
        return self.engine.resume(state.run_id, inputs)

    def ledger(self, state) -> dict:
        path = self.project / ".specify" / "workflows" / "runs" / state.run_id / "prd-governance.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def architecture_reached(self) -> bool:
        return "derive-review-architecture" in self.events

    def test_stale_approval_after_new_gap_blocks_architecture(self) -> None:
        state = self.start("Purpose defined.\n")
        self.assertEqual(state.status, RunStatus.PAUSED)
        self.overrides.append({"verdict": "PRODUCT_GAP", "gaps": [gap("gap-one")]})
        state = self.resume(state, prd_gate_decision="approve")
        self.assertNotEqual(state.status, RunStatus.COMPLETED)
        self.assertFalse(self.architecture_reached())
        ledger = self.ledger(state)
        self.assertEqual(ledger["reviews"][-1]["effective_verdict"], "PRODUCT_GAP")
        self.assertIsNone(ledger["approval"])

    def test_valid_approval_binds_exact_revision(self) -> None:
        state = self.start("Purpose defined.\n")
        state = self.resume(state, prd_gate_decision="approve")
        self.assertEqual(state.status, RunStatus.COMPLETED)
        self.assertTrue(self.architecture_reached())
        digest = hashlib.sha256(self.prd.read_bytes()).hexdigest()
        ledger = self.ledger(state)
        self.assertEqual(ledger["reviews"][-1]["prd_revision"], digest)
        self.assertEqual(ledger["approval"]["approved_prd_revision"], digest)
        self.assertEqual(ledger["approval"]["review_sequence"], 2)

    def test_prd_change_after_approval_invalidates_it(self) -> None:
        state = self.start("Purpose defined.\n")
        self.prd.write_text("Purpose defined. New requirement.\n", encoding="utf-8")
        state = self.resume(state, prd_gate_decision="approve")
        self.assertNotEqual(state.status, RunStatus.COMPLETED)
        self.assertFalse(self.architecture_reached())
        self.assertIsNone(self.ledger(state)["approval"])
        # A fresh explicit approval of the new review can pass.
        state = self.resume(state, prd_gate_decision="")
        self.assertEqual(state.status, RunStatus.PAUSED)
        state = self.resume(state, prd_gate_decision="approve")
        self.assertEqual(state.status, RunStatus.COMPLETED)

    def test_gap_resolution_requires_edit_review_and_approval(self) -> None:
        state = self.start("Purpose defined. GAP_ONE remains.\n")
        self.assertEqual(self.ledger(state)["unresolved_gaps"][0]["gap_id"], "gap-one")
        state = self.resume(state, prd_decision="gap-one: use consent")
        self.assertEqual(state.status, RunStatus.PAUSED)
        self.assertIn("Decision gap-one: use consent", self.prd.read_text())
        ledger = self.ledger(state)
        self.assertEqual(ledger["reviews"][-1]["effective_verdict"], "CLEAN")
        self.assertEqual(ledger["resolved_gaps"][0]["resolved_on_revision"], ledger["reviews"][-1]["prd_revision"])
        state = self.resume(state, prd_gate_decision="approve")
        self.assertEqual(state.status, RunStatus.COMPLETED)
        self.assertTrue(self.architecture_reached())

    def test_false_clean_on_same_revision_remains_blocked(self) -> None:
        state = self.start("Purpose defined. GAP_ONE remains.\n")
        self.overrides.append({"verdict": "CLEAN", "gaps": []})
        state = self.resume(state)
        ledger = self.ledger(state)
        self.assertEqual(state.status, RunStatus.PAUSED)
        self.assertEqual(ledger["reviews"][-1]["submitted_verdict"], "CLEAN")
        self.assertEqual(ledger["reviews"][-1]["effective_verdict"], "PRODUCT_GAP")
        self.assertEqual(len(ledger["unresolved_gaps"]), 1)
        self.assertFalse(self.architecture_reached())

    def test_same_revision_rediscovery_deduplicates(self) -> None:
        state = self.start("GAP_ONE remains.\n")
        alias = gap("alternate-id")
        alias["question"] = "WHAT should happen for gap-one?!"
        self.overrides.append({"verdict": "PRODUCT_GAP", "gaps": [alias]})
        state = self.resume(state)
        ledger = self.ledger(state)
        self.assertEqual([item["gap_id"] for item in ledger["unresolved_gaps"]], ["gap-one"])
        self.assertEqual(len(ledger["reviews"]), 2)

    def test_new_gap_on_same_revision_is_additive(self) -> None:
        state = self.start("GAP_ONE remains.\n")
        self.overrides.append({"verdict": "PRODUCT_GAP", "gaps": [gap("gap-two")]})
        state = self.resume(state)
        ledger = self.ledger(state)
        self.assertEqual([item["gap_id"] for item in ledger["unresolved_gaps"]], ["gap-one", "gap-two"])
        self.overrides.append({"verdict": "CLEAN", "gaps": []})
        state = self.resume(state)
        self.assertEqual(self.ledger(state)["reviews"][-1]["effective_verdict"], "PRODUCT_GAP")
        self.assertFalse(self.architecture_reached())

    def test_product_gap_human_surface_and_audit(self) -> None:
        state = self.start("GAP_ONE remains.\n")
        output = state.step_results["record-prd-review"]["output"]["data"]
        surface = output["human_message"]
        for expected in ("Decision required", "What should happen", "1. Use", "2. Use", "Custom rule", "Recommended:", "Please choose"):
            self.assertIn(expected, surface)
        for forbidden in (state.run_id, output["prd_revision"], "git status", "resume", "govern-prd", "prd_gate_decision"):
            self.assertNotIn(forbidden, surface)
        ledger = self.ledger(state)
        self.assertEqual(ledger["unresolved_gaps"][0]["discovered_on_revision"], output["prd_revision"])
        self.assertEqual(ledger["reviews"][0]["discovered_gap_ids"], ["gap-one"])
        self.assertEqual(state.step_results["prd-product-decision"]["output"]["message"], surface)

    def test_clean_approval_human_surface_and_audit(self) -> None:
        state = self.start("Purpose defined.\n")
        output = state.step_results["record-prd-review"]["output"]["data"]
        surface = output["human_message"]
        self.assertEqual(surface, "PRD review complete\n\nNo unresolved product gaps remain.\n\nApprove this PRD as the basis for architecture?\n\nRecommended:\nApprove.\n\nPlease reply: Approve or Reject.")
        self.assertNotIn(state.run_id, surface)
        self.assertNotIn(output["prd_revision"], surface)
        self.assertEqual(self.ledger(state)["reviews"][0]["prd_revision"], output["prd_revision"])
        self.assertEqual(state.step_results["prd-governance-gate"]["output"]["message"], surface)

    def test_missing_structured_submission_fails_closed(self) -> None:
        self.overrides.append(None)
        state = self.start("Purpose defined.\n")
        self.assertEqual(state.status, RunStatus.FAILED)
        self.assertFalse(self.architecture_reached())

    def test_invalid_structured_verdict_fails_closed(self) -> None:
        self.overrides.append({"verdict": "BAD", "gaps": []})
        state = self.start("Purpose defined.\n")
        self.assertEqual(state.status, RunStatus.FAILED)
        self.assertFalse(self.architecture_reached())

    def test_debug_text_in_product_question_fails_closed(self) -> None:
        unsafe = gap("gap-one")
        unsafe["question"] += " Run ID: abc12345; git status follows."
        self.overrides.append({"verdict": "PRODUCT_GAP", "gaps": [unsafe]})
        state = self.start("Purpose defined.\n")
        self.assertEqual(state.status, RunStatus.FAILED)
        self.assertFalse(self.architecture_reached())

    def test_unchanged_prd_cannot_resolve_a_gap_after_answer(self) -> None:
        state = self.start("GAP_ONE remains.\n")
        state = self.resume(state, prd_decision="NO_EDIT")
        self.assertEqual(state.status, RunStatus.PAUSED)
        self.assertEqual(self.ledger(state)["reviews"][-1]["effective_verdict"], "PRODUCT_GAP")
        self.assertEqual(len(self.ledger(state)["unresolved_gaps"]), 1)

    def test_replayed_answer_does_not_resolve_another_gap(self) -> None:
        state = self.start("GAP_ONE and GAP_TWO remain.\n")
        state = self.resume(state, prd_decision="gap-one: use consent")
        self.assertEqual(self.ledger(state)["pending_gap_id"], "gap-two")
        state = self.resume(state)
        self.assertEqual(state.status, RunStatus.PAUSED)
        self.assertEqual(self.ledger(state)["pending_gap_id"], "gap-two")
        self.assertEqual(self.apply_prompts[-1].count("gap-one: use consent"), 0)
        self.assertEqual(self.prd.read_text().count("Decision gap-one:"), 1)

    def test_numbered_human_answer_is_bound_to_the_pending_question(self) -> None:
        state = self.start("GAP_ONE remains.\n")
        state = self.resume(state, prd_decision="1")
        self.assertEqual(state.status, RunStatus.PAUSED)
        self.assertIn("Decision gap-one: Use the originating context.", self.prd.read_text())
        self.assertEqual(self.ledger(state)["reviews"][-1]["effective_verdict"], "CLEAN")

    def test_full_review_and_apply_contracts(self) -> None:
        steps = self.workflow.steps[0]["steps"]
        review = next(step for step in steps if step["id"] == "govern-prd")
        apply = next(step for step in steps if step["id"] == "apply-prd-resolution")
        self.assertIn("speckit.greenfield-foundation.prd", review["prompt"])
        self.assertIn("speckit.greenfield-foundation.prd", apply["prompt"])
        command = (WORKFLOW.parents[1] / "foundation/commands/speckit.greenfield-foundation.prd.md").read_text()
        self.assertIn("ENTIRE current Canonical", command)
        self.assertIn("reconcile each candidate issue", command)
        self.assertIn("stable lowercase slug", command)
        self.assertIn("If the decision is blank, make no change", command)
