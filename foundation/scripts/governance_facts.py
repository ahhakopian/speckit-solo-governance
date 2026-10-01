"""Read-only Greenfield approval facts and authority fingerprints.

Facts are human declarations bound to content, not cryptographic proof of an
approver. The caller owns human interaction and storage; this module never
writes a registry or remembers procedural progress.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

DEFAULT_REGISTRY = ".specify/governance/hitl.json"
BOUNDARIES = {"prd", "architecture", "project-ready", "human-acceptance"}
ROOT_FIELDS = {"schema_version", "canonical_prd", "prd_revision", "product_gaps", "approvals"}
APPROVAL_FIELDS = {"boundary", "subject", "decision", "human", "fingerprint", "inputs", "verification"}
GAP_FIELDS = {"gap_id", "question", "options", "recommended_option", "rationale",
              "discovered_on_revision", "status"}
HEX = re.compile(r"[a-f0-9]{64}\Z")
ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")


class FactError(ValueError):
    pass


def project_file(project: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute() or
            ".." in Path(relative).parts or Path(relative).as_posix() != relative):
        raise FactError(f"Invalid project-relative file: {relative!r}")
    path = (project / relative).resolve()
    if not path.is_relative_to(project.resolve()) or not path.is_file():
        raise FactError(f"Missing or escaping project file: {relative}")
    return path


def _digest(value: object) -> bool:
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def validate_facts(data: object) -> dict:
    if not isinstance(data, dict) or set(data) != ROOT_FIELDS or type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise FactError("Invalid governance-fact schema (current facts only)")
    prd = data["canonical_prd"]
    if (not isinstance(prd, str) or not prd or Path(prd).is_absolute() or
            ".." in Path(prd).parts or Path(prd).as_posix() != prd or not _digest(data["prd_revision"])):
        raise FactError("Invalid Canonical PRD identity/fingerprint")
    if not isinstance(data["product_gaps"], list) or not isinstance(data["approvals"], list):
        raise FactError("Decision facts and approvals must be lists")
    seen = set()
    for gap in data["product_gaps"]:
        if not isinstance(gap, dict) or set(gap) != GAP_FIELDS or gap["status"] != "unresolved" or not _digest(gap["discovered_on_revision"]):
            raise FactError("Only current unresolved PRODUCT GAP facts are permitted")
        # Reuse the PRD submission contract, including human-surface validation.
        try:
            from .prd_governance import gap_from_submission, validate_human_fields
        except ImportError:
            spec = importlib.util.spec_from_file_location("greenfield_prd_validation", Path(__file__).with_name("prd_governance.py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            gap_from_submission, validate_human_fields = module.gap_from_submission, module.validate_human_fields
        parsed = gap_from_submission(gap)
        validate_human_fields(parsed)
        if parsed["gap_id"] in seen:
            raise FactError("Duplicate PRODUCT GAP identity")
        seen.add(parsed["gap_id"])
    seen = set()
    for approval in data["approvals"]:
        if (not isinstance(approval, dict) or set(approval) != APPROVAL_FIELDS or
                not isinstance(approval["boundary"], str) or not re.fullmatch(r"[a-z][a-z0-9-]*", approval["boundary"]) or
                not isinstance(approval["subject"], str) or not ID.fullmatch(approval["subject"]) or
                approval["decision"] not in ("approve", "reject") or type(approval["human"]) is not bool or
                not _digest(approval["fingerprint"]) or not isinstance(approval["verification"], str)):
            raise FactError("Invalid human approval fact")
        inputs = approval["inputs"]
        if (not isinstance(inputs, list) or not inputs or any(not isinstance(p, str) or not p for p in inputs) or
                len(set(inputs)) != len(inputs)):
            raise FactError("Approval inputs must be unique project-relative paths")
        for path in inputs:
            if Path(path).is_absolute() or ".." in Path(path).parts or Path(path).as_posix() != path:
                raise FactError("Invalid approval input path")
        key = (approval["boundary"], approval["subject"])
        if key in seen:
            raise FactError("Duplicate current approval; replace the old fact")
        seen.add(key)
    return data


def load_facts(project: Path, registry: str = DEFAULT_REGISTRY) -> dict:
    return validate_facts(json.loads(project_file(project, registry).read_text(encoding="utf-8")))


def authority_bytes(relative: str, path: Path) -> bytes:
    if relative == "ROADMAP.md":
        # Only evaluator-owned fields are excluded; scope/dependencies/order remain bound.
        text = path.read_bytes().decode("utf-8")
        return re.sub(r"(?m)^(?:Status|Status reason|Feature spec):[^\r\n]*(?:\r?\n|$)", "", text).encode()
    if relative == "architecture/baseline.md":
        text = path.read_bytes().decode("utf-8")
        return re.sub(r"(?m)^Status: (?:Draft|Approved)[ \t]*(?:\r?\n|$)", "", text).encode()
    return path.read_bytes()


def required_inputs(boundary: str, canonical_prd: str, spec: str | None = None) -> set[str]:
    if boundary not in BOUNDARIES:
        raise FactError(f"Unsupported Greenfield boundary: {boundary}")
    required = {canonical_prd}
    if boundary != "prd":
        required.add("architecture/baseline.md")
    if boundary in {"project-ready", "human-acceptance"}:
        required.update({"ROADMAP.md", ".specify/memory/constitution.md"})
    if boundary == "human-acceptance":
        if not spec or Path(spec).name != "spec.md":
            raise FactError("Human Acceptance requires the linked Feature spec")
        folder = Path(spec).parent
        required.update({spec, (folder / "plan.md").as_posix(), (folder / "tasks.md").as_posix()})
    return required


def fingerprint(project: Path, boundary: str, subject: str, canonical_prd: str,
                inputs: list[str], spec: str | None = None) -> str:
    if not ID.fullmatch(subject) or (boundary != "human-acceptance" and subject != "foundation"):
        raise FactError("Invalid approval subject")
    if not inputs or len(set(inputs)) != len(inputs) or not required_inputs(boundary, canonical_prd, spec).issubset(inputs):
        raise FactError("Approval omits required authority inputs")
    if boundary != "human-acceptance" and set(inputs) != required_inputs(boundary, canonical_prd):
        raise FactError("Foundation approval inputs must match their authority set")
    values = {p: hashlib.sha256(authority_bytes(p, project_file(project, p))).hexdigest() for p in inputs}
    if boundary == "human-acceptance":
        # Bind additions/deletions and committed code too, not only the current diff.
        # Conservatively bind the whole project outside package/VCS metadata.
        for path in sorted(project.rglob("*")):
            relative = path.relative_to(project).as_posix()
            parts = Path(relative).parts
            if parts[0] in {".git", ".specify"} or parts[0] == ".roadmap-lifecycle.lock" or parts[0].startswith(".roadmap-lifecycle-"):
                continue
            if path.is_symlink() and not path.resolve().is_relative_to(project.resolve()):
                raise FactError(f"Escaping acceptance input: {relative}")
            if path.is_symlink():
                values[relative + "/@link"] = hashlib.sha256(os.readlink(path).encode()).hexdigest()
            if path.is_file():
                values[relative] = hashlib.sha256(authority_bytes(relative, project_file(project, relative))).hexdigest()
    body = {"boundary": boundary, "subject": subject, "canonical_prd": canonical_prd, "inputs": values}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require_approval(project: Path, data: dict, boundary: str, subject: str = "foundation",
                     *, spec: str | None = None, evidence: list[str] | None = None) -> dict:
    validate_facts(data)
    if data["product_gaps"]:
        raise FactError("Approval blocked: unresolved PRODUCT GAP")
    current_prd = hashlib.sha256(project_file(project, data["canonical_prd"]).read_bytes()).hexdigest()
    if data["prd_revision"] != current_prd:
        raise FactError("Canonical PRD decision facts are stale")
    if boundary != "prd":
        require_approval(project, data, "prd")
    if boundary in {"project-ready", "human-acceptance"}:
        require_approval(project, data, "architecture")
        baseline = project_file(project, "architecture/baseline.md").read_text()
        statuses = re.findall(r"(?m)^(?:Status:|\*\*Status:\*\*)[ \t]*([^\r\n]*)$", baseline)
        if len(statuses) != 1 or not re.fullmatch(r"Approved(?:[ \t]+[^\r\n]*)?", statuses[0]):
            raise FactError("Architecture Baseline must be explicitly Approved")
    if boundary == "human-acceptance":
        require_approval(project, data, "project-ready")
    found = [a for a in data["approvals"] if a["boundary"] == boundary and a["subject"] == subject]
    if not found or found[0]["human"] is not True or found[0]["decision"] != "approve":
        raise FactError(f"Current human {boundary} approval is required for {subject}")
    approval = found[0]
    expected_verification = "PROJECT READY" if boundary == "project-ready" else "PASS"
    if approval["verification"] != expected_verification:
        raise FactError(f"{boundary} approval lacks successful current verification")
    if evidence and not set(evidence).issubset(approval["inputs"]):
        raise FactError("Human Acceptance does not bind the required verification evidence")
    current = fingerprint(project, boundary, subject, data["canonical_prd"], approval["inputs"], spec)
    if current != approval["fingerprint"]:
        raise FactError(f"Stale {boundary} approval for {subject}")
    return approval


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fingerprint", "require"))
    parser.add_argument("boundary", choices=sorted(BOUNDARIES))
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--subject", default="foundation")
    parser.add_argument("--spec")
    parser.add_argument("--input", action="append", default=[])
    args = parser.parse_args()
    try:
        data = load_facts(args.project, args.registry)
        if args.action == "require":
            result = require_approval(args.project, data, args.boundary, args.subject, spec=args.spec)
        else:
            result = {"fingerprint": fingerprint(args.project, args.boundary, args.subject,
                      data["canonical_prd"], args.input, args.spec)}
        print(json.dumps(result))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Greenfield authorization blocked: {exc}", file=sys.stderr)
        sys.exit(1)
