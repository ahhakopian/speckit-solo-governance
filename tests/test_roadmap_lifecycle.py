"""ROADMAP lifecycle transitions and their fail-closed boundaries."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from argparse import Namespace
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from test_governance_facts import FactFixture, facts

from specify_cli.extensions import ExtensionManifest
from specify_cli.workflows.base import RunStatus, StepResult, StepStatus
from specify_cli.workflows.engine import WorkflowDefinition, WorkflowEngine, validate_workflow
from specify_cli.workflows.steps.prompt import PromptStep


SCRIPT = Path(__file__).resolve().parents[1] / "extension" / "scripts" / "roadmap_lifecycle.py"
specification = importlib.util.spec_from_file_location("roadmap_lifecycle", SCRIPT)
assert specification and specification.loader
lifecycle = importlib.util.module_from_spec(specification)
import sys
sys.modules[specification.name] = lifecycle
specification.loader.exec_module(lifecycle)


def row(feature_id: str, status: str = "planned", deps: str = "none", *,
        reason: str = "awaiting PROJECT READY", spec: str = "none",
        extra: str | None = None) -> str:
    lines = [
        f"<!-- roadmap-entry: {feature_id} -->\n",
        f"### {feature_id}: Feature title\n",
        f"Status: {status}\n",
        f"Status reason: {reason}\n",
        f"Depends on: {deps}\n",
        f"Feature spec: {spec}\n",
    ]
    if extra is not None:
        lines.append(f"Start requires: {extra}\n")
    lines.append("Outcome: A governed result.\n\n")
    return "".join(lines)


class RoadmapLifecycleTests(TestCase):
    def setUp(self) -> None:
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.roadmap = self.project / "ROADMAP.md"
        self.write(row("RM-01") + row("RM-02", deps="RM-01"))
        state_dir = self.project / ".specify" / "workflows" / "runs" / "run-1"
        state_dir.mkdir(parents=True)
        (state_dir / "state.json").write_text(json.dumps({
            "run_id": "run-1", "workflow_id": "greenfield-bootstrap", "step_results": {
            "project-ready": {"status": "completed", "output": {"choice": "approve"}},
        }}), encoding="utf-8")

    def write(self, content: str) -> None:
        self.roadmap.write_text(content, encoding="utf-8")

    def initial(self):
        return lifecycle.apply(self.project, Namespace(action="initial", run_id="run-1"))

    def spec(self, feature_id: str = "RM-01") -> str:
        name = f"specs/{feature_id}/spec.md"
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Feature\nROADMAP entry: {feature_id}\n", encoding="utf-8")
        checklist = path.parent / "checklists" / "requirements.md"
        checklist.parent.mkdir()
        checklist.write_text("- [x] Quality checked\n", encoding="utf-8")
        return name

    def start(self, feature_id: str = "RM-01", spec: str | None = None):
        return lifecycle.apply(self.project, Namespace(
            action="start", feature_id=feature_id, spec=spec or self.spec(feature_id)))

    def complete(self, **overrides):
        evidence = self.project / "tests" / "test_feature.py"
        evidence.parent.mkdir(exist_ok=True)
        evidence.write_text("# verified\n", encoding="utf-8")
        values = dict(action="complete", feature_id="RM-01", converge="clean",
                      compatibility="COMPATIBLE", feature_after_tasks="PASS",
                      feature_before_implement="PASS", mvp_before_implement="PASS",
                      mvp_after_implement="PASS", verification="PASS",
                      blockers="none", evidence=["tests/test_feature.py"])
        values.update(overrides)
        return lifecycle.apply(self.project, Namespace(**values))

    def tasks(self, content: str = "- [x] T001 Implement feature\n") -> None:
        (self.project / "specs" / "RM-01" / "tasks.md").write_text(content, encoding="utf-8")

    def status(self, feature_id: str) -> str:
        return lifecycle.Roadmap(self.roadmap.read_text(encoding="utf-8")).entries[feature_id].fields["Status"]

    def test_initial_readiness_and_normal_dependency(self) -> None:
        result = self.initial()
        self.assertEqual((self.status("RM-01"), self.status("RM-02")), ("ready", "planned"))
        self.assertIn("waiting for RM-01", self.roadmap.read_text())
        self.assertEqual([item["changed"] for item in result["entries"]], [True, True])

    def test_initial_gate_rejection_makes_no_change(self) -> None:
        state = self.project / ".specify/workflows/runs/run-1/state.json"
        content = json.loads(state.read_text())
        content["step_results"]["project-ready"]["output"]["choice"] = "reject"
        state.write_text(json.dumps(content))
        before = self.roadmap.read_bytes()
        with self.assertRaisesRegex(lifecycle.LifecycleError, "not approved"):
            self.initial()
        self.assertEqual(self.roadmap.read_bytes(), before)

    def test_blocked_and_deferred_are_preserved(self) -> None:
        self.write(row("RM-01", status="blocked", reason="product decision needed")
                   + row("RM-02", status="deferred", reason="explicitly deferred"))
        before = self.roadmap.read_bytes()
        self.initial()
        self.assertEqual(self.roadmap.read_bytes(), before)

    def test_explicit_extra_start_condition(self) -> None:
        self.write(row("RM-01", extra="file:contracts/auth.md"))
        self.initial()
        self.assertEqual(self.status("RM-01"), "planned")
        path = self.project / "contracts" / "auth.md"
        path.parent.mkdir()
        path.write_text("# Contract\n")
        self.initial()
        self.assertEqual(self.status("RM-01"), "ready")

    def test_unsupported_start_condition_fails_closed(self) -> None:
        self.write(row("RM-01", extra="check:guess-the-rule"))
        before = self.roadmap.read_bytes()
        with self.assertRaisesRegex(lifecycle.LifecycleError, "unsupported"):
            self.initial()
        self.assertEqual(self.roadmap.read_bytes(), before)

    def test_successful_specify_sets_link_and_active(self) -> None:
        self.initial()
        self.start()
        entry = lifecycle.Roadmap(self.roadmap.read_text()).entries["RM-01"]
        self.assertEqual(entry.fields["Status"], "active")
        self.assertEqual(entry.fields["Feature spec"], "specs/RM-01/spec.md")

    def test_failed_or_ambiguous_specify_makes_no_change(self) -> None:
        self.initial()
        name = self.spec()
        path = self.project / name
        before = self.roadmap.read_bytes()
        path.write_text("# Failed specification\n")
        with self.assertRaisesRegex(lifecycle.LifecycleError, "identify exactly"):
            self.start(spec=name)
        self.assertEqual(self.roadmap.read_bytes(), before)
        path.write_text("ROADMAP entry: RM-01\nROADMAP entry: RM-01\n")
        with self.assertRaisesRegex(lifecycle.LifecycleError, "identify exactly"):
            self.start(spec=name)
        self.assertEqual(self.roadmap.read_bytes(), before)

    def test_specify_requires_ready_and_complete_checklist(self) -> None:
        name = self.spec()
        with self.assertRaisesRegex(lifecycle.LifecycleError, "ready status"):
            self.start(spec=name)
        self.initial()
        (self.project / "specs/RM-01/checklists/requirements.md").write_text("- [ ] Missing\n")
        with self.assertRaisesRegex(lifecycle.LifecycleError, "checklist"):
            self.start(spec=name)

    def test_same_active_rm02_spec_reconciliation_preserves_link_and_downstream_work(self):
        self.write(row("RM-01", status="done") + row("RM-02", status="ready", deps="RM-01"))
        name = self.spec("RM-02")
        self.start("RM-02", name)
        folder = (self.project / name).parent
        (folder / "spec.md").write_text("ROADMAP entry: RM-02\nReconciled local behavior.\n")
        (folder / "tasks.md").write_text("- [x] T001 Existing work\n- [ ] T002 Remaining work\n")
        (folder / "plan.md").write_text("Existing Plan.\n")
        before = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        result = self.start("RM-02", name)
        self.assertEqual(result, {"action": "start", "id": "RM-02", "changed": False, "status": "active"})
        self.assertEqual(before, {p.relative_to(self.project): p.read_bytes()
                                  for p in self.project.rglob("*") if p.is_file()})

    def test_active_reconciliation_cannot_change_entry_link_or_reopen_done(self):
        self.initial()
        name = self.spec()
        self.start(spec=name)
        for feature, link in (("RM-01", "specs/new/spec.md"), ("RM-02", name), ("RM-99", name)):
            with self.subTest(feature=feature, link=link):
                before = self.roadmap.read_bytes()
                with self.assertRaises(lifecycle.LifecycleError):
                    self.start(feature, link)
                self.assertEqual(self.roadmap.read_bytes(), before)
        self.write(self.roadmap.read_text().replace("Status: active", "Status: done"))
        before = self.roadmap.read_bytes()
        with self.assertRaisesRegex(lifecycle.LifecycleError, "ready status"):
            self.start(spec=name)
        self.assertEqual(self.roadmap.read_bytes(), before)

    def test_incomplete_tasks_prevent_done(self) -> None:
        self.initial(); self.start(); self.tasks("- [ ] T001 Finish feature\n")
        with self.assertRaisesRegex(lifecycle.LifecycleError, "incomplete tasks"):
            self.complete()
        self.assertEqual(self.status("RM-01"), "active")

    def test_changed_or_ambiguous_spec_identity_prevents_done(self) -> None:
        self.initial(); name = self.spec(); self.start(spec=name); self.tasks()
        spec = self.project / name
        before = self.roadmap.read_bytes()
        for content in ("ROADMAP entry: RM-02\n",
                        "ROADMAP entry: RM-01\nROADMAP entry: RM-01\n"):
            spec.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(lifecycle.LifecycleError, "linked spec must identify exactly"):
                self.complete()
            self.assertEqual(self.roadmap.read_bytes(), before)

    def test_noncompatible_and_failed_governance_checks_prevent_done(self) -> None:
        self.initial(); self.start(); self.tasks()
        for values, expected in [
            ({"compatibility": "BASELINE_CHANGE_REQUIRED"}, "Greenfield COMPATIBLE"),
            ({"feature_after_tasks": "BLOCK"}, "Feature Governance after_tasks"),
            ({"feature_before_implement": "BLOCK"}, "Feature Governance before_implement"),
            ({"mvp_before_implement": "BLOCK"}, "MVP Governance before_implement"),
            ({"mvp_after_implement": "BLOCK"}, "MVP Governance after_implement"),
            ({"converge": "tasks_appended"}, "clean converge"),
            ({"verification": "BLOCK"}, "required verification"),
            ({"blockers": "unresolved finding"}, "no unresolved blockers"),
        ]:
            result = self.complete(**values)
            self.assertTrue(any(expected in blocker for blocker in result["blockers"]))
            self.assertEqual(self.status("RM-01"), "active")

    def test_missing_evidence_prevents_done(self) -> None:
        self.initial(); self.start(); self.tasks()
        with self.assertRaisesRegex(lifecycle.LifecycleError, "evidence was not identified"):
            self.complete(evidence=[])
        with self.assertRaisesRegex(lifecycle.LifecycleError, "Required file is missing"):
            self.complete(evidence=["tests/absent.py"])
        self.assertEqual(self.status("RM-01"), "active")

    def test_successful_completion_unlocks_direct_dependent(self) -> None:
        self.initial(); self.start(); self.tasks()
        result = self.complete()
        self.assertEqual((self.status("RM-01"), self.status("RM-02")), ("done", "ready"))
        self.assertEqual([item["id"] for item in result["dependents"]], ["RM-02"])

    def test_multiple_predecessors_must_be_done(self) -> None:
        self.write(row("RM-01") + row("RM-02") + row("RM-03", deps="RM-01, RM-02"))
        self.initial(); self.start(); self.tasks(); self.complete()
        self.assertEqual(self.status("RM-03"), "planned")
        self.assertIn("waiting for RM-02", self.roadmap.read_text())

    def test_deferred_dependent_stays_deferred(self) -> None:
        self.write(row("RM-01") + row("RM-02", status="deferred", deps="RM-01", reason="explicitly deferred"))
        self.initial(); self.start(); self.tasks(); self.complete()
        self.assertEqual(self.status("RM-02"), "deferred")

    def test_malformed_graph_blocks_all_changes(self) -> None:
        for content in [row("RM-01", deps="RM-99"),
                        row("RM-01", deps="RM-02") + row("RM-02", deps="RM-01"),
                        row("RM-01") + row("RM-01")]:
            self.write(content)
            before = self.roadmap.read_bytes()
            with self.assertRaises(lifecycle.LifecycleError):
                self.initial()
            self.assertEqual(self.roadmap.read_bytes(), before)

    def test_repeated_transitions_are_idempotent(self) -> None:
        self.initial(); before = self.roadmap.read_bytes(); self.initial()
        self.assertEqual(self.roadmap.read_bytes(), before)
        name = self.spec(); self.start(spec=name)
        before = self.roadmap.read_bytes(); self.start(spec=name)
        self.assertEqual(self.roadmap.read_bytes(), before)
        self.tasks(); self.complete()
        before = self.roadmap.read_bytes(); self.complete()
        self.assertEqual(self.roadmap.read_bytes(), before)

    def test_concurrent_roadmap_change_aborts_write(self) -> None:
        before = self.roadmap.read_text()
        def concurrent_edit():
            self.write(before + "Unrelated concurrent note.\n")
        with self.assertRaisesRegex(lifecycle.LifecycleError, "changed during"):
            lifecycle.apply(self.project, Namespace(action="initial", run_id="run-1"),
                            before_write=concurrent_edit)
        self.assertEqual(self.roadmap.read_text(), before + "Unrelated concurrent note.\n")

    def test_crlf_status_update_preserves_unrelated_bytes(self) -> None:
        original = ("# ROADMAP\n\n" + row("RM-01")
                    + "Unrelated note: keep spacing and punctuation.  \n").replace("\n", "\r\n").encode("utf-8")
        self.roadmap.write_bytes(original)

        self.initial()

        expected = original.replace(b"Status: planned\r\n", b"Status: ready\r\n").replace(
            b"Status reason: awaiting PROJECT READY\r\n",
            b"Status reason: prerequisites satisfied\r\n")
        self.assertEqual(self.roadmap.read_bytes(), expected)

    def test_concurrent_line_ending_only_change_aborts_write(self) -> None:
        original = row("RM-01").replace("\n", "\r\n").encode("utf-8")
        self.roadmap.write_bytes(original)
        concurrent = original.replace(b"\r\n", b"\n")

        def concurrent_edit():
            self.roadmap.write_bytes(concurrent)

        with self.assertRaisesRegex(lifecycle.LifecycleError, "changed during"):
            lifecycle.apply(self.project, Namespace(action="initial", run_id="run-1"),
                            before_write=concurrent_edit)
        self.assertEqual(self.roadmap.read_bytes(), concurrent)

    def test_competing_lifecycle_writer_fails_while_first_holds_lock(self) -> None:
        before = self.roadmap.read_bytes()
        def competing_writer():
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--project", str(self.project), "initial", "run-1"],
                capture_output=True, text=True, timeout=5, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Another ROADMAP lifecycle writer is active", result.stderr)
            self.assertEqual(self.roadmap.read_bytes(), before)
        lifecycle.apply(self.project, Namespace(action="initial", run_id="run-1"),
                        before_write=competing_writer)
        self.assertEqual(self.status("RM-01"), "ready")
        self.assertFalse((self.project / ".roadmap-lifecycle.lock").exists())

    def test_unrelated_entry_bytes_are_preserved(self) -> None:
        unrelated = row("RM-03", status="blocked", reason="needs a product decision")
        self.write("# ROADMAP\n\n" + row("RM-01") + unrelated)
        self.initial()
        self.assertIn(unrelated, self.roadmap.read_text())

    def test_manifest_and_workflow_are_valid(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = ExtensionManifest(root / "extension" / "extension.yml")
        self.assertEqual(manifest.id, "greenfield-roadmap-lifecycle")
        self.assertEqual(list(manifest.hooks), ["after_converge"])
        self.assertFalse(manifest.hooks["after_converge"]["optional"])
        workflow = WorkflowDefinition.from_yaml(root / "workflow" / "workflow.yml")
        self.assertEqual(validate_workflow(workflow), [])
        self.assertEqual([step["id"] for step in workflow.steps[-2:]],
                         ["project-ready", "initialize-roadmap-readiness"])

    def test_real_workflow_gate_triggers_initial_readiness(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = WorkflowDefinition.from_yaml(root / "workflow" / "workflow.yml")
        data = deepcopy(source.data)
        data["steps"] = data["steps"][-3:]
        workflow = WorkflowDefinition(data, source_path=root / "workflow" / "workflow.yml")
        installed = self.project / ".specify/extensions/greenfield-roadmap-lifecycle/scripts"
        installed.mkdir(parents=True)
        shutil.copy2(SCRIPT, installed / SCRIPT.name)
        engine = WorkflowEngine(self.project)
        with patch.object(PromptStep, "execute", return_value=StepResult(status=StepStatus.COMPLETED)):
            state = engine.execute(workflow, {"integration": "auto", "canonical_prd": "prd.md"})
            self.assertEqual(state.status, RunStatus.PAUSED)
            self.assertEqual(self.status("RM-01"), "planned")
            state = engine.resume(state.run_id, {"project_ready_decision": "approve"})
        self.assertEqual(state.status, RunStatus.COMPLETED)
        self.assertEqual(self.status("RM-01"), "ready")


class NativeLifecycleTests(FactFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.write("ROADMAP.md", row("RM-01") + row("RM-02", deps="RM-01"))
        self.approve("project-ready")
        self.save()
        root = SCRIPT.parents[2]
        shutil.copytree(root / "foundation", self.project / ".specify/extensions/greenfield-foundation")
        installed = self.project / ".specify/extensions/greenfield-roadmap-lifecycle/scripts"
        installed.mkdir(parents=True)
        shutil.copy2(SCRIPT, installed / SCRIPT.name)

    def native_initial(self, **overrides):
        values = dict(action="initial", run_id=None, registry=facts.DEFAULT_REGISTRY)
        values.update(overrides)
        return lifecycle.apply(self.project, Namespace(**values))

    def human_mode(self):
        self.write(".specify/extensions/greenfield-roadmap-lifecycle/greenfield-roadmap-lifecycle-config.yml",
                   "completion_mode: human\napproval_registry: .specify/governance/hitl.json\n")

    def active_feature(self):
        self.native_initial()
        self.feature()
        lifecycle.apply(self.project, Namespace(action="start", feature_id="RM-01", spec=self.spec))

    def arguments(self, action="complete"):
        return Namespace(action=action, feature_id="RM-01", converge="clean", compatibility="COMPATIBLE",
                         feature_after_tasks="PASS", feature_before_implement="PASS", mvp_before_implement="PASS",
                         mvp_after_implement="PASS", verification="PASS", blockers="none", evidence=["evidence/result.txt"])

    def status(self, feature="RM-01"):
        return lifecycle.Roadmap((self.project / "ROADMAP.md").read_text()).entries[feature].fields["Status"]

    def test_native_initial_and_repeat_without_any_workflow_directory(self):
        self.native_initial()
        before = (self.project / "ROADMAP.md").read_bytes()
        self.native_initial()
        self.assertEqual((self.project / "ROADMAP.md").read_bytes(), before)
        self.assertEqual((self.status(), self.status("RM-02")), ("ready", "planned"))
        self.assertFalse((self.project / ".specify/workflows").exists())

    def test_installed_cli_initial_accepts_native_authorization(self):
        script = self.project / ".specify/extensions/greenfield-roadmap-lifecycle/scripts/roadmap_lifecycle.py"
        result = subprocess.run([sys.executable, "-B", str(script), "--project", str(self.project),
                                 "initial", "--registry", facts.DEFAULT_REGISTRY], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["action"], "initial")
        self.assertEqual(self.status(), "ready")
        self.assertFalse((self.project / ".specify/workflows").exists())

    def test_explicit_sources_cannot_fallback_or_be_combined(self):
        for overrides in ({"registry": "missing.json"}, {"run_id": "run-1"}, {"registry": None, "run_id": "run-1"}):
            before = (self.project / "ROADMAP.md").read_bytes()
            with self.assertRaises((ValueError, OSError)):
                self.native_initial(**overrides)
            self.assertEqual((self.project / "ROADMAP.md").read_bytes(), before)

    def test_native_approval_change_before_initial_write_blocks_promotion(self):
        before = (self.project / "ROADMAP.md").read_bytes()
        with self.assertRaises(ValueError):
            lifecycle.apply(self.project, Namespace(action="initial", run_id=None, registry=facts.DEFAULT_REGISTRY),
                            before_write=lambda: self.write("prd.md", "Changed approved input.\n"))
        self.assertEqual((self.project / "ROADMAP.md").read_bytes(), before)

    def test_rejected_stale_and_unresolved_native_authorization_cannot_promote(self):
        original = deepcopy(self.data)
        for update in ({"decision": "reject"}, {"fingerprint": "0" * 64}, {"verification": "BLOCKED"}):
            self.data = deepcopy(original)
            self.data["approvals"][-1].update(update)
            self.save()
            with self.assertRaises(ValueError):
                self.native_initial()
            self.assertEqual(self.status(), "planned")

    def test_verify_is_read_only_even_when_lifecycle_lock_exists(self):
        self.active_feature()
        self.write(".roadmap-lifecycle.lock", "another writer")
        before = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        result = lifecycle.apply(self.project, self.arguments("verify"))
        self.assertTrue(result["ready_for_acceptance"])
        self.assertFalse(result["changed"])
        after = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(self.status(), "active")

    def test_human_mode_blocks_done_until_current_acceptance(self):
        self.human_mode()
        self.active_feature()
        lifecycle.apply(self.project, self.arguments("verify"))
        with self.assertRaisesRegex(ValueError, "human-acceptance"):
            lifecycle.apply(self.project, self.arguments())
        self.assertEqual(self.status(), "active")
        self.approve("human-acceptance", "RM-01", self.spec, ["evidence/result.txt"])
        self.save()
        result = lifecycle.apply(self.project, self.arguments())
        self.assertTrue(result["changed"])
        self.assertEqual((self.status(), self.status("RM-02")), ("done", "ready"))
        self.assertFalse(lifecycle.apply(self.project, self.arguments())["changed"])

    def test_tasks_appended_hook_skips_clean_verification_in_both_modes(self):
        self.active_feature()
        self.write("specs/RM-01/tasks.md", "- [x] T001 Implement A\n- [ ] T002 Correct convergence finding\n")
        for human in (False, True):
            with self.subTest(human=human):
                if human:
                    self.human_mode()
                before = {p.relative_to(self.project): p.read_bytes()
                          for p in self.project.rglob("*") if p.is_file()}
                args = lifecycle.parser().parse_args(["hook", "RM-01", "--converge", "tasks_appended"])
                with patch.object(lifecycle, "verify_completion") as verify:
                    result = lifecycle.apply(self.project, args)
                    verify.assert_not_called()
                self.assertEqual(result, {"action": "hook", "id": "RM-01", "changed": False,
                                          "status": "active", "converge": "tasks_appended"})
                self.assertEqual(before, {p.relative_to(self.project): p.read_bytes()
                                         for p in self.project.rglob("*") if p.is_file()})
                # Explicit Complete still rejects this non-clean outcome.
                complete_args = self.arguments()
                complete_args.converge = "tasks_appended"
                self.assertIn("clean converge", lifecycle.apply(self.project, complete_args)["blockers"])
                self.assertEqual(self.status(), "active")

    def test_current_acceptance_hook_verifies_without_another_acceptance_stop(self):
        self.human_mode()
        self.active_feature()
        self.approve("human-acceptance", "RM-01", self.spec, ["evidence/result.txt"])
        self.save()
        before = (self.project / "ROADMAP.md").read_bytes()
        with patch.object(lifecycle, "verify_completion", wraps=lifecycle.verify_completion) as verify:
            result = lifecycle.apply(self.project, self.arguments("hook"))
            verify.assert_called_once()
        self.assertTrue(result["ready_for_acceptance"])
        self.assertFalse(result["human_acceptance_required"])
        self.assertEqual((self.project / "ROADMAP.md").read_bytes(), before)
        self.assertEqual(lifecycle.apply(self.project, self.arguments())["status"], "done")

    def test_missing_or_stale_acceptance_hook_still_requires_acceptance_and_blocks_complete(self):
        self.human_mode()
        self.active_feature()
        for stale in (False, True):
            with self.subTest(stale=stale):
                if stale:
                    self.approve("human-acceptance", "RM-01", self.spec, ["evidence/result.txt"])
                    self.save()
                    self.write("src/service.py", "Changed implementation.\n")
                before = (self.project / "ROADMAP.md").read_bytes()
                result = lifecycle.apply(self.project, self.arguments("hook"))
                self.assertTrue(result["human_acceptance_required"])
                with self.assertRaisesRegex(ValueError, "human-acceptance"):
                    lifecycle.apply(self.project, self.arguments())
                self.assertEqual((self.project / "ROADMAP.md").read_bytes(), before)

    def test_current_acceptance_hook_cannot_replace_completion_checks_or_evidence(self):
        self.human_mode()
        self.active_feature()
        self.write("evidence/extra.txt", "Additional current verification.\n")
        self.approve("human-acceptance", "RM-01", self.spec, ["evidence/result.txt"])
        self.save()
        for field in ("converge", "compatibility", "feature_after_tasks", "feature_before_implement",
                      "mvp_before_implement", "mvp_after_implement", "verification", "blockers"):
            with self.subTest(field=field):
                args = self.arguments("hook")
                setattr(args, field, "unknown")
                result = lifecycle.apply(self.project, args)
                self.assertTrue(result["blockers"])
                self.assertNotIn("human_acceptance_required", result)
                self.assertEqual(self.status(), "active")
        args = self.arguments("hook")
        args.evidence.append("evidence/extra.txt")
        self.assertTrue(lifecycle.apply(self.project, args)["human_acceptance_required"])
        args.action = "complete"
        with self.assertRaisesRegex(ValueError, "required verification evidence"):
            lifecycle.apply(self.project, args)

    def test_automatic_clean_hook_retains_existing_completion(self):
        self.active_feature()
        self.assertEqual(lifecycle.apply(self.project, self.arguments("hook"))["status"], "done")

    def test_automatic_hook_cannot_bypass_human_mode_selected_before_write(self):
        self.active_feature()
        before = (self.project / "ROADMAP.md").read_bytes()
        with self.assertRaisesRegex(ValueError, "human-acceptance"):
            lifecycle.apply(self.project, self.arguments("hook"), before_write=self.human_mode)
        self.assertEqual((self.project / "ROADMAP.md").read_bytes(), before)

    def test_stale_acceptance_and_changes_before_write_cannot_complete(self):
        self.human_mode()
        self.active_feature()
        self.approve("human-acceptance", "RM-01", self.spec, ["evidence/result.txt"])
        self.save()
        before = (self.project / "ROADMAP.md").read_bytes()
        with self.assertRaisesRegex(ValueError, "Stale human-acceptance"):
            lifecycle.apply(self.project, self.arguments(), before_write=lambda: self.write("src/service.py", "CHANGED = True\n"))
        self.assertEqual((self.project / "ROADMAP.md").read_bytes(), before)
        self.assertFalse((self.project / ".roadmap-lifecycle.lock").exists())

    def test_direct_installed_cli_has_no_human_mode_bypass(self):
        self.human_mode()
        self.active_feature()
        args = self.arguments()
        command = [sys.executable, "-B", str(self.project / ".specify/extensions/greenfield-roadmap-lifecycle/scripts/roadmap_lifecycle.py"),
                   "--project", str(self.project), "complete", "RM-01"]
        for key, value in vars(args).items():
            if key in {"action", "feature_id"}:
                continue
            if isinstance(value, list):
                for item in value:
                    command.extend(["--" + key.replace("_", "-"), item])
            else:
                command.extend(["--" + key.replace("_", "-"), value])
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("human-acceptance", result.stderr)
        self.assertEqual(self.status(), "active")
        self.assertFalse((self.project / ".specify/workflows").exists())

    def test_automatic_mode_keeps_existing_completion_behavior(self):
        self.active_feature()
        self.assertEqual(lifecycle.lifecycle_config(self.project)["completion_mode"], "automatic")
        lifecycle.apply(self.project, self.arguments())
        self.assertEqual((self.status(), self.status("RM-02")), ("done", "ready"))

    def test_invalid_configuration_cannot_fall_back_to_automatic(self):
        self.active_feature()
        relative = ".specify/extensions/greenfield-roadmap-lifecycle/greenfield-roadmap-lifecycle-config.yml"
        for text in ("completion_mode: typo\n", "completion_mode: [human]\n", "unknown: value\n", "[invalid\n"):
            self.write(relative, text)
            with self.assertRaises(lifecycle.LifecycleError):
                lifecycle.apply(self.project, self.arguments())
            self.assertEqual(self.status(), "active")

    def test_human_mode_cannot_start_with_stale_project_ready(self):
        self.human_mode()
        self.native_initial()
        self.feature()
        self.write(".specify/memory/constitution.md", "Material new invariant.\n")
        with self.assertRaisesRegex(ValueError, "Stale project-ready"):
            lifecycle.apply(self.project, Namespace(action="start", feature_id="RM-01", spec=self.spec))
        self.assertEqual(self.status(), "ready")
