#!/usr/bin/env python3
"""Plan branch protections; write only a saved, unchanged plan on explicit request."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib
import urllib.parse

DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "policy/required-checks.toml"


class Missing(Exception):
    pass


class GitHub:
    def request(self, path, method="GET", payload=None):
        cmd = ["gh", "api", "--method", method, path]
        if payload is not None:
            cmd += ["--input", "-"]
        out = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                             text=True, capture_output=True, check=False)
        if out.returncode:
            if "HTTP 404" in out.stderr:
                raise Missing(path)
            raise RuntimeError(out.stderr.strip())
        return json.loads(out.stdout) if out.stdout.strip() else None

    def get(self, path):
        return self.request(path)

    def write(self, path, method, payload):
        return self.request(path, method, payload)


def collection(api, path, field):
    found = []
    for page in range(1, 1001):
        sep = "&" if "?" in path else "?"
        batch = api.get(f"{path}{sep}per_page=100&page={page}")[field]
        found.extend(batch)
        if len(batch) < 100:
            return found
    raise ValueError("GitHub pagination exceeded the safety limit")


def load_policy(path):
    raw = Path(path).read_bytes()
    data = tomllib.loads(raw.decode())
    if data.get("version") != 1 or not re.fullmatch(r"[A-Za-z0-9_.-]+", data.get("owner", "")):
        raise ValueError("invalid policy version or owner")
    names = [p["name"] for p in data["repository"]]
    if len(set(names)) != len(names) or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", n) for n in names):
        raise ValueError("invalid or duplicate repository name")
    return data, hashlib.sha256(raw).hexdigest()


def plan_repo(api, owner, desired):
    name = desired["name"]
    result = {"repository": f"{owner}/{name}", "actions": []}
    if desired.get("deferred"):
        return dict(result, state="deferred", reason=desired["deferred"])
    base = f"repos/{owner}/{name}"
    try:
        info = api.get(base)
    except Missing:
        return dict(result, state="deferred", reason="repository not found")
    branch = info["default_branch"]
    if branch != "main":
        return dict(result, state="deferred", reason=f"default branch is {branch}, not main")
    branch_path = f"{base}/branches/{urllib.parse.quote(branch, safe='')}"
    head = api.get(branch_path)["commit"]["sha"]
    result["head"] = head
    workflow = desired["workflow"]
    if not workflow.startswith(".github/workflows/") or not workflow.endswith((".yml", ".yaml")):
        raise ValueError("workflow must name a workflow file")
    try:
        source = api.get(f"{base}/contents/{workflow}?ref={head}")
    except Missing:
        return dict(result, state="deferred", reason=f"{workflow} is absent on main")
    if not isinstance(source, dict) or source.get("type") != "file":
        return dict(result, state="deferred", reason="workflow path is not a file")
    result["workflow_blob"] = source["sha"]
    runs = collection(api, f"{base}/actions/runs?head_sha={head}", "workflow_runs")
    suites = {r["check_suite_id"] for r in runs
              if r.get("head_sha") == head and r.get("path", "").split("@", 1)[0] == workflow}
    checks = collection(api, f"{base}/commits/{head}/check-runs", "check_runs")
    required = []
    for context in desired["contexts"]:
        observed = [c for c in checks if c.get("name") == context
                    and (c.get("app") or {}).get("slug") == "github-actions"
                    and (c.get("check_suite") or {}).get("id") in suites]
        app_ids = {(c.get("app") or {}).get("id") for c in observed}
        if len(app_ids) != 1 or None in app_ids:
            return dict(result, state="deferred", reason=f"{context!r} is not an observed check of {workflow} on main")
        required.append({"context": context, "app_id": app_ids.pop()})
    if not required:
        raise ValueError("policy must specify at least one required check")
    minimum = desired["minimum_reviews"]
    if isinstance(minimum, bool) or not isinstance(minimum, int) or not 1 <= minimum <= 6:
        raise ValueError("minimum_reviews must be between 1 and 6")
    try:
        protection = api.get(branch_path + "/protection")
    except Missing:
        protection = None
    for key in ("enforce_admins", "dismiss_stale_reviews", "required_conversation_resolution"):
        if not isinstance(desired.get(key), bool):
            raise ValueError(f"{key} must be true or false")
    result["protection"] = protection
    actions = result["actions"]
    if protection is None:
        actions.append({"method": "PUT", "path": branch_path + "/protection", "payload": {
            "required_status_checks": {"strict": False, "checks": required},
            "enforce_admins": bool(desired["enforce_admins"]),
            "required_pull_request_reviews": {"required_approving_review_count": minimum,
                                              "dismiss_stale_reviews": desired["dismiss_stale_reviews"]},
            "required_conversation_resolution": desired["required_conversation_resolution"],
            "restrictions": None}})
    else:
        status = protection.get("required_status_checks") or {}
        merged = copy.deepcopy(status.get("checks") or [])
        for check in merged:
            # GitHub reports a check that any source may set with app_id null;
            # it accepts -1 for that on write.
            if check.get("app_id") is None:
                check["app_id"] = -1
        for context in status.get("contexts") or []:
            if not any(c["context"] == context for c in merged):
                merged.append({"context": context, "app_id": -1})
        changed = False
        for check in required:
            existing = [c for c in merged if c["context"] == check["context"]]
            if existing and any(c.get("app_id", -1) not in (-1, None, check["app_id"]) for c in existing):
                return dict(result, state="deferred", reason=f"{check['context']} already belongs to a different app", actions=[])
            if not existing:
                merged.append(check)
                changed = True
        if changed:
            actions.append({"method": "PATCH", "path": branch_path + "/protection/required_status_checks",
                            "payload": {"strict": bool(status.get("strict", False)), "checks": merged}})
        reviews = protection.get("required_pull_request_reviews") or {}
        if reviews.get("required_approving_review_count", 0) < minimum:
            actions.append({"method": "PATCH", "path": branch_path + "/protection/required_pull_request_reviews",
                            "payload": {"required_approving_review_count": minimum}})
        if desired["enforce_admins"] and not (protection.get("enforce_admins") or {}).get("enabled"):
            actions.append({"method": "POST", "path": branch_path + "/protection/enforce_admins", "payload": None})
    return dict(result, state="ready" if actions else "unchanged")


def plan(api, policy_path, selected):
    policy, digest = load_policy(policy_path)
    names = [p["name"] for p in policy["repository"]]
    if selected and not set(selected) <= set(names):
        raise ValueError("selected repository is not in the policy")
    repos = [p for p in policy["repository"] if not selected or p["name"] in selected]
    return {"version": 1, "policy_sha256": digest, "selected": sorted(selected or names),
            "repositories": [plan_repo(api, policy["owner"], dict(policy["defaults"], **p)) for p in repos]}


def apply_saved(api, policy_path, saved):
    # Recompute all actions from the policy, never execute payloads supplied
    # by an edited plan. No writes occur if any read, SHA or setting drifted.
    if not isinstance(saved, dict) or not isinstance(saved.get("selected"), list):
        raise ValueError("saved plan must contain a repository selection")
    current = plan(api, policy_path, saved["selected"])
    if current != saved:
        raise ValueError("live state or policy changed; save and review a fresh dry-run plan")
    if any(r["state"] == "deferred" for r in current["repositories"]):
        raise ValueError("plan contains deferred repositories; select only ready repositories")
    for repo in current["repositories"]:
        base = "repos/" + repo["repository"] + "/branches/main"
        try:
            protection = api.get(base + "/protection")
        except Missing:
            protection = None
        if protection != repo["protection"]:
            raise ValueError("protection changed during apply; stop and create a fresh plan")
        for action in repo["actions"]:
            # Recheck the head before each write. GitHub has no atomic
            # compare-and-swap for branch protection; see the operator notes.
            base = "repos/" + repo["repository"] + "/branches/main"
            if api.get(base)["commit"]["sha"] != repo["head"]:
                raise ValueError("main changed during apply; stop and create a fresh plan")
            api.write(action["path"], action["method"], action["payload"])
    return current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--repo", action="append", default=[], help="repository short name; repeat to select")
    parser.add_argument("--write-plan", type=Path, help="save the read-only plan for review")
    parser.add_argument("--apply-plan", type=Path, help="explicitly apply an unchanged saved plan")
    args = parser.parse_args()
    if args.apply_plan and (args.repo or args.write_plan):
        parser.error("--apply-plan cannot be combined with --repo or --write-plan")
    try:
        api = GitHub()
        result = (apply_saved(api, args.policy, json.loads(args.apply_plan.read_text())) if args.apply_plan
                  else plan(api, args.policy, args.repo))
        output = json.dumps(result, indent=2) + "\n"
        if args.write_plan:
            args.write_plan.write_text(output)
        print(output, end="")
        return 2 if any(r["state"] == "deferred" for r in result["repositories"]) else 0
    except (ValueError, RuntimeError, Missing, OSError, KeyError, TypeError, AttributeError) as e:
        parser.exit(1, f"No further changes applied: {e}\n")


if __name__ == "__main__":
    raise SystemExit(main())
