"""Shared PRD validation; callers own transport and persistence."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
import sys

GAP_ID = re.compile(r"[a-z][a-z0-9-]*\Z")
INTERNAL_TEXT = re.compile(
    r"\b(?:run[ -]?id|git status|resume with|govern-prd|prd-governance|"
    r"workflow stage)\b|\.specify/|--input|\b[a-fA-F0-9]{64}\b",
    re.IGNORECASE,
)


def fail(message: str) -> None:
    raise ValueError(message)


def revision(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required_string(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"Review field {key!r} must be a nonempty string")
    return value.strip()


def gap_from_submission(item: object) -> dict:
    if not isinstance(item, dict):
        fail("Each PRODUCT GAP must be an object")
    gap_id = required_string(item, "gap_id")
    if not GAP_ID.fullmatch(gap_id):
        fail("PRODUCT GAP gap_id must be a stable lowercase slug")
    options = item.get("options")
    if not isinstance(options, list) or len(options) < 2 or any(
        not isinstance(option, str) or not option.strip() for option in options
    ):
        fail("PRODUCT GAP options must contain at least two nonempty choices")
    recommended = item.get("recommended_option")
    if not isinstance(recommended, int) or isinstance(recommended, bool) or not 1 <= recommended <= len(options):
        fail("recommended_option must be an option number")
    return {
        "gap_id": gap_id,
        "question": required_string(item, "question"),
        "options": [option.strip() for option in options],
        "recommended_option": recommended,
        "rationale": required_string(item, "rationale"),
    }


def question_key(question: str) -> str:
    """Collapse superficial wording differences for deterministic rediscovery."""
    return " ".join(re.findall(r"[\w]+", question.casefold()))


def validate_human_fields(gap: dict, diagnostic_id: str = "") -> None:
    for value in [gap["question"], *gap["options"], gap["rationale"]]:
        if (diagnostic_id and re.search(rf"(?<![\w-]){re.escape(diagnostic_id)}(?![\w-])", value)) or INTERNAL_TEXT.search(value):
            fail("PRODUCT GAP human text contains workflow diagnostics")


def gap_message(gap: dict) -> str:
    lines = ["Decision required", "", gap["question"], ""]
    lines.extend(f"{index}. {option}" for index, option in enumerate(gap["options"], 1))
    lines.extend([
        f"{len(gap['options']) + 1}. Custom rule (write it out).", "", "Recommended:",
        f"{gap['recommended_option']} — {gap['rationale']}", "",
        f"Please choose 1–{len(gap['options'])}, or provide a custom rule.",
    ])
    return "\n".join(lines)


def approval_message() -> str:
    return ("PRD review complete\n\nNo unresolved product gaps remain.\n\n"
            "Approve this PRD as the basis for architecture?\n\n"
            "Recommended:\nApprove.\n\nPlease reply: Approve or Reject.")


def validate_submission(submission: dict, diagnostic_id: str = "") -> tuple[str, list]:
    if not isinstance(submission, dict):
        fail("Structured PRD review submission must be an object")
    verdict = submission.get("verdict")
    if verdict not in ("CLEAN", "PRODUCT_GAP"):
        fail("Review verdict must be CLEAN or PRODUCT_GAP")
    submitted = submission.get("gaps")
    if not isinstance(submitted, list):
        fail("Review gaps must be a list")
    gaps = [gap_from_submission(item) for item in submitted]
    for gap in gaps:
        validate_human_fields(gap, diagnostic_id)
    if (verdict == "CLEAN") != (len(gaps) == 0):
        fail("Review verdict and gap list disagree")
    return verdict, gaps


def reconcile_gaps(existing: list, current: str, gaps: list,
                   resolution: dict | None = None) -> tuple[list, list, list]:
    """One sticky-gap algorithm for both transports; no history is recorded here."""
    unresolved, gaps = deepcopy(existing), deepcopy(gaps)
    for gap in gaps:
        match = next((old for old in unresolved if old["gap_id"] == gap["gap_id"] or
                      question_key(old["question"]) == question_key(gap["question"])), None)
        if match:
            gap["gap_id"] = match["gap_id"]
    if len({gap["gap_id"] for gap in gaps}) != len(gaps):
        fail("Review contains duplicate gap IDs")
    discovered = {gap["gap_id"] for gap in gaps}
    resolved = []
    if resolution and resolution["from_revision"] != current and resolution.get("decision_digest"):
        for old in list(unresolved):
            if old["gap_id"] == resolution["gap_id"] and old["gap_id"] not in discovered:
                old["status"] = "resolved"
                old["resolved_on_revision"] = current
                old["resolution_decision_digest"] = resolution["decision_digest"]
                resolved.append(old)
                unresolved.remove(old)
    for gap in gaps:
        if not any(old["gap_id"] == gap["gap_id"] for old in unresolved):
            unresolved.append({**gap, "discovered_on_revision": current, "status": "unresolved"})
    return unresolved, resolved, gaps


def review_facts(facts: dict, submission: dict, current: str,
                 review_start_revision: str, resolution: dict | None = None) -> dict:
    """Return current native facts only. Persistence belongs to the caller."""
    try:
        from .governance_facts import validate_facts
    except ImportError:
        from governance_facts import validate_facts

    validate_facts(facts)
    if review_start_revision != current:
        fail("Canonical PRD changed during review; repeat a full review")
    _, gaps = validate_submission(submission)
    candidate = None
    if resolution:
        if (set(resolution) != {"gap_id", "from_revision", "decision", "human"} or
                resolution["human"] is not True or not isinstance(resolution["decision"], str) or
                not resolution["decision"].strip() or
                resolution["from_revision"] != facts["prd_revision"] or
                not any(g["gap_id"] == resolution["gap_id"] for g in facts["product_gaps"])):
            fail("Resolution must be a current explicit human decision for one unresolved gap")
        candidate = {"gap_id": resolution["gap_id"], "from_revision": resolution["from_revision"],
                     "decision_digest": hashlib.sha256(resolution["decision"].encode()).hexdigest()}
    unresolved, _, _ = reconcile_gaps(facts["product_gaps"], current, gaps, candidate)
    result = deepcopy(facts)
    result["prd_revision"] = current
    result["product_gaps"] = unresolved
    # A new review does not grant or perpetuate approval of an unresolved PRD.
    if unresolved:
        result["approvals"] = [a for a in result["approvals"] if a["boundary"] != "prd"]
    validate_facts(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prd", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--review-start-revision", required=True)
    parser.add_argument("--resolution", type=Path)
    args = parser.parse_args()
    try:
        from governance_facts import project_file
        facts = json.loads(args.facts.read_text())
        if project_file(args.project, facts["canonical_prd"]) != args.prd.resolve():
            fail("Review PRD does not match the Canonical PRD fact")
        print(json.dumps(review_facts(facts,
              json.loads(args.submission.read_text()), revision(args.prd),
              args.review_start_revision,
              json.loads(args.resolution.read_text()) if args.resolution else None)))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"PRD governance validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
