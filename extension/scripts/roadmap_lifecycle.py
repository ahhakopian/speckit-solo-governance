"""Greenfield-owned, narrowly scoped ROADMAP status transitions.

ROADMAP entries use an explicit marker and four single-line lifecycle fields.
Everything else in ROADMAP.md is preserved verbatim.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ENTRY = re.compile(r"^<!-- roadmap-entry: ([A-Za-z][A-Za-z0-9_-]*) -->\s*$")
FIELD = re.compile(r"^(Status|Status reason|Depends on|Feature spec|Start requires):[ \t]*(.*?)[ \t]*\r?\n?$")
SPEC_ID = re.compile(r"^ROADMAP entry:[ \t]*([A-Za-z][A-Za-z0-9_-]*)[ \t]*$", re.MULTILINE)
TASK = re.compile(r"^[ \t]*-[ \t]*\[([ xX])\][ \t]+T\d+\b", re.MULTILINE)
OPEN_CHECKBOX = re.compile(r"^[ \t]*-[ \t]*\[ \]", re.MULTILINE)
STATUSES = {"planned", "ready", "active", "blocked", "deferred", "done"}


class LifecycleError(ValueError):
    pass


def verification_disposition(text: str, has_proof: bool) -> str | None:
    """Project-owned adoption classification; never resolves optional platform code."""
    sections = re.findall(r"(?ms)^## Verification Integration[^\S\n]*\n(.*?)(?=^## |\Z)", text)
    if not sections and not has_proof:
        return None  # Preserve existing unadopted features.
    if len(sections) != 1:
        raise LifecycleError("Verification Plan reconciliation required: exactly one applicability section required")
    values = re.findall(r"(?mi)^Applicability:[ \t]*(.*?)[ \t]*$", sections[0])
    if len(values) != 1 or values[0].lower() not in {"applicable", "not applicable"}:
        raise LifecycleError("Verification Plan reconciliation required: exactly one valid applicability required")
    disposition = values[0].lower()
    if disposition == "not applicable":
        if not re.search(r"(?mi)^Reason:[ \t]*\S[^\n]*$", sections[0]):
            raise LifecycleError("Verification Plan reconciliation required: missing non-applicability reason")
        if has_proof:
            raise LifecycleError("Verification Plan reconciliation required: contradictory proof artifact")
    return disposition


@dataclass
class RoadmapEntry:
    id: str
    fields: dict[str, str]
    lines: dict[str, int]


class Roadmap:
    def __init__(self, source: str):
        self.source = source
        self.text = source
        self.rows = source.splitlines(keepends=True)
        self.entries: dict[str, RoadmapEntry] = {}
        markers = [(i, match.group(1)) for i, row in enumerate(self.rows)
                   if (match := ENTRY.fullmatch(row.rstrip("\r\n")))]
        if not markers:
            raise LifecycleError("ROADMAP has no <!-- roadmap-entry: ID --> markers")
        for number, (start, feature_id) in enumerate(markers):
            if feature_id in self.entries:
                raise LifecycleError(f"Duplicate ROADMAP ID: {feature_id}")
            end = markers[number + 1][0] if number + 1 < len(markers) else len(self.rows)
            fields: dict[str, str] = {}
            lines: dict[str, int] = {}
            for index in range(start + 1, end):
                match = FIELD.fullmatch(self.rows[index])
                if not match:
                    continue
                key, value = match.groups()
                if key in fields:
                    raise LifecycleError(f"{feature_id}: duplicate {key} field")
                fields[key] = value.strip()
                lines[key] = index
            for required in ("Status", "Status reason", "Depends on", "Feature spec"):
                if required not in fields:
                    raise LifecycleError(f"{feature_id}: missing {required} field")
            if fields["Status"] not in STATUSES:
                raise LifecycleError(f"{feature_id}: invalid status {fields['Status']!r}")
            if fields["Status"] in {"blocked", "deferred"} and not fields["Status reason"]:
                raise LifecycleError(f"{feature_id}: {fields['Status']} needs a reason")
            self.entries[feature_id] = RoadmapEntry(feature_id, fields, lines)
        self._validate_graph()

    def _dependencies(self, entry: RoadmapEntry) -> list[str]:
        value = entry.fields["Depends on"]
        return [] if value.lower() == "none" else [part.strip() for part in value.split(",")]

    def _validate_graph(self) -> None:
        for entry in self.entries.values():
            deps = self._dependencies(entry)
            if any(not dep or dep not in self.entries for dep in deps):
                raise LifecycleError(f"{entry.id}: unknown or empty dependency")
            if len(deps) != len(set(deps)):
                raise LifecycleError(f"{entry.id}: duplicate dependency")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(feature_id: str) -> None:
            if feature_id in visiting:
                raise LifecycleError(f"Dependency cycle at {feature_id}")
            if feature_id in visited:
                return
            visiting.add(feature_id)
            for dep in self._dependencies(self.entries[feature_id]):
                visit(dep)
            visiting.remove(feature_id)
            visited.add(feature_id)

        for feature_id in self.entries:
            visit(feature_id)

    def _set(self, entry: RoadmapEntry, field: str, value: str) -> None:
        index = entry.lines[field]
        old = self.rows[index]
        ending = "\r\n" if old.endswith("\r\n") else "\n" if old.endswith("\n") else ""
        self.rows[index] = f"{field}: {value}{ending}"
        entry.fields[field] = value

    def readiness(self, entry: RoadmapEntry, project: Path) -> list[str]:
        reasons = [f"waiting for {dep}" for dep in self._dependencies(entry)
                   if self.entries[dep].fields["Status"] != "done"]
        extra = entry.fields.get("Start requires", "none")
        if extra.lower() != "none":
            for condition in (part.strip() for part in extra.split(",")):
                if not condition.startswith("file:"):
                    raise LifecycleError(f"{entry.id}: unsupported start condition {condition!r}")
                relative = condition[5:]
                candidate = safe_project_file(project, relative, must_exist=False)
                if not candidate.is_file():
                    reasons.append(f"missing start requirement {relative}")
        return reasons

    def promote(self, feature_id: str, project: Path) -> dict:
        entry = self.entries[feature_id]
        if entry.fields["Status"] != "planned":
            return {"id": feature_id, "status": entry.fields["Status"], "changed": False}
        reasons = self.readiness(entry, project)
        next_status = "ready" if not reasons else "planned"
        reason = "prerequisites satisfied" if not reasons else "; ".join(reasons)
        changed = (entry.fields["Status"] != next_status or entry.fields["Status reason"] != reason)
        if changed:
            self._set(entry, "Status", next_status)
            self._set(entry, "Status reason", reason)
        return {"id": feature_id, "status": next_status, "changed": changed, "reason": reason}

    def render(self) -> str:
        return "".join(self.rows)


def safe_project_file(project: Path, relative: str, *, must_exist: bool = True) -> Path:
    if not relative or Path(relative).is_absolute():
        raise LifecycleError(f"Invalid project-relative path: {relative!r}")
    path = (project / relative).resolve()
    if not path.is_relative_to(project.resolve()):
        raise LifecycleError(f"Path escapes project: {relative!r}")
    if must_exist and not path.is_file():
        raise LifecycleError(f"Required file is missing: {relative}")
    return path


def approved_project_ready(project: Path, run_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise LifecycleError("Invalid workflow run ID")
    run_dir = project / ".specify" / "workflows" / "runs" / run_id
    data = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    if data.get("run_id") != run_id or data.get("workflow_id") != "greenfield-bootstrap":
        raise LifecycleError("PROJECT READY state does not belong to this workflow run")
    steps = data.get("step_results", {})
    gate = steps.get("project-ready", {})
    if gate.get("status") != "completed" or gate.get("output", {}).get("choice") != "approve":
        raise LifecycleError("PROJECT READY gate was not approved")


def require_clean_tasks(project: Path, spec_relative: str) -> None:
    tasks = safe_project_file(project, str(Path(spec_relative).parent / "tasks.md"))
    content = tasks.read_text(encoding="utf-8")
    found = TASK.findall(content)
    if not found:
        raise LifecycleError("No numbered tasks found in tasks.md")
    if any(mark == " " for mark in found) or OPEN_CHECKBOX.search(content):
        raise LifecycleError("tasks.md has incomplete tasks")


def foundation_facts(project: Path):
    installed = project / ".specify/extensions/greenfield-foundation/scripts/governance_facts.py"
    source = Path(__file__).resolve().parents[2] / "foundation/scripts/governance_facts.py"
    path = installed if installed.is_file() else source
    if not path.is_file():
        raise LifecycleError("Install greenfield-foundation to consume repository-native approval facts")
    module_spec = importlib.util.spec_from_file_location("greenfield_facts", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def lifecycle_config(project: Path) -> dict:
    path = project / ".specify/extensions/greenfield-roadmap-lifecycle/greenfield-roadmap-lifecycle-config.yml"
    config = {"completion_mode": "automatic", "approval_registry": ".specify/governance/hitl.json"}
    if path.exists():
        import yaml
        safe_project_file(project, path.relative_to(project).as_posix())
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise LifecycleError("Invalid ROADMAP lifecycle configuration") from exc
        if not isinstance(loaded, dict) or set(loaded) - set(config):
            raise LifecycleError("Invalid ROADMAP lifecycle configuration")
        config.update(loaded)
    if not isinstance(config["completion_mode"], str) or config["completion_mode"] not in {"automatic", "human"}:
        raise LifecycleError("completion_mode must be automatic or human")
    registry = config["approval_registry"]
    if not isinstance(registry, str) or not registry.startswith(".specify/"):
        raise LifecycleError("approval_registry must be a project-relative .specify/ path")
    safe_project_file(project, registry, must_exist=False)
    return config


def require_human_acceptance(project: Path, entry: RoadmapEntry, evidence: list[str]) -> None:
    config = lifecycle_config(project)
    if config["completion_mode"] == "human":
        facts = foundation_facts(project)
        facts.require_approval(project, facts.load_facts(project, config["approval_registry"]),
                               "human-acceptance", entry.id,
                               spec=entry.fields["Feature spec"], evidence=evidence)


def require_native_project_ready(project: Path, registry: str) -> None:
    facts = foundation_facts(project)
    facts.require_approval(project, facts.load_facts(project, registry), "project-ready")


def verify_completion(roadmap: Roadmap, project: Path, args: argparse.Namespace) -> dict:
    entry = roadmap.entries[args.feature_id]
    if entry.fields["Status"] not in {"active", "done"}:
        raise LifecycleError(f"{entry.id}: completion requires active status")
    checks = {
        "clean converge": args.converge == "clean",
        "Greenfield COMPATIBLE": args.compatibility == "COMPATIBLE",
        "Feature Governance after_tasks PASS": args.feature_after_tasks == "PASS",
        "Feature Governance before_implement PASS": args.feature_before_implement == "PASS",
        "MVP Governance before_implement PASS": args.mvp_before_implement == "PASS",
        "MVP Governance after_implement PASS": args.mvp_after_implement == "PASS",
        "required verification PASS": args.verification == "PASS",
        "no unresolved blockers": args.blockers == "none",
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        return {"action": "verify", "id": entry.id, "changed": False,
                "status": entry.fields["Status"], "blockers": failed}
    if entry.fields["Feature spec"].lower() == "none":
        raise LifecycleError(f"{entry.id}: Feature spec link is missing")
    spec = safe_project_file(project, entry.fields["Feature spec"])
    if SPEC_ID.findall(spec.read_text(encoding="utf-8")) != [entry.id]:
        raise LifecycleError(f"{entry.id}: linked spec must identify exactly this ROADMAP entry")
    require_clean_tasks(project, entry.fields["Feature spec"])
    if not args.evidence:
        raise LifecycleError("Required verification evidence was not identified")
    for relative in args.evidence:
        safe_project_file(project, relative)
    proof_plan = spec.parent / "browser-verification-plan.json"
    plan_path = spec.parent / "plan.md"
    plan_text = plan_path.read_text(encoding="utf-8") if plan_path.is_file() else ""
    disposition = verification_disposition(plan_text, proof_plan.is_file())
    if disposition == "applicable" and not proof_plan.is_file():
        raise LifecycleError("Applicable feature verification is blocked: browser-verification-plan.json is missing")
    if proof_plan.is_file():
        # Transient ordinary platform result-validation invocation, not a
        # persisted handoff registry or another lifecycle/approval category.
        entrypoint = os.environ.get("VERIFICATION_PLATFORM_RESULT_VALIDATOR")
        request_json = os.environ.get("VERIFICATION_PLATFORM_RESULT_REQUEST")
        if not entrypoint or not request_json:
            raise LifecycleError("Required current platform result validation is unavailable")
        try:
            request = json.loads(request_json)
            request["planBytes"] = proof_plan.read_text(encoding="utf-8")
            request["binding"] = json.loads(safe_project_file(project, ".verification/platform.json").read_text(encoding="utf-8"))
            request["projectRoot"] = str(project.resolve())
            supplied = [safe_project_file(project, path) for path in args.evidence]
            published = []
            for path in supplied:
                try:
                    published.append(json.loads(path.read_text(encoding="utf-8")))
                except (ValueError, UnicodeDecodeError):
                    pass
            if request["result"] not in published or request["manifest"] not in published:
                raise ValueError("Current result and complete manifest must be published evidence inputs")
            if ".verification/platform.json" not in args.evidence:
                raise ValueError("Current neutral binding must be an explicit evidence/acceptance input")
            # The platform owns proof adequacy. The process adapter owns stable
            # publication and the existing explicit acceptance input boundary.
            required_ids = {evidence_id for claim in request["result"].get("claims", [])
                            for evidence_id in claim["evidenceIds"]}
            envelopes = {item["evidenceId"]: item for item in request.get("evidence", [])}
            for evidence_id in required_ids:
                envelope = envelopes[evidence_id]
                if envelope not in published:
                    raise ValueError("Required evidence envelope must be a published acceptance input: " + evidence_id)
                attachment = (Path(request["outputRoot"]) / envelope["attachment"]["path"]).resolve()
                if attachment not in supplied:
                    raise ValueError("Required evidence attachment must be a published acceptance input: " + evidence_id)
            for record in request.get("records", []):
                if record not in published:
                    raise ValueError("Current claim records must be published acceptance inputs")
            for config in request["assignment"]["providers"]:
                if not Path(config["entry"]).is_absolute():
                    safe_project_file(project, config["entry"])
                elif not Path(config["entry"]).is_file():
                    raise ValueError("Required provider support is not delivered")
            result = subprocess.run(["node", entrypoint], input=json.dumps(request), capture_output=True, text=True, timeout=30)
            report = json.loads(result.stdout)
            if result.returncode or report.get("valid") is not True or report.get("verdict") != "PASS":
                raise ValueError("Required proof cannot become verification PASS: " + json.dumps(report))
        except (ValueError, KeyError, TypeError, AttributeError, OSError, subprocess.TimeoutExpired) as exc:
            raise LifecycleError("Platform verification blocked: " + str(exc)) from exc
    if roadmap.readiness(entry, project):
        raise LifecycleError(f"{entry.id}: dependencies or start requirements are no longer satisfied")
    return {"action": "verify", "id": entry.id, "changed": False,
            "status": entry.fields["Status"], "ready_for_acceptance": True}


def transition(roadmap: Roadmap, project: Path, args: argparse.Namespace) -> dict:
    if args.action == "initial":
        run_id, registry = getattr(args, "run_id", None), getattr(args, "registry", None)
        if bool(run_id) == bool(registry):
            raise LifecycleError("Select exactly one Project Ready authorization source")
        if registry:
            require_native_project_ready(project, registry)
        else:
            approved_project_ready(project, run_id)
        changes = [roadmap.promote(feature_id, project) for feature_id in roadmap.entries]
        return {"action": "initial", "entries": changes}

    if args.feature_id not in roadmap.entries:
        raise LifecycleError(f"Unknown ROADMAP ID: {args.feature_id}")
    entry = roadmap.entries[args.feature_id]

    if args.action == "hook" and args.converge == "tasks_appended":
        lifecycle_config(project)  # invalid configuration never falls back to completion
        if entry.fields["Status"] != "active":
            raise LifecycleError(f"{entry.id}: corrective tasks require active status")
        spec = safe_project_file(project, entry.fields["Feature spec"])
        if SPEC_ID.findall(spec.read_text(encoding="utf-8")) != [entry.id]:
            raise LifecycleError(f"{entry.id}: linked spec must identify exactly this ROADMAP entry")
        return {"action": "hook", "id": entry.id, "changed": False,
                "status": "active", "converge": "tasks_appended"}

    if args.action == "start":
        config = lifecycle_config(project)
        if config["completion_mode"] == "human":
            require_native_project_ready(project, config["approval_registry"])
        if entry.fields["Status"] == "active" and entry.fields["Feature spec"] == args.spec:
            return {"action": "start", "id": args.feature_id, "changed": False, "status": "active"}
        if entry.fields["Status"] != "ready":
            raise LifecycleError(f"{entry.id}: specify requires ready status")
        if roadmap.readiness(entry, project):
            raise LifecycleError(f"{entry.id}: readiness prerequisites changed")
        if entry.fields["Feature spec"].lower() != "none":
            raise LifecycleError(f"{entry.id}: Feature spec link already exists")
        spec = safe_project_file(project, args.spec)
        if spec.name != "spec.md":
            raise LifecycleError("Feature spec link must name spec.md")
        matches = SPEC_ID.findall(spec.read_text(encoding="utf-8"))
        if matches != [entry.id]:
            raise LifecycleError(f"{entry.id}: spec must identify exactly this ROADMAP entry")
        if any(other.id != entry.id and other.fields["Feature spec"] == args.spec
               for other in roadmap.entries.values()):
            raise LifecycleError(f"{entry.id}: Feature spec is linked to another entry")
        checklist = safe_project_file(project, str(Path(args.spec).parent / "checklists" / "requirements.md"))
        if re.search(r"(?m)^\s*- \[ \]", checklist.read_text(encoding="utf-8")):
            raise LifecycleError("Specification quality checklist is incomplete")
        roadmap._set(entry, "Feature spec", args.spec)
        roadmap._set(entry, "Status", "active")
        roadmap._set(entry, "Status reason", "specify completed")
        return {"action": "start", "id": entry.id, "changed": True, "status": "active"}

    if args.action in {"complete", "hook"} and entry.fields["Status"] == "done":
        require_human_acceptance(project, entry, args.evidence)
        return {"action": "complete", "id": entry.id, "changed": False, "status": "done", "dependents": []}
    result = verify_completion(roadmap, project, args)
    result["action"] = args.action
    if result.get("blockers") or args.action == "verify":
        return result
    if args.action == "hook" and lifecycle_config(project)["completion_mode"] == "human":
        try:
            require_human_acceptance(project, entry, args.evidence)
        except ValueError:
            result["human_acceptance_required"] = True
        else:
            result["human_acceptance_required"] = False
        return result  # even current acceptance leaves mutation to explicit complete
    require_human_acceptance(project, entry, args.evidence)
    roadmap._set(entry, "Status", "done")
    roadmap._set(entry, "Status reason", "governed Feature completion passed")
    dependents = [roadmap.promote(other.id, project) for other in roadmap.entries.values()
                  if entry.id in roadmap._dependencies(other)]
    return {"action": "complete", "id": entry.id, "changed": True,
            "status": "done", "dependents": dependents}


def apply(project: Path, args: argparse.Namespace, *, before_write=None) -> dict:
    if args.action == "config":
        return lifecycle_config(project)
    if args.action == "verify" or (args.action == "hook" and (
            args.converge == "tasks_appended" or lifecycle_config(project)["completion_mode"] == "human")):
        # Verification is read-only, including no lifecycle lock/temp files.
        roadmap = Roadmap((project / "ROADMAP.md").read_text(encoding="utf-8"))
        return transition(roadmap, project, args)
    lock_path = project / ".roadmap-lifecycle.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise LifecycleError("Another ROADMAP lifecycle writer is active; rerun") from exc
    try:
        return _apply_locked(project, args, before_write=before_write)
    finally:
        os.close(lock_fd)
        lock_path.unlink()


def _apply_locked(project: Path, args: argparse.Namespace, *, before_write=None) -> dict:
    path = project / "ROADMAP.md"
    source_bytes = path.read_bytes()
    source = source_bytes.decode("utf-8")
    roadmap = Roadmap(source)
    result = transition(roadmap, project, args)
    updated_bytes = roadmap.render().encode("utf-8")
    if updated_bytes == source_bytes:
        return result
    if before_write is not None:
        before_write()
    recheck_authorization(project, roadmap, args)
    if path.read_bytes() != source_bytes:
        raise LifecycleError("ROADMAP changed during lifecycle evaluation; rerun")
    fd, temporary = tempfile.mkstemp(prefix=".roadmap-lifecycle-", dir=project)
    try:
        os.fchmod(fd, path.stat().st_mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(updated_bytes)
        if path.read_bytes() != source_bytes:
            raise LifecycleError("ROADMAP changed before lifecycle write; rerun")
        recheck_authorization(project, roadmap, args)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return result


def recheck_authorization(project: Path, roadmap: Roadmap, args: argparse.Namespace) -> None:
    """Recheck current authority immediately before committing lifecycle changes."""
    if args.action == "initial" and getattr(args, "registry", None):
        require_native_project_ready(project, args.registry)
    elif args.action == "start":
        config = lifecycle_config(project)
        if config["completion_mode"] == "human":
            require_native_project_ready(project, config["approval_registry"])
    elif args.action in {"complete", "hook"}:
        require_human_acceptance(project, roadmap.entries[args.feature_id], args.evidence)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--project", type=Path, default=Path.cwd())
    actions = command.add_subparsers(dest="action", required=True)
    actions.add_parser("config")
    initial = actions.add_parser("initial")
    initial.add_argument("run_id", nargs="?")
    initial.add_argument("--registry", help="Repository-native Project Ready facts; excludes run_id")
    start = actions.add_parser("start")
    start.add_argument("feature_id")
    start.add_argument("spec")
    for action in ("verify", "complete", "hook"):
        check = actions.add_parser(action)
        check.add_argument("feature_id")
        check.add_argument("--converge", default="unknown")
        check.add_argument("--compatibility", default="unknown")
        check.add_argument("--feature-after-tasks", default="unknown")
        check.add_argument("--feature-before-implement", default="unknown")
        check.add_argument("--mvp-before-implement", default="unknown")
        check.add_argument("--mvp-after-implement", default="unknown")
        check.add_argument("--verification", default="unknown")
        check.add_argument("--blockers", default="unknown")
        check.add_argument("--evidence", action="append", default=[])
    return command


if __name__ == "__main__":
    try:
        options = parser().parse_args()
        if options.action == "initial" and bool(options.run_id) == bool(options.registry):
            raise LifecycleError("Select exactly one Project Ready authorization source")
        print(json.dumps(apply(options.project.resolve(), options), ensure_ascii=False))
    except (LifecycleError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ROADMAP lifecycle blocked: {exc}", file=sys.stderr)
        sys.exit(1)
