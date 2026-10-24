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
                for p in self.root.rglob("*") if p.is_file() and ".lake" not in p.parts}

    def run(self, no_lean=True, offline=True, github=None):
        _, rep = check.check(self.root, no_lean=no_lean, offline=offline, github=github)
        return {r["item"]: (r["status"], r["detail"]) for r in rep.rows}

    def close(self):
        self.tmp.cleanup()


class FakeGitHub:
    """Reviews on one pull request, each made at a commit whose files
    are a snapshot of the project."""

    def __init__(self, login, files, state="APPROVED"):
        self.review = {"state": state, "user": {"login": login}, "commit_id": "c0ffee" * 6}
        self.files = files

    def reviews(self, owner, repo, number):
        return [self.review]

    def read(self, owner, repo, commit, path):
        assert commit == self.review["commit_id"]
        return self.files[path]


def approved_by(project, login="reviewer-b"):
    """A GitHub where `login` approved the project as it is now."""
    return FakeGitHub(login, project.snapshot())


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
        for item in (2, 4, 5, 6, 7):
            self.assertEqual(got[item][0], "PASS", got[item][1])
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

    def test_changing_other_sections_keeps_the_approval(self):
        self.p.approve()
        self.p.edit("README.md", "## Layout", "## Layout\n\nA new note.")
        self.p.edit("README.md", "on a million inputs", "on one million inputs")
        self.assertEqual(self.status(1), "SKIP")

    def test_line_endings_do_not_change_the_hash(self):
        before, _ = check.spec_hash(self.p.root, check.load_bar(self.p.root))
        path = self.p.root / "Spec.lean"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        after, _ = check.spec_hash(self.p.root, check.load_bar(self.p.root))
        self.assertEqual(before, after)

    def test_reviewer_who_is_an_author_fails(self):
        self.p.approve(reviewer="example-author")
        self.assertEqual(self.status(1), "FAIL")

    def test_no_approving_review_on_github_fails(self):
        self.p.approve()
        self.assertEqual(self.status(1, offline=False, github=approved_by(self.p, "someone-else")), "FAIL")

    def test_github_error_fails(self):
        self.p.approve()

        class Broken:
            def reviews(self, owner, repo, number):
                raise OSError("network down")
        got = self.p.run(offline=False, github=Broken())
        self.assertEqual(got[1][0], "FAIL")
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

    def test_review_of_other_text_fails(self):
        # The reviewer approved the pull request at a commit where the
        # spec said something else, and the author recorded the hash of
        # text the reviewer never saw.
        before = approved_by(self.p)
        self.p.edit("Spec.lean", "lo ≤ clamp lo hi x ∧", "lo ≤ clamp lo hi x ∨")
        self.p.approve()
        got = self.p.run(offline=False, github=before)
        self.assertEqual(got[1][0], "FAIL")
        self.assertIn("not the text this hash covers", got[1][1])

    def test_dismissed_review_fails(self):
        self.p.approve()
        github = FakeGitHub("reviewer-b", self.p.snapshot(), state="DISMISSED")
        self.assertEqual(self.status(1, offline=False, github=github), "FAIL")

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
            "admit": "theorem t2 : 1 = 1 := by admit\n",
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

    def test_decide_native_fails(self):
        self.p.edit("Clamp.lean", "end Clamp", "theorem t : 2 + 2 = 4 := by decide +native\n\nend Clamp")
        self.assertEqual(self.status(4), "FAIL")

    def test_sorry_in_proofs_fails_but_not_in_challenge(self):
        self.assertEqual(self.status(4), "PASS")  # Spec.lean is full of sorry
        self.p.edit("Proofs.lean", "  unfold clamp\n  omega\n\ntheorem Spec.clamp_of_mem",
                    "  sorry\n\ntheorem Spec.clamp_of_mem")
        status, detail = self.p.run()[4]
        self.assertEqual(status, "FAIL")
        self.assertIn("Proofs.lean:", detail)

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

    def test_recorded_failures_are_open(self):
        self.p.edit("tests/TEST-RESULTS.md", "- Failures: 0", "- Failures: 3")
        self.assertEqual(self.status(5), "OPEN")

    def test_zero_inputs_is_open(self):
        text = (self.p.root / "tests/TEST-RESULTS.md").read_text()
        (self.p.root / "tests/TEST-RESULTS.md").write_text(re.sub(r"- Inputs: \d+", "- Inputs: 0", text))
        self.assertEqual(self.status(5), "OPEN")

    def test_run_tests_reruns_and_reads_the_fresh_record(self):
        self.p.edit("bar.toml", 'command = "python3 tests/run_tests.py"',
                    'command = "printf -- \'- Oracle: o\\\\n- Seed: 1\\\\n- Inputs: 5\\\\n- Failures: 2\\\\n\' > tests/TEST-RESULTS.md"')
        _, rep = check.check(self.p.root, no_lean=True, offline=True, run_tests=True)
        row = next(r for r in rep.rows if r["item"] == 5)
        self.assertEqual(row["status"], "OPEN")
        self.assertIn("2 failures", row["detail"])

    def test_failing_test_command_is_open(self):
        self.p.edit("bar.toml", 'command = "python3 tests/run_tests.py"', 'command = "exit 3"')
        _, rep = check.check(self.p.root, no_lean=True, offline=True, run_tests=True)
        row = next(r for r in rep.rows if r["item"] == 5)
        self.assertEqual(row["status"], "OPEN")
        self.assertIn("exited 3", row["detail"])

    # Item 6: the page.

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

    def test_no_workflow_is_open(self):
        shutil.rmtree(self.p.root / ".github")
        self.assertEqual(self.status(7), "OPEN")

    # The command line.

    def run_main(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return check.main([str(self.p.root), *args])

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

    def test_sorry_proof_fails(self):
        self.p.edit("Proofs.lean", "  unfold clamp\n  omega\n\ntheorem Spec.clamp_of_mem",
                    "  sorry\n\ntheorem Spec.clamp_of_mem")
        got = self.p.run(no_lean=False)
        self.assertEqual(got[3][0], "FAIL")
        self.assertEqual(got[4][0], "FAIL")

    def test_implemented_by_passes_the_kernels_so_the_source_rule_must_catch_it(self):
        self.p.edit("Clamp.lean", "/-- Clamp `x`", "def clampFast (lo hi x : Nat) : Nat := x\n\n/-- Clamp `x`")
        self.p.edit("Clamp.lean", "def clamp (lo hi x : Nat)", "@[implemented_by clampFast]\ndef clamp (lo hi x : Nat)")
        got = self.p.run(no_lean=False)
        self.assertEqual(got[3][0], "PASS")
        self.assertEqual(got[4][0], "FAIL")


if __name__ == "__main__":
    unittest.main()
