"""Native command packaging and bootstrap composition without agent execution."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import yaml
from specify_cli.agents import CommandRegistrar
from specify_cli.extensions import ExtensionManifest, ExtensionManager
from specify_cli.workflows.engine import WorkflowDefinition, WorkflowEngine, validate_workflow
from specify_cli.workflows.base import StepResult, StepStatus, RunStatus
from specify_cli.workflows.steps.prompt import PromptStep

ROOT = Path(__file__).resolve().parents[1]


class FoundationInterfaceTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        (self.project / ".specify").mkdir()
        (self.project / ".specify/init-options.json").write_text(json.dumps({"ai": "codex", "ai_skills": True}))

    def test_native_command_generation_and_resource_paths(self):
        registrar = CommandRegistrar()
        output = self.project / ".agents/skills"
        for folder in ("foundation", "extension"):
            source = ROOT / folder
            manifest = ExtensionManifest(source / "extension.yml")
            installed = self.project / ".specify/extensions" / manifest.id
            shutil.copytree(source, installed)
            registered = registrar.register_commands("codex", manifest.commands, manifest.id,
                installed, self.project, _resolved_dir=output, extension_id=manifest.id)
            self.assertEqual(set(registered), {c["name"] for c in manifest.commands})
        skills = list(output.rglob("SKILL.md"))
        self.assertEqual(len(skills), 7)
        architecture = next(p.read_text() for p in skills if "# Greenfield Architecture" in p.read_text())
        self.assertIn(".specify/extensions/greenfield-foundation/scripts/governance_facts.py", architecture)
        self.assertIn(".specify/extensions/greenfield-foundation/docs/governance-facts.md", architecture)
        reconcile = next(p.read_text() for p in skills if "# Native Architecture reconciliation" in p.read_text())
        self.assertIn(".specify/extensions/greenfield-foundation/scripts/governance_facts.py require prd", reconcile)
        self.assertIn(".specify/extensions/greenfield-foundation/docs/governance-facts.md", reconcile)
        self.assertIn("Controlled Architecture Change", reconcile)
        self.assertIn("Stop at Architecture HITL", reconcile)
        self.assertIn("approval registry and downstream artifacts byte-for-byte", reconcile)
        self.assertIn("must not be recorded as approval of the unchanged baseline", reconcile)
        for skill in skills:
            metadata = yaml.safe_load(skill.read_text().split("---", 2)[1])
            self.assertTrue(metadata["name"].startswith("speckit-"))
            self.assertIn("description", metadata)

    def test_native_config_deployment_preserves_explicit_human_mode(self):
        installed = self.project / ".specify/extensions/greenfield-roadmap-lifecycle"
        shutil.copytree(ROOT / "extension", installed)
        manager = ExtensionManager(self.project)
        deployed, skipped, failed = manager.scaffold_config("greenfield-roadmap-lifecycle")
        self.assertEqual(failed, [])
        target = installed / "greenfield-roadmap-lifecycle-config.yml"
        self.assertEqual(yaml.safe_load(target.read_text())["completion_mode"], "automatic")
        target.write_text("completion_mode: human\napproval_registry: .specify/governance/hitl.json\n")
        before = target.read_bytes()
        deployed, skipped, failed = manager.scaffold_config("greenfield-roadmap-lifecycle")
        self.assertEqual(failed, [])
        self.assertIn(target.name, skipped)
        self.assertEqual(target.read_bytes(), before)

    def test_bootstrap_keeps_gate_identity_order_and_timeouts(self):
        workflow = WorkflowDefinition.from_yaml(ROOT / "workflow/workflow.yml")
        self.assertEqual(validate_workflow(workflow), [])
        self.assertEqual([s["id"] for s in workflow.steps], ["prd-convergence", "derive-review-architecture",
            "approve-architecture", "publish-baseline-and-roadmap", "establish-constitution", "verify-project-ready",
            "project-ready", "initialize-roadmap-readiness"])
        for step in workflow.steps:
            self.assertEqual(step["timeout"], 900)
        inner = workflow.steps[0]["steps"]
        for step in inner:
            self.assertEqual(step["timeout"], 900)
        branch = next(s for s in inner if s["id"] == "route-prd-review")
        for step in branch["then"] + branch["else"]:
            self.assertEqual(step["timeout"], 900)
            self.assertEqual(step["verdict_input"], "prd_gate_decision")
        for step in workflow.steps[1:6]:
            if step["id"] != "approve-architecture":
                invocation = step.get("command", step.get("prompt", ""))
                self.assertIn("speckit.greenfield-foundation.", invocation)
                if step.get("type") == "prompt":
                    self.assertTrue(step["prompt"].startswith("Invoke the installed"))
                    self.assertNotIn("TARGET Architecture", step["prompt"])

    def test_architecture_rejection_never_calls_publication(self):
        source = WorkflowDefinition.from_yaml(ROOT / "workflow/workflow.yml")
        data = deepcopy(source.data)
        data["steps"] = data["steps"][1:4]
        definition = WorkflowDefinition(data, source_path=ROOT / "workflow/workflow.yml")
        calls = []
        def command(_step, config, _context):
            calls.append(config["prompt"].split("`", 2)[1])
            return StepResult(status=StepStatus.COMPLETED)
        # Existing-engine compatibility fixture only; no installed project or agent is dispatched.
        engine = WorkflowEngine(self.project)
        with patch.object(PromptStep, "execute", command):
            result = engine.execute(definition, {"canonical_prd": "prd.md", "integration": "auto", "architecture_approval": "reject"})
        self.assertEqual(result.status, RunStatus.ABORTED)
        self.assertEqual(calls, ["speckit.greenfield-foundation.architecture"])

    def test_installed_workflow_adapter_uses_installed_shared_validator(self):
        installed = self.project / ".specify/extensions/greenfield-foundation"
        shutil.copytree(ROOT / "foundation", installed)
        adapter = self.project / ".specify/workflows/greenfield-bootstrap/governance.py"
        adapter.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "workflow/governance.py", adapter)
        # No workflow execution: only exercise the adapter against a fixed legacy transport fixture.
        transport = self.project / ".specify/workflows/runs/fixture"
        transport.mkdir(parents=True)
        (self.project / "prd.md").write_text("Approved purpose.\n")
        (transport / "inputs.json").write_text(json.dumps({"inputs": {"canonical_prd": "prd.md"}}))
        result = subprocess.run([sys.executable, "-B", str(adapter), "prepare", "fixture"],
                                cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("prd_revision", json.loads(result.stdout))

    def test_native_procedures_have_no_run_path_and_no_new_checklist_gate(self):
        for path in (ROOT / "foundation/commands").glob("*.md"):
            self.assertNotIn(".specify/workflows/runs", path.read_text())
            self.assertNotIn("context.run_id", path.read_text())
        ready = (ROOT / "foundation/commands/speckit.greenfield-foundation.project-ready.md").read_text()
        self.assertIn("Optional `speckit.checklist` is not required", ready)
        self.assertIn("Do not persist a checklist-skipped fact", ready)
        prd = (ROOT / "foundation/commands/speckit.greenfield-foundation.prd.md").read_text()
        self.assertIn("If the decision is blank, make no change", prd)
        self.assertIn("ENTIRE current Canonical", prd)
        verifier = (ROOT / "extension/commands/speckit.greenfield-roadmap-lifecycle.verify.md").read_text()
        self.assertIn("rendered evidence", verifier)
        self.assertIn("twice", verifier)
        self.assertIn("do not invoke it from this verification command", verifier)

    def test_bundle_versions_match_installed_component_manifests(self):
        bundle = yaml.safe_load((ROOT / "bundle.yml").read_text())
        for folder, section, identity in (("foundation", "extensions", "extension"),
                                          ("extension", "extensions", "extension"),
                                          ("preset", "presets", "preset"), ("workflow", "workflows", "workflow")):
            path = ROOT / folder / (identity + ".yml")
            manifest = yaml.safe_load(path.read_text())
            matching = next(c for c in bundle["provides"][section] if c["id"] == manifest[identity]["id"])
            self.assertEqual(matching["version"], manifest[identity]["version"])

    def test_reconciliation_contracts_preserve_native_identity_and_task_progress(self):
        specify = " ".join((ROOT / "preset/commands/speckit.specify.md").read_text().split())
        self.assertIn("only active-entry exception", specify)
        self.assertIn("current native directory is that explicit directory", specify)
        self.assertIn("entry's unique Feature spec link", specify)
        self.assertIn("new directory/link, ambiguous context or done entry is rejected", specify)
        self.assertIn("Do not reset status, allocate a Feature, run branch-creation hooks", specify)
        self.assertIn("copy a fresh template over the Spec", specify)
        self.assertIn("ordinary specification quality review", specify)
        plan = " ".join((ROOT / "preset/commands/speckit.plan.md").read_text().split())
        self.assertIn("before Core setup", plan)
        self.assertIn("Preserve existing Tasks, task IDs/completed markers, implementation and evidence", plan)
        tasks = " ".join((ROOT / "preset/commands/speckit.tasks.md").read_text().split())
        self.assertIn("reconcile it in place against the current approved Plan/UX", tasks)
        self.assertIn("Preserve task IDs for still-applicable work", tasks)
        self.assertIn("preserve their completed checkbox markers", tasks)
        self.assertIn("do not renumber existing tasks or reset progress", tasks)
        self.assertIn("Core's mandatory `after_tasks` Feature Governance Guard must still run", tasks)

    def test_completion_hook_contract_branches_before_clean_verification(self):
        hook = " ".join((ROOT / "extension/commands/speckit.greenfield-roadmap-lifecycle.complete.md").read_text().split())
        recovery, clean = hook.split("2. Invoke the installed", 1)
        self.assertIn("If it is `tasks_appended`", recovery)
        self.assertIn("hook <ID> --converge tasks_appended", recovery)
        self.assertIn("Do not invoke the clean-completion verifier", recovery)
        self.assertIn("only `converged` continues below", recovery)
        self.assertIn("precisely the verifier's current flags and evidence", clean)
        self.assertIn("If `human_acceptance_required` is true", clean)
        self.assertIn("If false, return the verified result without another acceptance stop", clean)
        self.assertIn("ROADMAP remains active in either human-mode case", clean)
