"""Current approval facts, authority changes and sticky product decisions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

from foundation.scripts import governance_facts as facts
from foundation.scripts import prd_governance as prd


class FactFixture:
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.write("prd.md", "Purpose and approved behavior.\n")
        self.write("architecture/baseline.md", "Status: Draft\nRevision: 1\nContract A.\n")
        self.write("ROADMAP.md", "<!-- roadmap-entry: RM-01 -->\nStatus: planned\nStatus reason: awaiting approval\nDepends on: none\nFeature spec: none\nOutcome: Contract A.\n")
        self.write(".specify/memory/constitution.md", "# Native Constitution\nInvariant.\n")
        self.data = {"schema_version": 1, "canonical_prd": "prd.md",
                     "prd_revision": self.revision(), "product_gaps": [], "approvals": []}
        self.approve("prd")
        self.approve("architecture")
        self.write("architecture/baseline.md", "Status: Approved\nRevision: 1\nContract A.\n")
        self.approve("project-ready")
        self.save()

    def write(self, relative, content):
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def revision(self):
        return hashlib.sha256((self.project / "prd.md").read_bytes()).hexdigest()

    def approve(self, boundary, subject="foundation", spec=None, extra=()):
        inputs = sorted(facts.required_inputs(boundary, "prd.md", spec) | set(extra))
        approval = {"boundary": boundary, "subject": subject, "decision": "approve", "human": True,
                    "verification": "PROJECT READY" if boundary == "project-ready" else "PASS",
                    "inputs": inputs,
                    "fingerprint": facts.fingerprint(self.project, boundary, subject, "prd.md", inputs, spec)}
        self.data["approvals"] = [a for a in self.data["approvals"] if (a["boundary"], a["subject"]) != (boundary, subject)]
        self.data["approvals"].append(approval)
        return approval

    def save(self):
        self.write(facts.DEFAULT_REGISTRY, json.dumps(self.data))

    def feature(self):
        self.spec = "specs/RM-01/spec.md"
        self.write(self.spec, "ROADMAP entry: RM-01\nFeature A.\n")
        self.write("specs/RM-01/plan.md", "Plan A.\n")
        self.write("specs/RM-01/tasks.md", "- [x] T001 Implement A\n")
        self.write("specs/RM-01/checklists/requirements.md", "- [x] Quality\n")
        self.write("src/service.py", "IMPLEMENTED = True\n")
        self.write("evidence/result.txt", "Verified current implementation.\n")


class GovernanceFactTests(FactFixture, TestCase):
    def test_approved_input_and_publication_preserve_authorization(self):
        facts.require_approval(self.project, self.data, "prd")
        facts.require_approval(self.project, self.data, "architecture")
        facts.require_approval(self.project, self.data, "project-ready")
        self.assertFalse((self.project / ".specify/workflows").exists())

    def test_only_managed_roadmap_fields_are_excluded(self):
        path = self.project / "ROADMAP.md"
        path.write_text(path.read_text().replace("Status: planned", "Status: active")
                        .replace("awaiting approval", "specify completed").replace("Feature spec: none", "Feature spec: specs/RM-01/spec.md"))
        facts.require_approval(self.project, self.data, "project-ready")
        path.write_text(path.read_text().replace("Outcome: Contract A.", "Outcome: Contract B."))
        with self.assertRaisesRegex(facts.FactError, "Stale project-ready"):
            facts.require_approval(self.project, self.data, "project-ready")

    def test_upstream_authority_changes_invalidate_approval(self):
        for relative in ("prd.md", "architecture/baseline.md", ".specify/memory/constitution.md"):
            with self.subTest(relative=relative):
                path = self.project / relative
                original = path.read_text()
                path.write_text(original + "Material change.\n")
                with self.assertRaises(facts.FactError):
                    facts.require_approval(self.project, self.data, "project-ready")
                path.write_text(original)

    def test_missing_rejected_nonhuman_or_unverified_approval_fails(self):
        original = deepcopy(self.data)
        for update in ({"decision": "reject"}, {"human": False}, {"verification": "BLOCKED"}):
            self.data = deepcopy(original)
            self.data["approvals"][-1].update(update)
            with self.assertRaises(facts.FactError):
                facts.require_approval(self.project, self.data, "project-ready")
        self.data["approvals"] = []
        with self.assertRaises(facts.FactError):
            facts.require_approval(self.project, self.data, "prd")

    def test_draft_or_duplicate_baseline_status_blocks_project_ready(self):
        for status in ("Status: Draft\n", "Status: Approved\nStatus: Draft\n"):
            self.write("architecture/baseline.md", status + "Revision: 1\nContract A.\n")
            with self.assertRaisesRegex(facts.FactError, "explicitly Approved"):
                facts.require_approval(self.project, self.data, "project-ready")

    def test_schema_rejects_workflow_state_and_history(self):
        for field in ("run_id", "current_stage", "reviews", "history", "status", "checklist_skipped"):
            data = deepcopy(self.data)
            data[field] = "anything"
            with self.assertRaisesRegex(facts.FactError, "schema"):
                facts.validate_facts(data)
        data = deepcopy(self.data)
        data["approvals"][0]["run_id"] = "anything"
        with self.assertRaises(facts.FactError):
            facts.validate_facts(data)

    def test_duplicate_or_incomplete_approval_is_not_authorization(self):
        data = deepcopy(self.data)
        data["approvals"].append(data["approvals"][0])
        with self.assertRaisesRegex(facts.FactError, "Duplicate"):
            facts.validate_facts(data)
        self.data["approvals"][-1]["inputs"] = ["prd.md"]
        with self.assertRaisesRegex(facts.FactError, "omits required"):
            facts.require_approval(self.project, self.data, "project-ready")

    def test_missing_escaping_and_symlink_inputs_fail_closed(self):
        with self.assertRaises(facts.FactError):
            facts.fingerprint(self.project, "prd", "foundation", "missing.md", ["missing.md"])
        with self.assertRaises(facts.FactError):
            facts.project_file(self.project, "../outside")
        (self.project / "escape").symlink_to(Path(__file__).resolve())
        with self.assertRaises(facts.FactError):
            facts.project_file(self.project, "escape")

    def test_acceptance_binds_evidence_and_entire_implementation(self):
        self.feature()
        self.approve("human-acceptance", "RM-01", self.spec, ["evidence/result.txt"])
        facts.require_approval(self.project, self.data, "human-acceptance", "RM-01", spec=self.spec, evidence=["evidence/result.txt"])
        for path in ("src/service.py", "evidence/result.txt", "specs/RM-01/plan.md"):
            original = (self.project / path).read_text()
            self.write(path, original + "changed\n")
            with self.assertRaisesRegex(facts.FactError, "Stale human-acceptance"):
                facts.require_approval(self.project, self.data, "human-acceptance", "RM-01", spec=self.spec)
            self.write(path, original)
        self.write("src/new.py", "new implementation\n")
        with self.assertRaises(facts.FactError):
            facts.require_approval(self.project, self.data, "human-acceptance", "RM-01", spec=self.spec)

    def test_acceptance_deletions_wrong_subject_and_omitted_evidence_fail(self):
        self.feature()
        self.approve("human-acceptance", "RM-01", self.spec)
        with self.assertRaisesRegex(facts.FactError, "does not bind"):
            facts.require_approval(self.project, self.data, "human-acceptance", "RM-01", spec=self.spec, evidence=["evidence/result.txt"])
        with self.assertRaises(facts.FactError):
            facts.require_approval(self.project, self.data, "human-acceptance", "RM-02", spec=self.spec)
        (self.project / "src/service.py").unlink()
        with self.assertRaises(facts.FactError):
            facts.require_approval(self.project, self.data, "human-acceptance", "RM-01", spec=self.spec)

    def test_cli_is_read_only_and_has_no_run_dependency(self):
        before = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        result = subprocess.run([sys.executable, "-B", str(Path(facts.__file__).resolve()), "require", "project-ready",
                                 "--project", str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_acceptance_binds_in_project_symlink_targets(self):
        self.feature()
        self.write("src/alternate.py", "ALTERNATE = True\n")
        link = self.project / "selected.py"
        link.symlink_to("src/service.py")
        self.approve("human-acceptance", "RM-01", self.spec, ["evidence/result.txt"])
        link.unlink()
        link.symlink_to("src/alternate.py")
        with self.assertRaisesRegex(facts.FactError, "Stale human-acceptance"):
            facts.require_approval(self.project, self.data, "human-acceptance", "RM-01", spec=self.spec)


class NativeProductDecisionTests(FactFixture, TestCase):
    def submission(self, *ids):
        return {"verdict": "PRODUCT_GAP" if ids else "CLEAN", "gaps": [
            {"gap_id": identity, "question": f"Which behavior for {identity}?", "options": ["A", "B"],
             "recommended_option": 1, "rationale": "Small scope."} for identity in ids]}

    def review(self, submission, resolution=None):
        self.data = prd.review_facts(self.data, submission, self.revision(), self.revision(), resolution)
        return self.data

    def test_false_clean_and_changed_prd_without_decision_keep_gap(self):
        self.review(self.submission("gap-a"))
        with self.assertRaisesRegex(facts.FactError, "unresolved PRODUCT GAP"):
            facts.require_approval(self.project, self.data, "project-ready")
        self.review(self.submission())
        self.assertEqual(len(self.data["product_gaps"]), 1)
        self.write("prd.md", "Changed without human decision.\n")
        self.review(self.submission())
        self.assertEqual(len(self.data["product_gaps"]), 1)
        self.assertFalse(any(a["boundary"] == "prd" for a in self.data["approvals"]))

    def test_resolution_requires_changed_prd_and_full_clean_review(self):
        self.review(self.submission("gap-a", "gap-b"))
        decision = {"gap_id": "gap-a", "from_revision": self.revision(), "human": True, "decision": "Use A"}
        self.review(self.submission(), decision)
        self.assertEqual(len(self.data["product_gaps"]), 2)
        self.write("prd.md", "Human decision gap-a: Use A.\n")
        self.review(self.submission("gap-b"), decision)
        self.assertEqual([g["gap_id"] for g in self.data["product_gaps"]], ["gap-b"])
        self.assertEqual(set(self.data), facts.ROOT_FIELDS)
        with self.assertRaises(ValueError):
            self.review(self.submission(), decision)

    def test_rediscovery_preserves_identity_and_review_race_blocks(self):
        self.review(self.submission("gap-a"))
        alias = self.submission("other-id")
        alias["gaps"][0]["question"] = "WHICH behavior for gap-a?!"
        self.review(alias)
        self.assertEqual([g["gap_id"] for g in self.data["product_gaps"]], ["gap-a"])
        with self.assertRaisesRegex(ValueError, "changed during review"):
            prd.review_facts(self.data, self.submission(), self.revision(), "0" * 64)

    def test_native_cli_returns_current_facts_without_writing_registry(self):
        self.write("submission.json", json.dumps(self.submission("gap-a")))
        registry = self.project / facts.DEFAULT_REGISTRY
        before = registry.read_bytes()
        command = [sys.executable, "-B", str(Path(prd.__file__).resolve()), "--project", str(self.project),
                   "--prd", str(self.project / "prd.md"), "--facts", str(registry),
                   "--submission", str(self.project / "submission.json"), "--review-start-revision", self.revision()]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        current = json.loads(result.stdout)
        facts.validate_facts(current)
        self.assertEqual(current["product_gaps"][0]["gap_id"], "gap-a")
        self.assertEqual(registry.read_bytes(), before)
        self.assertFalse((self.project / ".specify/workflows").exists())
