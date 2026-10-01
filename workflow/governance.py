"""Fail-closed PRD review ledger for the SpecKit 0.16.2 workflow package.

The run-local ledger is audit/debug state, never product authority. The canonical
PRD remains the only product document. Shell steps capture JSON from this helper;
model stdout is never used as a verdict.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

RUN_ID = re.compile(r"[A-Za-z0-9_-]+\Z")
# Installed workflow packages cannot import their sibling source tree.
# Load the installed foundation; use the source tree only when running source tests.
import importlib.util


def shared_prd_module():
    installed = Path.cwd() / ".specify/extensions/greenfield-foundation/scripts/prd_governance.py"
    source = Path(__file__).resolve().parents[1] / "foundation/scripts/prd_governance.py"
    path = installed if installed.is_file() else source
    if not path.is_file():
        raise ValueError("Install greenfield-foundation before running greenfield-bootstrap")
    spec = importlib.util.spec_from_file_location("greenfield_prd", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shared = shared_prd_module()
fail = shared.fail
revision = shared.revision
gap_message = shared.gap_message
approval_message = shared.approval_message
validate_submission = shared.validate_submission
reconcile_gaps = shared.reconcile_gaps


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail(f"Expected JSON object: {path}")
    return data


def save_json(path: Path, data: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main(stage: str, run_id: str) -> dict:
    if not RUN_ID.fullmatch(run_id):
        fail("Invalid run ID")
    root = Path.cwd().resolve()
    run_dir = root / ".specify" / "workflows" / "runs" / run_id
    inputs = read_json(run_dir / "inputs.json")["inputs"]
    prd = (root / inputs["canonical_prd"]).resolve()
    if not prd.is_relative_to(root) or not prd.is_file():
        fail("Canonical PRD must be an existing project file")
    ledger_path = run_dir / "prd-governance.json"
    receipt_path = run_dir / "prd-review-submission.json"
    ledger = read_json(ledger_path) if ledger_path.exists() else {
        "schema_version": 1, "reviews": [], "unresolved_gaps": [],
        "resolved_gaps": [], "approval": None, "pending_gap_id": None,
        "last_decision_key": None, "pending_resolution": None,
    }
    current = revision(prd)

    if stage == "prepare":
        previous = ledger["reviews"][-1] if ledger["reviews"] else None
        requested = inputs.get("prd_gate_decision") == "approve"
        ledger["approval_request_revision"] = (
            previous["prd_revision"] if requested and previous and
            previous["effective_verdict"] == "CLEAN" else None
        )
        decision = inputs.get("prd_decision", "").strip()
        gap_id = ledger.get("pending_gap_id")
        # Inputs persist across resumes. The same answer must
        # never be rebound to a different gap merely because the pending gap
        # changed after a prior review.
        decision_key = hashlib.sha256(decision.encode()).hexdigest() if gap_id and decision else None
        fresh = bool(decision_key and decision_key != ledger.get("last_decision_key"))
        if not decision:
            ledger["last_decision_key"] = None
        if fresh:
            ledger["pending_resolution"] = {
                "gap_id": gap_id, "from_revision": current,
                "decision_digest": decision_key,
            }
            ledger["last_decision_key"] = decision_key
        else:
            ledger["pending_resolution"] = None
        applied_decision = ""
        if fresh:
            pending_gap = next(gap for gap in ledger["unresolved_gaps"] if gap["gap_id"] == gap_id)
            if decision.isdecimal() and not 1 <= int(decision) <= len(pending_gap["options"]):
                fail("Choose a listed option or supply a custom rule in words")
            if decision.isdecimal() and 1 <= int(decision) <= len(pending_gap["options"]):
                answer = pending_gap["options"][int(decision) - 1]
            elif decision.startswith(f"{gap_id}:"):
                answer = decision[len(gap_id) + 1:].strip()
            else:
                answer = decision
            if not answer:
                fail("A product decision answer is required")
            applied_decision = f"{gap_id}: {answer}"
        save_json(ledger_path, ledger)
        return {"prd_revision": current, "decision": applied_decision,
                "comment": inputs.get("prd_comment", "") if fresh else ""}

    if stage == "start_review":
        ledger["review_start_revision"] = current
        receipt_path.unlink(missing_ok=True)
        save_json(ledger_path, ledger)
        return {"prd_revision": current}

    if stage == "record":
        if ledger.get("review_start_revision") != current:
            fail("Canonical PRD changed during review; repeat a full review")
        if not receipt_path.is_file():
            fail("Structured PRD review submission is missing")
        submission = read_json(receipt_path)
        verdict, gaps = validate_submission(submission, run_id)
        pending = ledger.get("pending_resolution")
        previous_revision = ledger["reviews"][-1]["prd_revision"] if ledger["reviews"] else None
        resolution = pending if pending and pending["from_revision"] == previous_revision else None
        unresolved, resolved, gaps = reconcile_gaps(ledger["unresolved_gaps"], current, gaps, resolution)
        ledger["unresolved_gaps"] = unresolved
        ledger["resolved_gaps"].extend(resolved)
        discovered_ids = {gap["gap_id"] for gap in gaps}
        # A CLEAN claim never clears gaps on the same revision, nor gaps that
        # lack an explicit, PRD-changing resolution candidate.
        effective = "PRODUCT_GAP" if ledger["unresolved_gaps"] else verdict
        review = {"sequence": len(ledger["reviews"]) + 1,
                  "prd_revision": current, "submitted_verdict": verdict,
                  "effective_verdict": effective,
                  "discovered_gap_ids": sorted(discovered_ids)}
        ledger["reviews"].append(review)
        ledger["approval"] = None
        ledger["pending_resolution"] = None
        ledger["pending_gap_id"] = ledger["unresolved_gaps"][0]["gap_id"] if ledger["unresolved_gaps"] else None
        save_json(ledger_path, ledger)
        message = gap_message(ledger["unresolved_gaps"][0]) if effective == "PRODUCT_GAP" else approval_message()
        return {"effective_verdict": effective, "can_approve": effective == "CLEAN",
                "prd_revision": current, "human_message": message,
                "unresolved_gap_ids": [gap["gap_id"] for gap in ledger["unresolved_gaps"]]}

    if stage == "verify":
        last = ledger["reviews"][-1] if ledger["reviews"] else None
        if not last or last["effective_verdict"] != "CLEAN" or ledger["unresolved_gaps"]:
            fail("PRD approval blocked: unresolved PRODUCT GAP")
        if current != last["prd_revision"]:
            fail("PRD approval blocked: canonical PRD changed after review")
        state = read_json(run_dir / "state.json")
        gate = state["step_results"].get("prd-governance-gate", {})
        if gate.get("output", {}).get("choice") != "approve":
            fail("PRD approval blocked: no explicit Approve choice")
        # The input is presented before replay; it is bound to the review
        # visible at that earlier pause. Interactive choice occurs now.
        if inputs.get("prd_gate_decision") == "approve" and ledger.get("approval_request_revision") != current:
            fail("PRD approval blocked: approval belongs to another PRD revision")
        ledger["approval"] = {"approved_prd_revision": current,
                              "review_sequence": last["sequence"], "choice": "approve"}
        save_json(ledger_path, ledger)
        return {"approved_prd_revision": current, "review_sequence": last["sequence"]}

    fail(f"Unknown governance stage: {stage}")


if __name__ == "__main__":
    try:
        print(json.dumps(main(sys.argv[1], sys.argv[2]), ensure_ascii=False))
    except (KeyError, IndexError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"PRD governance validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
