"""Check the decisions carried by the UX/UI command contract.

These addenda are prose instructions, so tests check condition/outcome clauses
and artifact roles rather than exact sentences or line wrapping.
"""

from pathlib import Path
from unittest import TestCase

import yaml


ROOT = Path(__file__).resolve().parents[1]


def contract(path: str) -> str:
    return " ".join((ROOT / path).read_text(encoding="utf-8").split())


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


class UxUiContractTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = contract("preset/commands/speckit.plan.md")
        cls.tasks = contract("preset/commands/speckit.tasks.md")
        cls.implement = contract("preset/commands/speckit.implement.md")
        cls.converge = contract("preset/commands/speckit.converge.md")
        cls.policy = contract("docs/greenfield-governance-policy.md")
        cls.artifacts = section(cls.policy, "### UX/UI artifact ownership", "### Task decomposition and implementation")
        cls.review = section(cls.policy, "### Post-implementation UX/UI convergence", "## 16.")
        cls.readme = section(contract("README.md"), "## Conditional UX/UI lifecycle", "## Installation from GitHub")

    def test_preset_registers_existing_commands_as_append_addenda(self) -> None:
        manifest = yaml.safe_load((ROOT / "preset/preset.yml").read_text(encoding="utf-8"))
        commands = {item["name"]: item for item in manifest["provides"]["templates"]}
        for name in ("speckit.plan", "speckit.tasks", "speckit.implement", "speckit.converge"):
            with self.subTest(name=name):
                entry = commands[name]
                self.assertEqual((entry["type"], entry["strategy"]), ("command", "append"))
                self.assertTrue((ROOT / "preset" / entry["file"]).is_file())

    def test_plan_requires_feature_design_or_a_justified_pattern(self) -> None:
        self.assertRegex(self.plan, r"no material UI change.{0,90}no `ux-design\.md`")
        self.assertRegex(self.plan, r"fully determines the change.{0,160}exact pattern.{0,60}authoritative source.{0,110}affected states and interactions")
        self.assertRegex(self.plan, r"not fully determined.{0,160}`specs/<feature>/ux-design\.md` before technical planning")
        self.assertRegex(self.plan, r"changes user-observable Feature behavior.{0,100}`spec\.md` is reconciled and revalidated")
        self.assertRegex(self.plan, r"`DESIGN\.md` only when shaping produces a reusable cross-Feature UX/UI rule")

    def test_feature_artifact_has_concrete_interaction_authority(self) -> None:
        self.assertRegex(self.artifacts, r"`specs/<feature>/ux-design\.md` is REQUIRED when a Feature materially changes.{0,110}pattern does not fully determine")
        for concern in ("user-visible states", "information hierarchy", "destructive actions",
                        "progressive disclosure", "control model", "command semantics and labels",
                        "transitions between states", "error/status presentation", "keyboard",
                        "non-obstruction constraints", "acceptance-relevant rendered states"):
            with self.subTest(concern=concern):
                self.assertIn(concern, self.artifacts)
        self.assertRegex(self.artifacts, r"`DESIGN\.md` is reserved for reusable project-wide, cross-Feature UX/UI rules")
        self.assertIn("Feature-local interaction decisions belong in `ux-design.md`", self.artifacts)

    def test_tasks_preserve_design_or_stop_for_missing_decisions(self) -> None:
        self.assertRegex(self.tasks, r"required `ux-design\.md` as Feature-local design authority.{0,80}missing, STOP task generation.{0,70}Plan/UX shaping")
        self.assertRegex(self.tasks, r"valid established-pattern reuse.{0,80}exact pattern, authoritative source, and coverage justification.{0,100}without requiring a redundant `ux-design\.md`")
        self.assertRegex(self.tasks, r"Derive implementation tasks from each material interaction state and decision.{0,100}verification/evidence tasks for acceptance-relevant rendered states")
        self.assertRegex(self.tasks, r"Do not reduce concrete interaction design back to capability-only tasks")
        self.assertRegex(self.tasks, r"undetermined or the cited pattern does not fully cover it, STOP and route back to Plan/UX shaping")

    def test_implement_conforms_and_returns_new_ux_to_plan(self) -> None:
        self.assertRegex(self.implement, r"read and obey applicable project `DESIGN\.md`.{0,100}`specs/<feature>/ux-design\.md` or the exact established pattern")
        self.assertRegex(self.implement, r"`tasks\.md` decomposes this design; it does not replace or override it")
        self.assertRegex(self.implement, r"MUST NOT independently introduce or change the interaction model.{0,200}control composition")
        self.assertRegex(self.implement, r"required `ux-design\.md` is missing.{0,140}STOP the affected implementation and route back to Plan/UX shaping")
        self.assertRegex(self.implement, r"new or changed UX decision not determined by the existing design authority, STOP.{0,90}Plan/UX shaping")

    def test_capability_list_cannot_authorize_rm02_button_panel(self) -> None:
        self.assertRegex(self.plan, r"Capability-level wording.{0,100}override / disable / re-enable / remove / delete.{0,130}does not satisfy")
        self.assertRegex(self.tasks, r"capability-only tasks.{0,100}override / disable / re-enable / remove / delete")
        self.assertRegex(self.implement, r"override / disable / re-enable / remove / delete.{0,100}does not authorize.{0,70}button-per-command management UI")

    def test_converge_keeps_risk_review_without_feature_design(self) -> None:
        self.assertIn("exact established-pattern authority recorded in `plan.md`", self.converge)
        self.assertIn("exact established-pattern authority recorded in `plan.md`", self.review)
        self.assertRegex(self.converge, r"critique capability.{0,90}when `ux-design\.md` applies, UX/interaction quality is materially at risk, or the change is a substantial new or redesigned surface")
        self.assertRegex(self.converge, r"accessibility, responsiveness, theming, performance, or implementation integrity is materially at risk, or the change is a substantial new or redesigned surface, invoke:.{0,100}audit capability")
        self.assertRegex(self.converge, r"audit capability.{0,80}An applicable `ux-design\.md` alone does not require audit")
        self.assertRegex(self.review, r"audit capability.{0,100}An applicable `ux-design\.md` alone does not require audit")

    def test_converge_requires_rendered_critique_for_feature_design(self) -> None:
        self.assertRegex(self.converge, r"`specs/<feature>/ux-design\.md` applies, current rendered evidence must cover its affected user-facing states")
        self.assertRegex(self.converge, r"critique of the current rendered implementation is mandatory regardless of risk classification")
        self.assertRegex(self.converge, r"conformance to that artifact and applicable `DESIGN\.md` rules.{0,90}rendered interaction and visual hierarchy")
        self.assertRegex(self.review, r"current rendered evidence MUST cover its affected user-facing states")

    def test_converge_blocks_findings_and_returns_design_revisions(self) -> None:
        self.assertRegex(self.converge, r"required named capability is unavailable or cannot run, stop convergence")
        self.assertRegex(self.converge, r"Material findings block convergence.{0,190}recheck the affected rendered state, and rerun critique")
        self.assertRegex(self.converge, r"approved `ux-design\.md` itself needs revision, stop Converge and return to Plan/UX shaping.{0,60}do not redesign")
        self.assertRegex(self.review, r"rendered state, and rerun critique before Converge can succeed")

    def test_readme_summarizes_the_same_authority_and_review_boundary(self) -> None:
        self.assertIn("`DESIGN.md` owns reusable project-wide", self.readme)
        self.assertIn("`specs/<feature>/ux-design.md` owns concrete Feature-local interaction design", self.readme)
        self.assertIn("Without `ux-design.md`, critique remains risk-based", self.readme)
        self.assertIn("Impeccable audit remains risk-based", self.readme)
