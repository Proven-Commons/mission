"""Safety tests for the read-only planner and explicit branch-policy apply."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[2] / "tools/reconcile_required_checks.py"
spec = importlib.util.spec_from_file_location("policy", SOURCE)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class FakeGitHub:
    def __init__(self):
        self.head = "a" * 40
        self.contexts = ["self-test", "lean-self-test", "template / bar"]
        self.workflow = ".github/workflows/ci.yml"
        self.workflow_exists = True
        self.suite_path = self.workflow
        self.app = "github-actions"
        self.protection = {
            "required_status_checks": {"strict": True, "contexts": ["external"],
                                       "checks": [{"context": "external", "app_id": 77}]},
            "required_pull_request_reviews": {"required_approving_review_count": 1,
                                               "dismiss_stale_reviews": True,
                                               "require_code_owner_reviews": True},
            "enforce_admins": {"enabled": True},
            "restrictions": {"users": ["owner"]}, "required_linear_history": {"enabled": True}}
        self.writes = []
        self.reads = []

    def get(self, path):
        self.reads.append(path)
        if "/contents/" in path:
            if not self.workflow_exists:
                raise policy.Missing(path)
            return {"type": "file", "sha": "workflow-blob"}
        if "/actions/runs?" in path:
            return {"workflow_runs": [{"head_sha": self.head, "path": self.suite_path, "check_suite_id": 9}]}
        if "/check-runs?" in path:
            return {"check_runs": [{"name": c, "app": {"id": 15368, "slug": self.app},
                                    "check_suite": {"id": 9}} for c in self.contexts]}
        if path.endswith("/protection"):
            if self.protection is None:
                raise policy.Missing(path)
            return copy.deepcopy(self.protection)
        if "/branches/" in path:
            return {"commit": {"sha": self.head}}
        return {"default_branch": "main"}

    def write(self, path, method, payload):
        self.writes.append((path, method, copy.deepcopy(payload)))


class ProtectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "policy.toml"
        self.path.write_text('''version = 1
owner = "Proven-Commons"
[defaults]
minimum_reviews = 1
enforce_admins = true
dismiss_stale_reviews = true
required_conversation_resolution = true
workflow = ".github/workflows/ci.yml"
contexts = ["self-test", "lean-self-test", "template / bar"]
[[repository]]
name = "mission"
''')
        self.api = FakeGitHub()

    def plan(self):
        return policy.plan(self.api, self.path, ["mission"])

    def test_default_planning_never_writes(self):
        result = self.plan()
        self.assertEqual(result["repositories"][0]["state"], "ready")
        self.assertEqual(self.api.writes, [])

    def test_merge_keeps_other_contexts_app_bindings_and_strict_mode(self):
        repo = self.plan()["repositories"][0]
        self.assertEqual(len(repo["actions"]), 1)
        action = repo["actions"][0]
        self.assertEqual(action["method"], "PATCH")
        self.assertTrue(action["payload"]["strict"])
        self.assertIn({"context": "external", "app_id": 77}, action["payload"]["checks"])
        self.assertEqual(len(action["payload"]["checks"]), 4)
        # No PUT of a reduced protection object can erase unrelated settings.
        self.assertTrue(action["path"].endswith("/required_status_checks"))

    def test_missing_workflow_is_deferred(self):
        self.api.workflow_exists = False
        self.assertEqual(self.plan()["repositories"][0]["state"], "deferred")
        self.assertEqual(self.api.writes, [])

    def test_unobserved_required_context_is_deferred(self):
        self.api.contexts.remove("template / bar")
        self.assertEqual(self.plan()["repositories"][0]["state"], "deferred")

    def test_same_context_from_other_workflow_is_not_accepted(self):
        self.api.suite_path = ".github/workflows/other.yml"
        self.assertEqual(self.plan()["repositories"][0]["state"], "deferred")

    def test_same_context_from_other_app_is_not_accepted(self):
        self.api.app = "external-service"
        self.assertEqual(self.plan()["repositories"][0]["state"], "deferred")

    def test_existing_binding_to_another_app_is_not_replaced(self):
        self.api.protection["required_status_checks"]["checks"].append({"context": "self-test", "app_id": 8})
        repo = self.plan()["repositories"][0]
        self.assertEqual(repo["state"], "deferred")
        self.assertEqual(repo["actions"], [])

    def test_apply_rejects_changed_head_before_any_write(self):
        saved = self.plan()
        self.api.head = "b" * 40
        with self.assertRaisesRegex(ValueError, "changed"):
            policy.apply_saved(self.api, self.path, saved)
        self.assertEqual(self.api.writes, [])

    def test_apply_rejects_changed_settings_before_any_write(self):
        saved = self.plan()
        self.api.protection["required_status_checks"]["contexts"].append("new-external")
        with self.assertRaisesRegex(ValueError, "changed"):
            policy.apply_saved(self.api, self.path, saved)
        self.assertEqual(self.api.writes, [])

    def test_tampered_plan_cannot_supply_writes(self):
        saved = self.plan()
        saved["repositories"][0]["actions"][0]["payload"]["checks"] = []
        with self.assertRaisesRegex(ValueError, "changed"):
            policy.apply_saved(self.api, self.path, saved)
        self.assertEqual(self.api.writes, [])

    def test_policy_change_invalidates_saved_plan(self):
        saved = self.plan()
        self.path.write_text(self.path.read_text() + "\n# changed policy\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            policy.apply_saved(self.api, self.path, saved)
        self.assertEqual(self.api.writes, [])

    def test_explicit_apply_writes_only_the_planned_narrow_patch(self):
        saved = self.plan()
        before = copy.deepcopy(self.api.protection)
        policy.apply_saved(self.api, self.path, saved)
        self.assertEqual(len(self.api.writes), 1)
        self.assertEqual(self.api.writes[0][1], "PATCH")
        self.assertEqual(self.api.protection, before)
        self.assertNotIn("required_pull_request_reviews", self.api.writes[0][2])

    def test_main_moving_during_apply_aborts_before_write(self):
        saved = self.plan()
        original_get = self.api.get
        branch_reads = 0
        def get(path):
            nonlocal branch_reads
            if path.endswith("/branches/main"):
                branch_reads += 1
                if branch_reads == 2:
                    self.api.head = "b" * 40
            return original_get(path)
        self.api.get = get
        with self.assertRaisesRegex(ValueError, "main changed"):
            policy.apply_saved(self.api, self.path, saved)
        self.assertEqual(self.api.writes, [])

    def test_protection_moving_during_apply_aborts_before_write(self):
        saved = self.plan()
        original_get = self.api.get
        protection_reads = 0
        def get(path):
            nonlocal protection_reads
            if path.endswith("/protection"):
                protection_reads += 1
                if protection_reads == 2:
                    self.api.protection["required_linear_history"]["enabled"] = False
            return original_get(path)
        self.api.get = get
        with self.assertRaisesRegex(ValueError, "protection changed"):
            policy.apply_saved(self.api, self.path, saved)
        self.assertEqual(self.api.writes, [])

    def test_already_satisfied_policy_is_unchanged(self):
        status = self.api.protection["required_status_checks"]
        status["checks"] += [{"context": c, "app_id": 15368} for c in self.api.contexts]
        self.assertEqual(self.plan()["repositories"][0]["state"], "unchanged")

    def test_review_minimum_never_lowers_existing_reviews(self):
        self.api.protection["required_pull_request_reviews"]["required_approving_review_count"] = 3
        repo = self.plan()["repositories"][0]
        self.assertFalse(any(a["path"].endswith("required_pull_request_reviews") for a in repo["actions"]))

    def test_missing_reviews_are_added_without_changing_other_review_options(self):
        self.api.protection["required_pull_request_reviews"]["required_approving_review_count"] = 0
        actions = self.plan()["repositories"][0]["actions"]
        review = next(a for a in actions if a["path"].endswith("required_pull_request_reviews"))
        self.assertEqual(review["payload"], {"required_approving_review_count": 1})

    def test_unprotected_branch_has_an_explicit_initial_protection_plan(self):
        self.api.protection = None
        action = self.plan()["repositories"][0]["actions"][0]
        self.assertEqual(action["method"], "PUT")
        self.assertTrue(action["payload"]["enforce_admins"])
        self.assertEqual(action["payload"]["required_pull_request_reviews"]["required_approving_review_count"], 1)
        # The first protection must match the org baseline: an approval on an
        # older head does not count, and open conversations block a merge.
        self.assertIs(action["payload"]["required_pull_request_reviews"]["dismiss_stale_reviews"], True)
        self.assertIs(action["payload"]["required_conversation_resolution"], True)

    def test_initial_protection_settings_must_be_booleans(self):
        self.api.protection = None
        self.path.write_text(self.path.read_text().replace("dismiss_stale_reviews = true", 'dismiss_stale_reviews = "yes"'))
        with self.assertRaisesRegex(ValueError, "dismiss_stale_reviews"):
            self.plan()

    def test_any_source_check_is_sent_back_as_minus_one(self):
        self.api.protection["required_status_checks"]["checks"].append({"context": "legacy", "app_id": None})
        actions = self.plan()["repositories"][0]["actions"]
        patch = next(a for a in actions if a["path"].endswith("required_status_checks"))
        self.assertIn({"context": "legacy", "app_id": -1}, patch["payload"]["checks"])
        self.assertNotIn(None, [c["app_id"] for c in patch["payload"]["checks"]])

    def test_workflow_path_that_is_a_directory_is_deferred(self):
        real_get = self.api.get
        self.api.get = lambda path: [] if "/contents/" in path else real_get(path)
        self.assertEqual(self.plan()["repositories"][0]["state"], "deferred")

    def test_missing_repository_is_deferred_not_fatal(self):
        real_get = self.api.get
        def get(path):
            if path == "repos/Proven-Commons/mission":
                raise policy.Missing(path)
            return real_get(path)
        self.api.get = get
        repo = self.plan()["repositories"][0]
        self.assertEqual((repo["state"], repo["reason"]), ("deferred", "repository not found"))

    def test_tar_stays_deferred_until_policy_is_reviewed_after_landing(self):
        self.path.write_text(self.path.read_text() + '\n[[repository]]\nname = "tar"\ndeferred = "Set B not landed"\n')
        result = policy.plan(self.api, self.path, ["tar"])
        self.assertEqual(result["repositories"][0]["state"], "deferred")
        self.assertEqual(self.api.reads, [])
        with self.assertRaisesRegex(ValueError, "deferred"):
            policy.apply_saved(self.api, self.path, result)
        self.assertEqual(self.api.writes, [])
