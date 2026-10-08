"""Process adapter contract fixtures; no real release/adoption or acceptance."""
import json
import shutil
import subprocess
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from test_roadmap_lifecycle import lifecycle, row

class PlatformCompletionTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.folder = self.project / "specs/current"
        self.folder.mkdir(parents=True)
        (self.folder / "spec.md").write_text("ROADMAP entry: RM-01\n")
        (self.folder / "tasks.md").write_text("- [x] T001 Approved work\n")
        (self.folder / "checklists").mkdir()
        (self.folder / "checklists/requirements.md").write_text("- [x] Quality\n")
        (self.folder / "browser-verification-plan.json").write_text('{"current":"plan"}')
        (self.folder / "plan.md").write_text("## Verification Integration\nApplicability: applicable\nReason: Required browser proof.\n")
        (self.project / ".verification").mkdir()
        (self.project / ".verification/platform.json").write_text('{"current":"binding"}')
        (self.folder / "result.json").write_text('{"fixture":"result"}')
        (self.folder / "manifest.json").write_text('{"fixture":"manifest"}')
        self.request = {"result":{"fixture":"result"}, "manifest":{"fixture":"manifest"},
                        "assignment":{"providers":[]}}
        self.roadmap = lifecycle.Roadmap(row("RM-01", status="active", spec="specs/current/spec.md"))
        self.args = Namespace(feature_id="RM-01", converge="clean", compatibility="COMPATIBLE",
                              feature_after_tasks="PASS", feature_before_implement="PASS",
                              mvp_before_implement="PASS", mvp_after_implement="PASS",
                              verification="PASS", blockers="none", evidence=[
                              "specs/current/result.json", "specs/current/manifest.json", ".verification/platform.json"])

    def test_current_four_verdicts_do_not_manufacture_completion_or_acceptance(self):
        for verdict in ("PASS", "FAIL", "BLOCKED", "INCONCLUSIVE"):
            with self.subTest(verdict=verdict), patch.dict("os.environ", {
                "VERIFICATION_PLATFORM_RESULT_VALIDATOR":"explicit-fixture-entry",
                "VERIFICATION_PLATFORM_RESULT_REQUEST":json.dumps(self.request)}), patch.object(
                lifecycle.subprocess, "run", return_value=Namespace(returncode=0 if verdict=="PASS" else 2,
                stdout=json.dumps({"valid":verdict=="PASS", "verdict":verdict}))) as run:
                if verdict=="PASS":
                    result=lifecycle.verify_completion(self.roadmap,self.project,self.args)
                    self.assertTrue(result["ready_for_acceptance"])
                    self.assertFalse(result["changed"])
                else:
                    with self.assertRaisesRegex(lifecycle.LifecycleError,"cannot become verification PASS"):
                        lifecycle.verify_completion(self.roadmap,self.project,self.args)
                invocation=json.loads(run.call_args.kwargs["input"])
                self.assertEqual(invocation["planBytes"],'{"current":"plan"}')
                self.assertEqual(invocation["binding"],{"current":"binding"})

    def test_missing_published_manifest_or_neutral_binding_cannot_pass(self):
        with patch.dict("os.environ",{"VERIFICATION_PLATFORM_RESULT_VALIDATOR":"entry",
             "VERIFICATION_PLATFORM_RESULT_REQUEST":json.dumps(self.request)}):
            self.args.evidence.remove("specs/current/manifest.json")
            with self.assertRaisesRegex(lifecycle.LifecycleError,"published evidence"):
                lifecycle.verify_completion(self.roadmap,self.project,self.args)

    def test_applicable_missing_plan_blocks_completion_without_platform_call(self):
        (self.folder / "browser-verification-plan.json").unlink()
        (self.folder / "plan.md").write_text("## Verification Integration\nApplicability: applicable\nReason: Required browser proof.\n")
        with self.assertRaisesRegex(lifecycle.LifecycleError,"browser-verification-plan.json is missing"):
            lifecycle.verify_completion(self.roadmap,self.project,self.args)

    def test_unrelated_non_applicable_completion_remains_operational_without_platform(self):
        (self.folder / "browser-verification-plan.json").unlink()
        (self.folder / "plan.md").write_text("## Verification Integration\nApplicability: not applicable\nReason: Domain-only proof.\n")
        with patch.dict("os.environ",{"VERIFICATION_PLATFORM_RESULT_VALIDATOR":"","VERIFICATION_PLATFORM_RESULT_REQUEST":""}), patch.object(lifecycle.subprocess,"run") as run:
            result=lifecycle.verify_completion(self.roadmap,self.project,self.args)
            self.assertTrue(result["ready_for_acceptance"])
            run.assert_not_called()

    def test_malformed_adoption_cannot_silently_skip_required_proof(self):
        (self.folder / "browser-verification-plan.json").unlink()
        for text in ("## Verification Integration\nReason: Missing classification.\n",
                     "## Verification Integration\nApplicability: not applicable\n",
                     "## Verification Integration\nApplicability: applicable\nApplicability: not applicable\nReason: Contradictory.\n",
                     "## Verification Integration\nApplicability: not applicable\nReason: Domain.\n## Verification Integration\nApplicability: not applicable\nReason: Duplicate.\n"):
            with self.subTest(text=text):
                (self.folder / "plan.md").write_text(text)
                with self.assertRaisesRegex(lifecycle.LifecycleError, "reconciliation required"):
                    lifecycle.verify_completion(self.roadmap, self.project, self.args)

    def test_legacy_unadopted_completion_does_not_load_platform(self):
        (self.folder / "browser-verification-plan.json").unlink()
        (self.folder / "plan.md").write_text("COMPATIBLE\nExisting non-verification design.\n")
        with patch.object(lifecycle.subprocess, "run") as run:
            self.assertTrue(lifecycle.verify_completion(self.roadmap, self.project, self.args)["ready_for_acceptance"])
            run.assert_not_called()

    def test_real_platform_result_validation_binds_current_proof_and_published_evidence(self):
        platform = Path(__file__).resolve().parents[2] / "verification-platform"
        fixture = subprocess.run(["node", "--input-type=module", "-e",
            "import {currentResultFixture} from './tests/fixtures/current-result.mjs'; console.log(JSON.stringify(currentResultFixture()))"],
            cwd=platform, capture_output=True, text=True, check=True)
        request = json.loads(fixture.stdout)
        original = Path(request["projectRoot"])
        self.addCleanup(shutil.rmtree, original)
        snapshot = self.project / "snapshot"
        shutil.copytree(original, snapshot)
        for name in ("projectRoot", "sourceRoot", "outputRoot"):
            request[name] = str(snapshot)
        request["resolution"]["root"] = str(snapshot)
        (self.folder / "browser-verification-plan.json").write_text(request["planBytes"])
        (self.project / ".verification/platform.json").write_text(json.dumps(request["binding"]))
        (self.folder / "result.json").write_text(json.dumps(request["result"]))
        (self.folder / "manifest.json").write_text(json.dumps(request["manifest"]))
        for name, item in (("evidence", request["evidence"][0]), ("record", request["records"][0])):
            (self.folder / (name + ".json")).write_text(json.dumps(item))
            self.args.evidence.append("specs/current/" + name + ".json")
        self.args.evidence.append("snapshot/raw.json")
        # Provider implementation lookup is project-relative at this boundary.
        for name in ("fixture.ts", "fixture.d.ts", "verification-fixtures.ts"):
            shutil.copy(snapshot / name, self.project / name)
        env = {"VERIFICATION_PLATFORM_RESULT_VALIDATOR": str(platform / "dist/src/validation/result-cli.js"),
               "VERIFICATION_PLATFORM_RESULT_REQUEST": json.dumps(request)}
        with patch.dict("os.environ", env):
            self.assertTrue(lifecycle.verify_completion(self.roadmap, self.project, self.args)["ready_for_acceptance"])
            plan_path = self.folder / "browser-verification-plan.json"
            current_plan = plan_path.read_text()
            plan_path.write_text(current_plan + "\n")
            with self.assertRaisesRegex(lifecycle.LifecycleError, "Platform verification blocked"):
                lifecycle.verify_completion(self.roadmap, self.project, self.args)
            plan_path.write_text(current_plan)
            binding_path = self.project / ".verification/platform.json"
            current_binding = binding_path.read_text()
            changed_binding = json.loads(current_binding)
            changed_binding["repository"] = "https://example.invalid/changed"
            binding_path.write_text(json.dumps(changed_binding))
            with self.assertRaisesRegex(lifecycle.LifecycleError, "Platform verification blocked"):
                lifecycle.verify_completion(self.roadmap, self.project, self.args)
            binding_path.write_text(current_binding)
            self.args.evidence.remove("snapshot/raw.json")
            with self.assertRaisesRegex(lifecycle.LifecycleError, "attachment must be a published"):
                lifecycle.verify_completion(self.roadmap, self.project, self.args)
            self.args.evidence.append("snapshot/raw.json")
            (snapshot / "reference.spec.ts").write_text("changed generated source")
            with self.assertRaisesRegex(lifecycle.LifecycleError, "Generated source bytes mismatch"):
                lifecycle.verify_completion(self.roadmap, self.project, self.args)
            (snapshot / "reference.spec.ts").write_text("ordinary-source")
            request["records"] = []  # Green runner/result cannot replace actual proof records.
            with patch.dict("os.environ", {"VERIFICATION_PLATFORM_RESULT_REQUEST": json.dumps(request)}):
                with self.assertRaisesRegex(lifecycle.LifecycleError, "INCONCLUSIVE"):
                    lifecycle.verify_completion(self.roadmap, self.project, self.args)
