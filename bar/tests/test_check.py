"""Self-tests for bar/check.py.

Each test copies the template project, plants one change, and checks the
status the checker gives. Run from the repo root:

    python3 -m unittest discover -s bar/tests -v

The tests marked Lean build the project and run `lake comparator`. They
run only when BAR_LEAN=1 is set, and need elan and bubblewrap.
"""

import contextlib
import importlib.util
import io
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BAR = Path(__file__).resolve().parent.parent
TEMPLATE = BAR / "template"
spec = importlib.util.spec_from_file_location("check", BAR / "check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

LEAN = os.environ.get("BAR_LEAN") == "1"


class Project:
    """A copy of the template in a temporary directory."""

    def __init__(self, keep_build=False):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        ignore = None if keep_build else shutil.ignore_patterns(".lake")
        shutil.copytree(TEMPLATE, self.root, ignore=ignore)

    def edit(self, rel, old, new):
        path = self.root / rel
        text = path.read_text()
        assert old in text, f"{old!r} not in {rel}"
        path.write_text(text.replace(old, new, 1))

    def append(self, rel, text):
        path = self.root / rel
        path.write_text(path.read_text() + text)

    def approve(self, reviewer="reviewer-b", record="https://github.com/Proven-Commons/clamp/pull/7"):
        digest, _ = check.spec_hash(self.root, check.load_bar(self.root))
        self.append("bar.toml", f'\n[[spec.approval]]\nreviewer = "{reviewer}"\n'
                    f'date = "2026-10-24"\nsha256 = "{digest}"\nrecord = "{record}"\n')

    def snapshot(self):
        """The project's files as text, as GitHub would serve them."""
        return {p.relative_to(self.root).as_posix(): p.read_text()
                for p in self.root.rglob("*") if p.is_file() and not {".lake", ".git"} & set(p.parts)}

    def run(self, no_lean=True, offline=True, github=None):
        _, rep = check.check(self.root, no_lean=no_lean, offline=offline, github=github)
        return {r["item"]: (r["status"], r["detail"]) for r in rep.rows}

    def close(self):
        self.tmp.cleanup()


class FakeGitHub:
    """Reviews on one pull request, each made at a commit whose files
    are a snapshot of the project."""

    def __init__(self, login, files, state="APPROVED", forks=None, committers=(), maintainer=True, author="example-author", head=None):
        self.review = {"state": state, "user": {"login": login}, "commit_id": "c0ffee" * 6}
        self.files = files
        self.forks = forks or {}
        self.committers = {c.lower() for c in committers}
        self.maintainer = maintainer
        self.author = author
        self.head = head or self.review["commit_id"]

    def is_maintainer(self, owner, repo, login):
        return self.maintainer

    def pull_request(self, owner, repo, number):
        return {"user": {"login": self.author}, "head": {"sha": self.head}}

    def commit_logins(self, owner, repo, path, ref=None):
        return self.committers

    required = {"bar / bar"}

    def required_checks(self, full_name):
        return "main", self.required

    def parent(self, full_name):
        return self.forks.get(full_name)

    def reviews(self, owner, repo, number):
        return [self.review]

    def read(self, owner, repo, commit, path):
        assert commit == self.review["commit_id"]
        return self.files[path]


def approved_by(project, login="reviewer-b"):
    """A GitHub where `login` approved the project as it is now."""
    return FakeGitHub(login, project.snapshot())


class MaintainerAPITest(unittest.TestCase):
    def test_write_maintain_and_admin_are_current_maintainers(self):
        for role in ("write", "maintain", "admin"):
            with self.subTest(role=role):
                github = check.GitHub()
                github.get = mock.Mock(return_value={"permission": role})
                self.assertTrue(github.is_maintainer("Org", "repo", "Reviewer"))
                self.assertEqual(github.get.call_args.args[0], "/repos/Org/repo/collaborators/Reviewer/permission")

    def test_read_triage_and_no_access_cannot_approve(self):
        for role in ("read", "triage", "none", "unknown", None):
            with self.subTest(role=role):
                github = check.GitHub()
                github.get = mock.Mock(return_value={"permission": role})
                self.assertFalse(github.is_maintainer("Org", "repo", "reviewer"))
                self.assertEqual(github.get.call_count, 1)

    def test_missing_permission_is_not_maintainer_authority(self):
        github = check.GitHub()
        github.get = mock.Mock(return_value={})
        self.assertFalse(github.is_maintainer("Org", "repo", "reviewer"))

    def test_malformed_permission_response_is_not_authority(self):
        github = check.GitHub()
        for response in (None, "write", []):
            with self.subTest(response=response):
                github.get = mock.Mock(return_value=response)
                self.assertFalse(github.is_maintainer("Org", "repo", "reviewer"))

    def test_spec_commit_history_uses_the_approved_head(self):
        github = check.GitHub()
        github.get = mock.Mock(return_value=[])
        github.commit_logins("Org", "repo", "SPEC.md", ref="current-head")
        self.assertIn("&sha=current-head", github.get.call_args.args[0])

    def test_authority_api_errors_do_not_establish_permission(self):
        github = check.GitHub()
        github.get = mock.Mock(side_effect=OSError("authority API unavailable"))
        with self.assertRaises(OSError):
            github.is_maintainer("Org", "repo", "reviewer")

    def test_github_commit_logins_include_authors_and_committers(self):
        github = check.GitHub()
        github.get = mock.Mock(return_value=[{"author": {"login": "Writer"},
                                             "committer": {"login": "Committer"}}])
        self.assertEqual(github.commit_logins("Org", "repo", "SPEC.md"), {"writer", "committer"})


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        # CI sets GITHUB_REPOSITORY to this repo; the tests set it themselves.
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GITHUB_REPOSITORY", None)

    def tearDown(self):
        self.p.close()

    def status(self, item, **kw):
        return self.p.run(**kw)[item][0]

    # The template as shipped.

    def test_template_has_no_failures(self):
        got = self.p.run()
        self.assertEqual(got[1][0], "OPEN")
        self.assertEqual(got[3][0], "SKIP")
        for item in (2, 4, 5, 6):
            self.assertEqual(got[item][0], "PASS", got[item][1])
        self.assertEqual(got[7][0], "SKIP")  # offline: the branch rule is not read
        self.assertIn("not in place", got[2][1])

    # Item 1: the approval.

    def test_approval_confirmed_on_github_passes(self):
        self.p.approve()
        got = self.p.run(offline=False, github=approved_by(self.p, "Reviewer-B"))
        self.assertEqual(got[1][0], "PASS", got[1][1])
        self.assertIn("rests on the spec approval", got[2][1])

    def test_approval_offline_is_skipped_not_passed(self):
        self.p.approve()
        self.assertEqual(self.status(1), "SKIP")

    def test_changing_a_statement_voids_the_approval(self):
        self.p.approve()
        github = approved_by(self.p)
        self.p.edit("Spec.lean", "lo ≤ clamp lo hi x ∧", "lo ≤ clamp lo hi x ∨")
        got = self.p.run(offline=False, github=github)
        self.assertEqual(got[1][0], "OPEN")
        self.assertIn("changed after the last approval", got[1][1])

    def test_changing_a_claim_on_the_page_voids_the_approval(self):
        self.p.approve()
        self.p.edit("README.md", "is never below `lo`", "is always safe and never below `lo`")
        self.assertEqual(self.status(1), "OPEN")

    def test_changing_the_limits_on_the_page_voids_the_approval(self):
        self.p.approve()
        self.p.edit("README.md", "- How fast it runs.\n", "")
        self.assertEqual(self.status(1), "OPEN")

    def test_a_claim_anywhere_on_the_page_voids_the_approval(self):
        # Found in review: claims added outside the three sections used
        # to keep the approval.
        for old, new in [("Copy it to start", "It is formally proven to have no bugs. Copy it to start"),
                         ("## Layout", "## Security guarantees\n\nNo side channels.\n\n## Layout")]:
            with self.subTest(new):
                p = Project()
                try:
                    p.approve()
                    p.edit("README.md", old, new)
                    self.assertEqual(p.run()[1][0], "OPEN")
                finally:
                    p.close()

    def test_changing_files_outside_the_spec_and_page_keeps_the_approval(self):
        self.p.approve()
        self.p.edit("Clamp.lean", "Kept deliberately small.", "Kept small on purpose.")
        self.assertEqual(self.status(1), "SKIP")

    def test_line_endings_do_not_change_the_hash(self):
        before, _ = check.spec_hash(self.p.root, check.load_bar(self.p.root))
        path = self.p.root / "Spec.lean"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        after, _ = check.spec_hash(self.p.root, check.load_bar(self.p.root))
        self.assertEqual(before, after)

    def test_reviewer_who_committed_to_the_spec_fails(self):
        import subprocess
        git = ["git", "-C", str(self.p.root)]
        subprocess.run(git + ["init", "-q"], check=True)
        for who, email in [("example-author", "a@example.org"),
                           ("Someone", "12345+reviewer-b@users.noreply.github.com")]:
            self.p.append("SPEC.md", f"\nEdited by {who}.\n")
            subprocess.run(git + ["add", "-A"], check=True)
            subprocess.run(git + ["-c", f"user.name={who}", "-c", f"user.email={email}",
                                  "commit", "-q", "-m", "edit"], check=True)
        self.p.approve()
        status, detail = self.p.run(offline=False, github=approved_by(self.p))[1]
        self.assertEqual(status, "FAIL")
        self.assertIn("committed to the spec files", detail)

    def test_exact_duplicate_section_is_covered(self):
        self.p.approve()
        self.p.append("README.md", "\n## What is proved\n\nIt is also fast.\n")
        self.assertEqual(self.status(1), "OPEN")
        secs = check.sections((self.p.root / "README.md").read_text())
        self.assertIn("It is also fast.", check.find_section(secs, "What is proved"))

    def test_reviewer_without_current_repo_authority_is_open_then_fails(self):
        self.p.approve(reviewer="sock-puppet")
        got = self.p.run(offline=False, github=FakeGitHub("sock-puppet", self.p.snapshot(), maintainer=False))
        self.assertEqual(got[1][0], "OPEN")
        self.assertIn("not a current maintainer", got[1][1])
        self.p.edit("bar.toml", 'status = "in-progress"', 'status = "verified"')
        self.assertEqual(self.status(1, offline=False, github=FakeGitHub("sock-puppet", self.p.snapshot(), maintainer=False)), "FAIL")

    def test_static_reviewer_list_environment_has_no_authority(self):
        self.p.approve()
        with mock.patch.dict(os.environ, {"BAR_REVIEWERS": "/no-such-static-roster"}):
            self.assertEqual(self.status(1, offline=False, github=approved_by(self.p)), "PASS")

    def test_any_independent_current_maintainer_can_approve(self):
        self.p.approve(reviewer="new-maintainer")
        github = FakeGitHub("NEW-MAINTAINER", self.p.snapshot())
        self.assertEqual(self.status(1, offline=False, github=github), "PASS")

    def test_pull_request_author_cannot_approve(self):
        self.p.approve()
        github = FakeGitHub("reviewer-b", self.p.snapshot(), author="Reviewer-B")
        self.assertEqual(self.status(1, offline=False, github=github), "FAIL")

    def test_additional_spec_author_cannot_approve(self):
        self.p.edit("bar.toml", 'spec_authors = ["example-author"]',
                    'spec_authors = ["example-author", "Reviewer-B"]')
        self.p.approve()
        self.assertEqual(self.status(1, offline=False, github=approved_by(self.p)), "FAIL")

    def test_approval_on_previous_head_does_not_count_even_with_same_hash(self):
        self.p.approve()
        github = FakeGitHub("reviewer-b", self.p.snapshot(), head="new-head")
        status, detail = self.p.run(offline=False, github=github)[1]
        self.assertEqual(status, "OPEN")
        self.assertIn("current head", detail)

    def test_later_request_for_changes_overrides_an_approval(self):
        self.p.approve()
        github = approved_by(self.p)
        approved = dict(github.review, id=1)
        changed = dict(github.review, id=2, state="CHANGES_REQUESTED")
        github.reviews = lambda *args: [changed, approved]
        self.assertEqual(self.status(1, offline=False, github=github), "OPEN")

    def test_later_comment_does_not_replace_an_approval_verdict(self):
        self.p.approve()
        github = approved_by(self.p)
        approved = dict(github.review, id=1)
        comment = dict(github.review, id=2, state="COMMENTED")
        github.reviews = lambda *args: [approved, comment]
        self.assertEqual(self.status(1, offline=False, github=github), "PASS")

    def test_local_spec_committer_cannot_approve(self):
        import subprocess
        git = ["git", "-C", str(self.p.root)]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "SPEC.md"], check=True)
        subprocess.run(git + ["-c", "user.name=reviewer-b", "-c", "user.email=reviewer-b@example.org",
                              "commit", "-q", "--author=Someone <someone@example.org>", "-m", "spec"], check=True)
        self.p.approve()
        self.assertEqual(self.status(1, offline=False, github=approved_by(self.p)), "FAIL")

    def test_reviewer_who_authored_a_spec_commit_on_github_fails(self):
        self.p.approve()
        github = FakeGitHub("reviewer-b", self.p.snapshot(), committers=["Reviewer-B"])
        status, detail = self.p.run(offline=False, github=github)[1]
        self.assertEqual(status, "FAIL")
        self.assertIn("author of a commit", detail)

    def test_approving_a_pull_request_that_does_not_record_the_approval_does_not_count(self):
        # The reviewer approved some other pull request while the text was
        # the same; the approval itself was added later.
        github = approved_by(self.p)
        self.p.approve()
        got = self.p.run(offline=False, github=github)
        self.assertEqual(got[1][0], "OPEN")

    def test_each_reviewed_file_voids_the_approval(self):
        for rel, old, new in [("comparator.json", '"Spec.clamp_of_mem"', '"Spec.clamp_of_mem" '),
                              ("Main.lean", "It calls the proved function", "It calls the function"),
                              ("tests/run_tests.py", "default=20261024", "default=1")]:
            with self.subTest(rel):
                p = Project()
                try:
                    p.approve()
                    p.edit(rel, old, new)
                    self.assertEqual(p.run()[1][0], "OPEN")
                finally:
                    p.close()

    def test_reviewer_who_is_an_author_fails(self):
        self.p.approve(reviewer="example-author")
        self.assertEqual(self.status(1), "FAIL")

    def test_no_approving_review_yet_is_open_then_fails_once_verified(self):
        self.p.approve()
        self.assertEqual(self.status(1, offline=False, github=approved_by(self.p, "someone-else")), "OPEN")
        self.p.edit("bar.toml", 'status = "in-progress"', 'status = "verified"')
        self.assertEqual(self.status(1, offline=False, github=approved_by(self.p, "someone-else")), "FAIL")

    def test_github_error_is_skipped_not_passed(self):
        self.p.approve()

        class Broken:
            def is_maintainer(self, owner, repo, login):
                raise OSError("network down")

            def commit_logins(self, owner, repo, path, ref=None):
                raise OSError("network down")

            def reviews(self, owner, repo, number):
                raise OSError("network down")
        got = self.p.run(offline=False, github=Broken())
        self.assertEqual(got[1][0], "SKIP")
        self.assertIn("network down", got[1][1])

    def test_record_that_is_not_a_pull_request_fails(self):
        self.p.approve(record="approved in a call")
        self.assertEqual(self.status(1, offline=False, github=approved_by(self.p)), "FAIL")

    def test_pull_request_in_another_repo_fails(self):
        self.p.approve()
        os.environ["GITHUB_REPOSITORY"] = "Proven-Commons/other"
        self.assertEqual(self.status(1, offline=False, github=approved_by(self.p)), "FAIL")
        os.environ["GITHUB_REPOSITORY"] = "proven-commons/CLAMP"
        self.assertEqual(self.status(1, offline=False, github=approved_by(self.p)), "PASS")
        # CI in a contributor's fork.
        os.environ["GITHUB_REPOSITORY"] = "someone/clamp"
        fork = FakeGitHub("reviewer-b", self.p.snapshot(), forks={"someone/clamp": "Proven-Commons/clamp"})
        self.assertEqual(self.status(1, offline=False, github=fork), "PASS")

    def test_review_of_other_text_does_not_count(self):
        # The reviewer approved the pull request at a commit where the
        # spec said something else, and the author recorded the hash of
        # text the reviewer never saw.
        before = approved_by(self.p)
        self.p.edit("Spec.lean", "lo ≤ clamp lo hi x ∧", "lo ≤ clamp lo hi x ∨")
        self.p.approve()
        got = self.p.run(offline=False, github=before)
        self.assertEqual(got[1][0], "OPEN")
        self.assertIn("not the text this hash covers", got[1][1])

    def test_dismissed_review_does_not_count(self):
        self.p.approve()
        github = FakeGitHub("reviewer-b", self.p.snapshot(), state="DISMISSED")
        self.assertEqual(self.status(1, offline=False, github=github), "OPEN")

    def test_second_proved_section_is_covered(self):
        self.p.approve()
        self.p.append("README.md", "\n## What is proved, continued\n\nIt is also fast.\n")
        self.assertEqual(self.status(1), "OPEN")

    def test_verified_project_without_approval_fails(self):
        self.p.edit("bar.toml", 'status = "in-progress"', 'status = "verified"')
        self.assertEqual(self.status(1), "FAIL")

    # Item 2: claims name theorems.

    def test_theorem_missing_from_claims_is_open(self):
        self.p.edit("README.md", "| `Spec.clamp_of_mem` |", "| (see Spec.lean) |")
        self.assertEqual(self.status(2), "OPEN")

    def test_theorem_name_must_match_whole(self):
        self.p.edit("README.md", "`Spec.clamp_of_mem`", "`Spec.clamp_of_mem_aux`")
        self.assertEqual(self.status(2), "OPEN")

    # Item 3: proof configuration.

    def test_extra_permitted_axiom_fails(self):
        self.p.edit("comparator.json", '"Classical.choice"]', '"Classical.choice", "Clamp.cheat"]')
        self.assertEqual(self.status(3), "FAIL")

    def test_challenge_file_must_be_approved(self):
        self.p.edit("bar.toml", 'files = ["SPEC.md", "Spec.lean"]', 'files = ["SPEC.md"]')
        got = self.p.run()
        self.assertEqual(got[3][0], "FAIL")
        self.assertIn("not one of the approved spec files", got[3][1])

    def test_floating_toolchain_fails(self):
        (self.p.root / "lean-toolchain").write_text("leanprover/lean4:stable\n")
        self.assertEqual(self.status(3), "FAIL")

    def test_missing_manifest_fails(self):
        (self.p.root / "lake-manifest.json").unlink()
        self.assertEqual(self.status(3), "FAIL")

    # Item 4: the source rule.

    def test_each_forbidden_feature_fails(self):
        plants = {
            "implemented_by": "def fast (n : Nat) : Nat := n\n@[implemented_by fast] def slow (n : Nat) : Nat := n\n",
            "extern": '@[extern "lean_clamp"] def ext (n : Nat) : Nat := n\n',
            "unsafe": "unsafe def u (n : Nat) : Nat := n\n",
            "native evaluation": "theorem t : 2 + 2 = 4 := by native_decide\n",
            "skipKernelTC": "set_option debug.skipKernelTC true\n",
            "axiom": "axiom cheat : False\n",
        }
        for name, code in plants.items():
            with self.subTest(name):
                p = Project()
                try:
                    p.edit("Clamp.lean", "end Clamp", code + "\nend Clamp")
                    status, detail = p.run()[4]
                    self.assertEqual(status, "FAIL")
                    self.assertIn(f"Clamp.lean:", detail)
                    self.assertIn(name, detail)
                finally:
                    p.close()

    def test_set_implemented_by_api_is_caught(self):
        self.p.edit("Clamp.lean", "end Clamp", "-- no import here, but the name alone is enough\n"
                    "def f := Lean.setImplementedBy\n\nend Clamp")
        self.assertIn("implemented_by", self.p.run()[4][1])

    def test_metaprogram_setting_implemented_by_fails(self):
        # The bypass found in review: no `implemented_by` token, yet the
        # compiled clamp returns x unchanged.
        self.p.edit("Clamp.lean", "namespace Clamp", "import Lean\n\nnamespace Clamp")
        self.p.append("Clamp.lean", "\nopen Lean in\nrun_cmd Elab.Command.liftCoreM do\n"
                      "  match Compiler.implementedByAttr.setParam (← getEnv) ``Clamp.clamp ``Clamp.clamp with\n"
                      "  | .ok env => setEnv env\n  | .error e => throwError e\n")
        status, detail = self.p.run()[4]
        self.assertEqual(status, "FAIL")
        for name in ("import Lean", "metaprogram", "implemented_by"):
            self.assertIn(name, detail)

    def test_imports_of_lean_and_lake_fail(self):
        for line in ("import Lean", "import Lean.Elab.Command", "public import Lean.Meta",
                     "import Std Lake", "meta import Lean"):
            with self.subTest(line):
                p = Project()
                try:
                    p.edit("Clamp.lean", "namespace Clamp", f"{line}\n\nnamespace Clamp")
                    status, detail = p.run()[4]
                    self.assertEqual(status, "FAIL")
                    self.assertIn("import Lean", detail)
                finally:
                    p.close()

    def test_imports_that_only_start_with_lean_pass(self):
        (self.p.root / "LeanTar.lean").write_text("def x := 1\n")
        self.p.edit("Clamp.lean", "namespace Clamp", "import LeanTar\nimport Std.Data\n\nnamespace Clamp")
        self.assertEqual(self.status(4), "PASS")

    def test_notation_and_macros_fail(self):
        plants = ['infixl:65 " +++ " => Nat.add', 'notation "‖" x "‖" => x',
                  'local notation:50 a " ≤ " b => True', 'macro "go" : tactic => `(tactic| rfl)',
                  'syntax "foo" : term', 'macro_rules | `(foo) => `(1)', 'prefix:max "√" => Nat.sqrt']
        for code in plants:
            with self.subTest(code):
                p = Project()
                try:
                    p.edit("Clamp.lean", "end Clamp", code + "\n\nend Clamp")
                    self.assertEqual(p.run()[4][0], "FAIL")
                finally:
                    p.close()

    def test_names_like_prefix_in_code_pass(self):
        self.p.edit("Clamp.lean", "end Clamp", "def join (prefix suffix : String) : String :=\n"
                    "  prefix ++ suffix\n\nend Clamp")
        self.assertEqual(self.status(4), "PASS")

    def test_instances_are_reported_for_the_reviewer(self):
        self.p.edit("Clamp.lean", "end Clamp", "instance (priority := high) : LE Nat := ⟨fun _ _ => True⟩\n\nend Clamp")
        status, detail = self.p.run()[4]
        self.assertEqual(status, "PASS")
        self.assertIn("instance declarations for the reviewer to read", detail)
        self.assertIn("Clamp.lean:", detail)

    def test_hidden_folders_are_scanned(self):
        (self.p.root / ".hidden").mkdir()
        (self.p.root / ".hidden" / "Evil.lean").write_text("axiom cheat : False\n")
        status, detail = self.p.run()[4]
        self.assertEqual(status, "FAIL")
        self.assertIn(".hidden/Evil.lean", detail)

    def test_lakefile_rules(self):
        cases = {
            "moreLinkArgs": ("[[lean_exe]]\nname = \"clamp\"\nroot = \"Main\"",
                             "[[lean_exe]]\nname = \"clamp\"\nroot = \"Main\"\nmoreLinkArgs = [\"evil.o\"]"),
            "debug.skipKernelTC": ('defaultTargets', 'leanOptions = { "debug.skipKernelTC" = true }\ndefaultTargets'),
            "srcDir": ('[[lean_lib]]\nname = "Clamp"', '[[lean_lib]]\nname = "Clamp"\nsrcDir = "../elsewhere"'),
            "plugins": ('defaultTargets', 'plugins = ["x"]\ndefaultTargets'),
        }
        for name, (old, new) in cases.items():
            with self.subTest(name):
                p = Project()
                try:
                    p.edit("lakefile.toml", old, new)
                    status, detail = p.run()[4]
                    self.assertEqual(status, "FAIL")
                    self.assertIn("lakefile", detail)
                finally:
                    p.close()

    def test_harmless_lean_options_pass(self):
        self.p.edit("lakefile.toml", "defaultTargets", 'leanOptions = { autoImplicit = false }\ndefaultTargets')
        self.assertEqual(self.status(4), "PASS")

    def test_lakefile_lean_fails(self):
        (self.p.root / "lakefile.lean").write_text("import Lake\nopen Lake DSL\npackage clamp\n")
        status, detail = self.p.run()[4]
        self.assertEqual(status, "FAIL")
        self.assertIn("lakefile.lean", detail)

    def test_decide_native_fails(self):
        self.p.edit("Clamp.lean", "end Clamp", "theorem t : 2 + 2 = 4 := by decide +native\n\nend Clamp")
        self.assertEqual(self.status(4), "FAIL")

    def test_unfinished_proofs_are_open_in_progress_and_fail_once_verified(self):
        self.assertEqual(self.status(4), "PASS")  # Spec.lean is full of sorry
        self.p.edit("Proofs.lean", "  unfold clamp\n  omega\n\ntheorem Spec.clamp_of_mem",
                    "  sorry\n\ntheorem Spec.clamp_of_mem")
        self.p.edit("Clamp.lean", "end Clamp", "theorem t2 : 1 = 1 := by admit\n\nend Clamp")
        status, detail = self.p.run()[4]
        self.assertEqual(status, "OPEN")
        self.assertIn("Proofs.lean:", detail)
        self.assertIn("admit", detail)
        self.p.edit("bar.toml", 'status = "in-progress"', 'status = "verified"')
        self.assertEqual(self.status(4), "FAIL")

    def test_sorry_next_to_another_forbidden_feature_fails_in_progress(self):
        self.p.edit("Clamp.lean", "end Clamp", "theorem t2 : 1 = 1 := sorry\naxiom cheat : False\n\nend Clamp")
        self.assertEqual(self.status(4), "FAIL")

    def test_words_in_comments_and_strings_are_ignored(self):
        self.p.edit("Clamp.lean", "end Clamp",
                    '-- no sorry, no unsafe here\n/- nested /- extern -/ admit -/\n'
                    'def msg : String := "implemented_by \\" sorry"\n'
                    "def q : Char := '\"'\ndef p' (n : Nat) : Nat := n\n\nend Clamp")
        self.assertEqual(self.status(4), "PASS")

    def test_trusted_exception_is_allowed_and_must_be_on_the_page(self):
        self.p.edit("Clamp.lean", "end Clamp", '@[extern "lean_clamp"] def ext (n : Nat) : Nat := n\n\nend Clamp')
        self.p.append("bar.toml", '\n[[trusted]]\nfile = "Clamp.lean"\nfeature = "extern"\nreason = "test"\n')
        got = self.p.run()
        self.assertEqual(got[4][0], "PASS")
        self.assertIn("1 listed as trusted", got[4][1])
        self.assertEqual(got[6][0], "OPEN")
        self.p.edit("README.md", "- The hardware it runs on.", "- The hardware it runs on.\n- `Clamp.lean`, which calls C.")
        self.assertEqual(self.status(4), "PASS")
        self.assertEqual(self.status(6), "PASS")

    def test_build_folders_are_not_scanned(self):
        hidden = self.p.root / ".lake" / "packages" / "dep"
        hidden.mkdir(parents=True)
        (hidden / "Dep.lean").write_text("axiom cheat : False\n")
        self.assertEqual(self.status(4), "PASS")

    # Item 5: the test record.

    def test_missing_seed_is_open(self):
        self.p.edit("tests/TEST-RESULTS.md", "- Seed:", "- Random:")
        self.assertEqual(self.status(5), "OPEN")

    def test_recorded_failures_fail(self):
        self.p.edit("tests/TEST-RESULTS.md", "- Failures: 0", "- Failures: 3")
        self.assertEqual(self.status(5), "FAIL")

    def test_zero_inputs_is_open(self):
        text = (self.p.root / "tests/TEST-RESULTS.md").read_text()
        (self.p.root / "tests/TEST-RESULTS.md").write_text(re.sub(r"- Inputs: \d+", "- Inputs: 0", text))
        self.assertEqual(self.status(5), "OPEN")

    def test_run_tests_reruns_and_reads_the_fresh_record(self):
        self.p.edit("bar.toml", 'command = "python3 tests/run_tests.py"',
                    'command = "printf -- \'- Oracle: o\\\\n- Seed: 1\\\\n- Inputs: 5\\\\n- Failures: 2\\\\n\' > tests/TEST-RESULTS.md"')
        _, rep = check.check(self.p.root, no_lean=True, offline=True, run_tests=True)
        row = next(r for r in rep.rows if r["item"] == 5)
        self.assertEqual(row["status"], "FAIL")
        self.assertIn("2 failures", row["detail"])

    def test_failing_test_command_fails_even_in_progress(self):
        # Found in review: a red test run used to leave CI green.
        self.p.edit("bar.toml", 'command = "python3 tests/run_tests.py"', 'command = "exit 3"')
        _, rep = check.check(self.p.root, no_lean=True, offline=True, run_tests=True)
        row = next(r for r in rep.rows if r["item"] == 5)
        self.assertEqual(row["status"], "FAIL")
        self.assertIn("exited 3", row["detail"])

    def git_commit_all(self):
        import subprocess
        git = ["git", "-C", str(self.p.root), "-c", "user.name=a", "-c", "user.email=a@example.org"]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "x"], check=True)

    def test_record_must_be_committed(self):
        (self.p.root / "tests" / "TEST-RESULTS.md").unlink()
        self.git_commit_all()
        self.p.edit("bar.toml", 'command = "python3 tests/run_tests.py"',
                    'command = "printf -- \'- Oracle: o\\\\n- Seed: 1\\\\n- Inputs: 5\\\\n- Failures: 0\\\\n\' > tests/TEST-RESULTS.md"')
        _, rep = check.check(self.p.root, no_lean=True, offline=True, run_tests=True)
        row = next(r for r in rep.rows if r["item"] == 5)
        self.assertEqual(row["status"], "OPEN")
        self.assertIn("not committed", row["detail"])

    def test_stale_committed_record_is_open(self):
        self.git_commit_all()
        self.p.edit("bar.toml", 'command = "python3 tests/run_tests.py"',
                    'command = "printf -- \'- Oracle: o\\\\n- Seed: 9\\\\n- Inputs: 5\\\\n- Failures: 0\\\\n\' > tests/TEST-RESULTS.md"')
        _, rep = check.check(self.p.root, no_lean=True, offline=True, run_tests=True)
        row = next(r for r in rep.rows if r["item"] == 5)
        self.assertEqual(row["status"], "OPEN")
        self.assertIn("differs from a fresh run", row["detail"])

    # Item 6: the page.

    def test_dependencies_must_be_named_as_trusted(self):
        (self.p.root / "lake-manifest.json").write_text(
            '{"version": "1.3.0", "packagesDir": ".lake/packages", "name": "clamp", "lakeDir": ".lake",'
            ' "packages": [{"name": "mathlib", "type": "git"}]}')
        got = self.p.run()
        self.assertEqual(got[6][0], "OPEN")
        self.assertIn("dependency mathlib", got[6][1])
        self.p.edit("README.md", "- The hardware it runs on.", "- The hardware it runs on.\n- Mathlib, which is not scanned.")
        self.assertEqual(self.status(6), "PASS")

    def test_status_line_must_match_bar_toml(self):
        self.assertEqual(self.status(6), "PASS")
        p = self.p
        p.edit("README.md", "Status: in progress.", "Status: verified.")
        got = p.run()
        self.assertEqual(got[6][0], "OPEN")
        self.assertIn("does not say in progress", got[6][1])
        p.edit("README.md", "Status: verified.", "")
        self.assertIn("no `Status:` line", p.run()[6][1])

    def test_trust_section_must_name_hardware(self):
        self.p.edit("README.md", "- The hardware it runs on.\n", "")
        got = self.p.run()
        self.assertEqual(got[6][0], "OPEN")
        self.assertIn("hardware", got[6][1])

    def test_recheck_must_give_the_command(self):
        self.p.edit("README.md", "lake comparator --paranoid\npython3", "lake build\npython3")
        self.p.edit("README.md", "`lake comparator --paranoid` builds", "It builds")
        self.assertEqual(self.status(6), "OPEN")

    def test_heading_in_code_fence_does_not_count(self):
        self.p.edit("README.md", "## What you must trust", "```\n## What you must trust\n```\n### Trust")
        self.assertEqual(self.status(6), "OPEN")

    # Item 7: CI.

    def test_branch_rule_is_read_from_github(self):
        os.environ["GITHUB_REPOSITORY"] = "Proven-Commons/clamp"
        github = approved_by(self.p)
        self.assertEqual(self.status(7, offline=False, github=github), "PASS")
        github.required = {"something else"}
        got = self.p.run(offline=False, github=github)
        self.assertEqual(got[7][0], "OPEN")
        self.assertIn("does not require the `bar / bar` check", got[7][1])

    def test_no_workflow_is_open(self):
        shutil.rmtree(self.p.root / ".github")
        self.assertEqual(self.status(7), "OPEN")

    def test_a_workflow_that_only_mentions_the_bar_is_open(self):
        (self.p.root / ".github" / "workflows" / "bar.yml").write_text(
            "# TODO: use Proven-Commons/mission/.github/workflows/verified-bar.yml\n"
            "jobs:\n  bar:\n    runs-on: ubuntu-24.04\n    steps:\n      - run: lake comparator --paranoid\n")
        self.assertEqual(self.status(7), "OPEN")

    def test_workflow_at_the_top_of_the_repo_counts_for_a_project_in_a_folder(self):
        import subprocess
        repo = self.p.root.parent / "repo"
        shutil.move(str(self.p.root), str(repo / "lean"))
        shutil.move(str(repo / "lean" / ".github"), str(repo / ".github"))
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        _, rep = check.check(repo / "lean", no_lean=True, offline=True)
        row = next(r for r in rep.rows if r["item"] == 7)
        self.assertEqual(row["status"], "SKIP")
        self.assertIn(".github/workflows/bar.yml calls the verified-bar workflow", row["detail"])

    # The command line.

    def run_main(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return check.main([str(self.p.root), *args])

    def test_verified_project_must_pass_every_item_to_exit_0(self):
        # Found in review: --offline left a verified project green.
        self.p.approve()
        self.p.edit("bar.toml", 'status = "in-progress"', 'status = "verified"')
        self.assertEqual(self.run_main("--no-lean", "--offline"), 1)

    def test_exit_codes(self):
        self.assertEqual(self.run_main("--no-lean", "--offline"), 0)
        self.p.edit("comparator.json", '"Classical.choice"]', '"Classical.choice", "x"]')
        self.assertEqual(self.run_main("--no-lean", "--offline"), 1)
        (self.p.root / "bar.toml").unlink()
        self.assertEqual(self.run_main("--no-lean", "--offline"), 2)

    def test_malformed_bar_toml_is_a_clear_error(self):
        self.p.append("bar.toml", '\n[[trusted]]\nfile = "x"\n')
        (self.p.root / "bar.toml").write_text('[project]\nstatus = "in-progress"\nspec_authors = "a"\n')
        self.assertEqual(self.run_main("--no-lean", "--offline"), 2)


class StripTest(unittest.TestCase):
    def test_keeps_line_numbers(self):
        src = 'a\n/- x\ny -/\n"s\nt"\nsorry'
        out = check.strip_lean(src)
        self.assertEqual(out.count("\n"), src.count("\n"))
        self.assertEqual(out.split("\n")[-1], "sorry")

    def test_raw_string(self):
        self.assertNotIn("sorry", check.strip_lean('def s := r#"a " sorry"#'))

    def test_string_gap_keeps_line_numbers(self):
        src = 'def s := "a\\\n  b"\nsorry'
        out = check.strip_lean(src)
        self.assertEqual(out.count("\n"), src.count("\n"))

    def test_primes_are_names_not_chars(self):
        self.assertIn("sorry", check.strip_lean("theorem h' : x := sorry"))


@unittest.skipUnless(LEAN, "set BAR_LEAN=1 to run the Lean end-to-end tests")
class LeanTest(unittest.TestCase):
    def setUp(self):
        self.p = Project(keep_build=True)

    def tearDown(self):
        self.p.close()

    def test_template_proofs_pass(self):
        self.assertEqual(self.p.run(no_lean=False)[3][0], "PASS")

    def test_weaker_statement_fails(self):
        self.p.edit("Proofs.lean", "    lo ≤ clamp lo hi x ∧ clamp lo hi x ≤ hi := by\n  unfold clamp\n  omega",
                    "    lo ≤ clamp lo hi x ∨ clamp lo hi x ≤ hi := by\n  unfold clamp\n  omega")
        status, detail = self.p.run(no_lean=False)[3]
        self.assertEqual(status, "FAIL")
        self.assertIn("do not match", detail)

    def test_sorry_proof_fails_once_verified(self):
        self.p.edit("Proofs.lean", "  unfold clamp\n  omega\n\ntheorem Spec.clamp_of_mem",
                    "  sorry\n\ntheorem Spec.clamp_of_mem")
        self.p.edit("bar.toml", 'status = "in-progress"', 'status = "verified"')
        got = self.p.run(no_lean=False)
        self.assertEqual(got[3][0], "FAIL")
        self.assertEqual(got[4][0], "FAIL")

    def walk(self, extra_theorems=()):
        import subprocess
        import json
        path = self.p.root / "comparator.json"
        cfg = json.loads(path.read_text())
        cfg["theorem_names"] = ["Spec.clamp_in_range", "Spec.clamp_of_mem", *extra_theorems]
        path.write_text(json.dumps(cfg, indent=2))
        subprocess.run(["lake", "build", "Spec"], cwd=self.p.root, capture_output=True, check=True)
        bar = check.load_bar(self.p.root)
        cmp_cfg, _ = check.load_comparator(self.p.root)
        return check.statement_dependencies(self.p.root, bar, cmp_cfg)[0]

    def test_walk_passes_the_template(self):
        self.assertEqual(self.walk(), [])

    def test_instance_in_the_code_that_changes_a_statement_fails(self):
        # The comparator sees the same instance on both sides, so only the
        # walk can tell that `≤` in Spec.lean no longer means Nat.le.
        self.p.edit("Clamp.lean", "end Clamp",
                    "instance (priority := high) sneaky : LE Nat := ⟨fun _ _ => True⟩\n\nend Clamp")
        problems = self.walk()
        self.assertTrue(any("Clamp.sneaky" in p for p in problems), problems)

    def test_predicate_in_the_code_fails_and_in_the_spec_passes(self):
        self.p.edit("Clamp.lean", "end Clamp", "def Good (n : Nat) : Prop := n = n\n\nend Clamp")
        self.p.append("Spec.lean", "\ntheorem Spec.good (lo hi x : Nat) : Clamp.Good (clamp lo hi x) := sorry\n")
        problems = self.walk(["Spec.good"])
        self.assertTrue(any("Clamp.Good" in p for p in problems), problems)

        self.p.edit("Clamp.lean", "def Good (n : Nat) : Prop := n = n\n", "")
        self.p.edit("Spec.lean", "theorem Spec.good (lo hi x : Nat) : Clamp.Good",
                    "def Spec.Good (n : Nat) : Prop := n = n\n\ntheorem Spec.good (lo hi x : Nat) : Spec.Good")
        self.assertEqual(self.walk(["Spec.good"]), [])

    def test_theorem_left_out_of_comparator_json_fails(self):
        # Found in review: a claimed theorem could be dropped from
        # comparator.json, and so from the proof check, after approval.
        self.p.append("Spec.lean", "\ntheorem Spec.clamp_le_hi (lo hi x : Nat) (h : lo ≤ hi) : "
                      "clamp lo hi x ≤ hi := sorry\n")
        problems = self.walk()
        self.assertTrue(any("does not name these theorems" in p and "Spec.clamp_le_hi" in p
                            for p in problems), problems)

    def test_unfinished_proof_is_open_in_progress(self):
        self.p.edit("Proofs.lean", "  unfold clamp\n  omega\n\ntheorem Spec.clamp_of_mem",
                    "  sorry\n\ntheorem Spec.clamp_of_mem")
        got = self.p.run(no_lean=False)
        self.assertEqual(got[3][0], "OPEN", got[3][1])
        self.assertEqual(got[4][0], "OPEN")

    def test_statement_without_code_fails(self):
        self.p.append("Spec.lean", "\ntheorem Spec.trivial : 1 + 1 = 2 := sorry\n")
        problems = self.walk(["Spec.trivial"])
        self.assertTrue(any("mentions no code under proof" in p for p in problems), problems)

    def test_implemented_by_passes_the_kernels_so_the_source_rule_must_catch_it(self):
        self.p.edit("Clamp.lean", "/-- Clamp `x`", "def clampFast (lo hi x : Nat) : Nat := x\n\n/-- Clamp `x`")
        self.p.edit("Clamp.lean", "def clamp (lo hi x : Nat)", "@[implemented_by clampFast]\ndef clamp (lo hi x : Nat)")
        got = self.p.run(no_lean=False)
        self.assertEqual(got[3][0], "PASS")
        self.assertEqual(got[4][0], "FAIL")


if __name__ == "__main__":
    unittest.main()
