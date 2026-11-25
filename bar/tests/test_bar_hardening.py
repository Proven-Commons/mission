#!/usr/bin/env python3
"""Regression tests for bar/check.py trust-boundary hardening:
1. Empty/whitespace page sections (trust, re-check, not-proved) fail closed.
2. lakefile.toml srcDir overrides (including .lake/.git/sub/non-string) are rejected.
3. [[trusted]] entries are folded into spec_hash and verified against the reviewed bar.toml.
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
BAR_DIR = TESTS_DIR.parent
for path in (BAR_DIR, TESTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import check  # noqa: E402
from test_check import FakeGitHub, Project, approved_by  # noqa: E402


class EmptySectionHardeningTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.saved_env = os.environ.get("GITHUB_REPOSITORY")
        os.environ.pop("GITHUB_REPOSITORY", None)

    def tearDown(self):
        if self.saved_env is None:
            os.environ.pop("GITHUB_REPOSITORY", None)
        else:
            os.environ["GITHUB_REPOSITORY"] = self.saved_env
        self.p.close()

    def _write_readme(self, trust_body, recheck_body, not_proved_body="- Parsing in Main.lean."):
        (self.p.root / "README.md").write_text(
            "# Clamp\n\n"
            "Status: in progress. The specification has not been approved by a reviewer, so this is not verified.\n\n"
            "## What is proved\n\n"
            "- `Clamp.Spec.clamp_in_range`\n"
            "- `Clamp.Spec.clamp_of_mem`\n\n"
            f"## What is not proved\n\n{not_proved_body}\n\n"
            f"## What you must trust\n\n{trust_body}\n\n"
            f"## Re-check it\n\n{recheck_body}\n",
            encoding="utf-8",
        )

    def test_empty_trust_section_fails_closed(self):
        self._write_readme(
            trust_body="",
            recheck_body="Run `lake comparator --paranoid` and `python3 tests/run_tests.py`.",
        )
        got = self.p.run()
        self.assertEqual(got[6][0], "OPEN")
        self.assertIn("'What you must trust' section is empty", got[6][1])
        for word in check.TRUST_WORDS:
            self.assertIn(word, got[6][1])

        self.p.edit("bar.toml", 'status = "in-progress"', 'status = "verified"')
        self.p.edit(
            "README.md",
            "Status: in progress. The specification has not been approved by a reviewer, so this is not verified.",
            "Status: verified.",
        )
        got_verified = self.p.run()
        self.assertEqual(got_verified[6][0], "FAIL")
        self.assertIn("'What you must trust' section is empty", got_verified[6][1])

    def test_whitespace_trust_section_checks_trusted_files_and_dependencies(self):
        self.p.append(
            "bar.toml",
            '\n[[trusted]]\nfile = "Clamp.lean"\nfeature = "extern"\nreason = "ffi"\n',
        )
        (self.p.root / "lake-manifest.json").write_text(
            '{"version": "1.3.0", "packagesDir": ".lake/packages", "name": "clamp", "lakeDir": ".lake",'
            ' "packages": [{"name": "mathlib", "type": "git"}]}',
            encoding="utf-8",
        )
        self._write_readme(
            trust_body="   \n\t  \n",
            recheck_body="Run `lake comparator --paranoid` and `python3 tests/run_tests.py`.",
        )
        got = self.p.run()
        self.assertEqual(got[6][0], "OPEN")
        self.assertIn("'What you must trust' section is empty", got[6][1])
        self.assertIn("trusted file Clamp.lean", got[6][1])
        self.assertIn("dependency mathlib", got[6][1])

    def test_empty_recheck_section_fails_closed(self):
        self._write_readme(
            trust_body="- Lean kernel, compiler, runtime, and hardware.",
            recheck_body="   \n",
        )
        got = self.p.run()
        self.assertEqual(got[6][0], "OPEN")
        self.assertIn("'Re-check' section is empty", got[6][1])
        self.assertIn(check.RECHECK_COMMAND, got[6][1])
        self.assertIn("python3 tests/run_tests.py", got[6][1])

        self.p.edit("bar.toml", 'status = "in-progress"', 'status = "verified"')
        self.p.edit(
            "README.md",
            "Status: in progress. The specification has not been approved by a reviewer, so this is not verified.",
            "Status: verified.",
        )
        self.assertEqual(self.p.run()[6][0], "FAIL")

    def test_empty_not_proved_section_fails_closed(self):
        self._write_readme(
            trust_body="- Lean kernel, compiler, runtime, and hardware.",
            recheck_body="Run `lake comparator --paranoid` and `python3 tests/run_tests.py`.",
            not_proved_body="   ",
        )
        got = self.p.run()
        self.assertEqual(got[6][0], "OPEN")
        self.assertIn("'What is not proved' section is empty", got[6][1])

    def test_non_empty_valid_sections_pass(self):
        self._write_readme(
            trust_body="- Lean kernel, compiler, runtime, and hardware.",
            recheck_body="Run `lake comparator --paranoid` and `python3 tests/run_tests.py`.",
        )
        self.assertEqual(self.p.run()[6][0], "PASS")


class SrcDirHardeningTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()

    def tearDown(self):
        self.p.close()

    def test_dot_lake_srcdir_cannot_hide_forbidden_lean_code(self):
        hidden = self.p.root / ".lake" / "hidden"
        hidden.mkdir(parents=True)
        (hidden / "Clamp.lean").write_text(
            'axiom cheat : False\n@[extern "evil"] opaque f : Unit -> Unit\n',
            encoding="utf-8",
        )
        self.p.edit(
            "lakefile.toml",
            '[[lean_lib]]\nname = "Clamp"',
            '[[lean_lib]]\nname = "Clamp"\nsrcDir = ".lake/hidden"',
        )
        status, detail = self.p.run()[4]
        self.assertEqual(status, "FAIL")
        self.assertIn("srcDir", detail)
        self.assertIn(".lake/hidden", detail)

    def test_non_root_and_malformed_srcdir_variants_rejected(self):
        bad_values = [
            '".lake"',
            '".lake/hidden"',
            '"a/.lake/b"',
            '".git/hidden"',
            '"sub"',
            '"src/lean"',
            '"../elsewhere"',
            r'"..\\elsewhere"',
            r'".\\"',
            r'"./\\"',
            r'".\\."',
            r'"\\"',
            '"/tmp/evil"',
            r'"C:\\evil"',
            '""',
            '"   "',
            "123",
            '["."]',
        ]
        for raw in bad_values:
            with self.subTest(srcDir=raw):
                p = Project()
                try:
                    p.edit(
                        "lakefile.toml",
                        '[[lean_lib]]\nname = "Clamp"',
                        f'[[lean_lib]]\nname = "Clamp"\nsrcDir = {raw}',
                    )
                    status, detail = p.run()[4]
                    self.assertEqual(status, "FAIL")
                    self.assertIn("srcDir", detail)
                finally:
                    p.close()

    def test_package_srcdir_rejected_even_when_listed_in_trusted(self):
        self.p.append(
            "bar.toml",
            '\n[[trusted]]\nfile = "lakefile.toml"\nfeature = "srcDir"\nreason = "bypass attempt"\n',
        )
        self.p.edit("lakefile.toml", "defaultTargets", 'srcDir = ".lake/hidden"\ndefaultTargets')
        status, detail = self.p.run()[4]
        self.assertEqual(status, "FAIL")
        self.assertIn("srcDir", detail)

    def test_lean_exe_srcdir_rejected(self):
        self.p.edit(
            "lakefile.toml",
            '[[lean_exe]]\nname = "clamp"\nroot = "Main"',
            '[[lean_exe]]\nname = "clamp"\nroot = "Main"\nsrcDir = ".git/hooks"',
        )
        status, detail = self.p.run()[4]
        self.assertEqual(status, "FAIL")
        self.assertIn("srcDir", detail)

    def test_explicit_root_dot_srcdir_allowed(self):
        self.p.edit(
            "lakefile.toml",
            '[[lean_lib]]\nname = "Clamp"',
            '[[lean_lib]]\nname = "Clamp"\nsrcDir = "."',
        )
        self.p.edit(
            "lakefile.toml",
            '[[lean_exe]]\nname = "clamp"\nroot = "Main"',
            '[[lean_exe]]\nname = "clamp"\nroot = "Main"\nsrcDir = "./"',
        )
        self.assertEqual(self.p.run()[4][0], "PASS")

    def test_non_list_lean_lib_table_rejected(self):
        (self.p.root / "lakefile.toml").write_text(
            'name = "clamp"\nversion = "0.1.0"\nlicense = "Apache-2.0"\n'
            'defaultTargets = ["Clamp"]\n\n'
            '[lean_lib]\nname = "Clamp"\nsrcDir = ".lake/hidden"\n',
            encoding="utf-8",
        )
        status, detail = self.p.run()[4]
        self.assertEqual(status, "FAIL")
        self.assertIn("lean_lib", detail)


class TrustedSpecHashHardeningTest(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GITHUB_REPOSITORY", None)
        reviewers = Path(self.p.tmp.name) / "reviewers.toml"
        reviewers.write_text(
            '[[reviewer]]\nlogin = "reviewer-b"\n[[reviewer]]\nlogin = "example-author"\n',
            encoding="utf-8",
        )
        os.environ["BAR_REVIEWERS"] = str(reviewers)

    def tearDown(self):
        self.p.close()

    def test_spec_hash_sensitive_to_trusted_entries_and_order_independent(self):
        bar0 = check.load_bar(self.p.root)
        h0, cov0 = check.spec_hash(self.p.root, bar0)
        self.assertFalse(any("[[trusted]]" in item for item in cov0))

        bar1 = dict(bar0)
        bar1["trusted"] = [{"file": "Clamp.lean", "feature": "extern", "reason": "ffi"}]
        h1, cov1 = check.spec_hash(self.p.root, bar1)
        self.assertNotEqual(h0, h1)
        self.assertTrue(any("[[trusted]]" in item and "Clamp.lean:extern" in item for item in cov1))

        # Editing file, feature, or reason each changes the hash.
        for field, mutated in (
            ("file", "Main.lean"),
            ("feature", "unsafe"),
            ("reason", "different reason"),
        ):
            bar_mut = dict(bar0)
            entry = dict(bar1["trusted"][0])
            entry[field] = mutated
            bar_mut["trusted"] = [entry]
            h_mut, _ = check.spec_hash(self.p.root, bar_mut)
            self.assertNotEqual(h1, h_mut, f"changing {field} must change spec_hash")

        # Duplicate entry produces distinct hash.
        bar_dup = dict(bar0)
        bar_dup["trusted"] = [dict(bar1["trusted"][0]), dict(bar1["trusted"][0])]
        h_dup, _ = check.spec_hash(self.p.root, bar_dup)
        self.assertNotEqual(h1, h_dup)

        # Reordering entries yields the exact same canonical hash.
        e_a = {"file": "Clamp.lean", "feature": "extern", "reason": "a"}
        e_b = {"file": "Main.lean", "feature": "unsafe", "reason": "b"}
        bar_ab = dict(bar0)
        bar_ab["trusted"] = [e_a, e_b]
        bar_ba = dict(bar0)
        bar_ba["trusted"] = [e_b, e_a]
        self.assertEqual(check.spec_hash(self.p.root, bar_ab)[0], check.spec_hash(self.p.root, bar_ba)[0])

    def test_post_approval_trusted_addition_invalidates_review(self):
        os.environ["GITHUB_REPOSITORY"] = "Proven-Commons/clamp"
        self.p.approve()
        github = approved_by(self.p)
        self.assertEqual(self.p.run(offline=False, github=github)[1][0], "PASS")

        # Post-approval attacker adds a [[trusted]] exception for lakefile.toml without re-review.
        self.p.append(
            "bar.toml",
            '\n[[trusted]]\nfile = "lakefile.toml"\nfeature = "moreLinkArgs"\nreason = "unreviewed"\n',
        )
        self.p.append("lakefile.toml", 'moreLinkArgs = ["-lm"]\n')
        got = self.p.run(offline=False, github=github)
        self.assertEqual(got[1][0], "OPEN")
        self.assertIn("the spec changed after the last approval", got[1][1])

        self.p.edit("bar.toml", 'status = "in-progress"', 'status = "verified"')
        self.assertEqual(self.p.run(offline=False, github=github)[1][0], "FAIL")

    def test_prerecorded_future_hash_cannot_smuggle_post_approval_trusted(self):
        os.environ["GITHUB_REPOSITORY"] = "Proven-Commons/clamp"
        # Compute the future spec_hash WITH a [[trusted]] entry not yet in bar.toml at review time.
        bar_with_trusted = check.load_bar(self.p.root)
        bar_with_trusted["trusted"] = [
            {"file": "lakefile.toml", "feature": "moreLinkArgs", "reason": "smuggled"}
        ]
        future_hash, _ = check.spec_hash(self.p.root, bar_with_trusted)

        # Record future_hash in bar.toml WITHOUT the [[trusted]] entry at commit C, then simulate GitHub review.
        self.p.append(
            "bar.toml",
            f'\n[[spec.approval]]\nreviewer = "reviewer-b"\ndate = "2026-11-02"\n'
            f'sha256 = "{future_hash}"\nrecord = "https://github.com/Proven-Commons/clamp/pull/7"\n',
        )
        github = FakeGitHub("reviewer-b", self.p.snapshot())

        # After review, add [[trusted]] to working-tree bar.toml so current spec_hash == future_hash.
        self.p.append(
            "bar.toml",
            '\n[[trusted]]\nfile = "lakefile.toml"\nfeature = "moreLinkArgs"\nreason = "smuggled"\n',
        )
        got = self.p.run(offline=False, github=github)
        self.assertEqual(got[1][0], "OPEN")
        self.assertIn("is not the text this hash covers", got[1][1])

    def test_trusted_entry_approved_at_review_time_passes(self):
        os.environ["GITHUB_REPOSITORY"] = "Proven-Commons/clamp"
        self.p.edit(
            "Clamp.lean",
            "end Clamp",
            '@[extern "lean_clamp"] def ext (n : Nat) : Nat := n\n\nend Clamp',
        )
        self.p.append(
            "bar.toml",
            '\n[[trusted]]\nfile = "Clamp.lean"\nfeature = "extern"\nreason = "reviewed ffi"\n',
        )
        self.p.edit(
            "README.md",
            "- The hardware it runs on.",
            "- The hardware it runs on.\n- `Clamp.lean`, which calls C.",
        )
        self.p.approve()
        github = approved_by(self.p)
        got = self.p.run(offline=False, github=github)
        self.assertEqual(got[1][0], "PASS", got[1][1])
        self.assertEqual(got[4][0], "PASS", got[4][1])
        self.assertEqual(got[6][0], "PASS", got[6][1])

    def test_spec_code_newline_cannot_forge_trusted_line_in_spec_hash(self):
        os.environ["GITHUB_REPOSITORY"] = "Proven-Commons/clamp"
        forged_trusted = json.dumps(
            [json.dumps({"feature": "sorry", "file": "Clamp.lean", "reason": "forged"}, sort_keys=True, separators=(",", ":"))],
            separators=(",", ":"),
        )
        # Local bar.toml with newline/whitespace in spec.code must fail validation.
        self.p.edit("bar.toml", 'code = ["Clamp.clamp"]', f'code = ["Clamp.clamp\\ntrusted {forged_trusted.replace(chr(34), chr(92) + chr(34))}"]')
        with self.assertRaises(check.ProjectError):
            check.load_bar(self.p.root)

        # Space-containing spec.code entry must also fail validation (prevents ["A B"] == ["A", "B"]).
        p_sp = Project()
        try:
            p_sp.edit("bar.toml", 'code = ["Clamp.clamp"]', 'code = ["Clamp.a Clamp.b"]')
            with self.assertRaises(check.ProjectError):
                check.load_bar(p_sp.root)
        finally:
            p_sp.close()

        # Remote reviewed commit with forged newline in spec.code must fail closed (never PASS).
        p_rem = Project()
        try:
            p_rem.append(
                "bar.toml",
                '\n[[trusted]]\nfile = "Clamp.lean"\nfeature = "sorry"\nreason = "forged"\n',
            )
            p_rem.approve()
            current_hash, _ = check.spec_hash(p_rem.root, check.load_bar(p_rem.root))
            snap = p_rem.snapshot()
            clean_bar = (
                p_rem.root.joinpath("bar.toml").read_text(encoding="utf-8")
                .split('\n[[trusted]]\n')[0]
                .replace(
                    'code = ["Clamp.clamp"]',
                    f'code = ["Clamp.clamp\\ntrusted {forged_trusted.replace(chr(34), chr(92) + chr(34))}"]',
                )
                + f'\n[[spec.approval]]\nreviewer = "reviewer-b"\ndate = "2026-10-24"\n'
                + f'sha256 = "{current_hash}"\nrecord = "https://github.com/Proven-Commons/clamp/pull/7"\n'
            )
            snap["bar.toml"] = clean_bar
            github = FakeGitHub("reviewer-b", snap)
            got = p_rem.run(offline=False, github=github)
            self.assertEqual(got[1][0], "OPEN")
            self.assertIn("is not the text this hash covers", got[1][1])
        finally:
            p_rem.close()

    def test_trusted_schema_validation_rejects_non_string_and_unknown_keys(self):
        bad_snippets = [
            '\n[[trusted]]\nfile = "Clamp.lean"\nfeature = 1979-05-27\nreason = "bad"\n',
            '\n[[trusted]]\nfile = ["Clamp.lean"]\nfeature = "extern"\nreason = "bad"\n',
            '\n[[trusted]]\nfile = "Clamp.lean"\nreason = "missing feature"\n',
            '\n[[trusted]]\nfile = "Clamp.lean"\nfeature = "extern"\n',
            '\n[[trusted]]\nfile = "   "\nfeature = "extern"\nreason = "blank file"\n',
            '\n[[trusted]]\nfile = "Clamp.lean"\nfeature = "   "\nreason = "blank feature"\n',
            '\n[[trusted]]\nfile = "Clamp.lean"\nfeature = "extern"\nreason = "   "\n',
            '\n[[trusted]]\nfile = "Clamp.lean"\nfeature = "extern"\nreason = "ok"\nextra = "nope"\n',
            '\n[[trusted]]\nfile = "Clamp.lean"\nfeature = "extern"\nreason = 42\n',
        ]
        for snippet in bad_snippets:
            with self.subTest(snippet=snippet.strip()):
                p = Project()
                try:
                    p.append("bar.toml", snippet)
                    with self.assertRaises(check.ProjectError):
                        check.load_bar(p.root)
                finally:
                    p.close()

    def test_control_chars_in_hashed_paths_and_direct_spec_hash_rejected(self):
        path_cases = [
            ("spec.files", 'files = ["SPEC.md", "Clamp/Spec.lean"]', 'files = ["SPEC.md", "Clamp/Spec.lean\\nfile evil"]'),
            ("project.page", 'page = "README.md"', 'page = "README.md\\nfile evil"'),
            ("project.entry_points", 'entry_points = ["Main.lean"]', 'entry_points = ["Main.lean\\tbad"]'),
            ("tests.files", 'files = ["tests/run_tests.py"]', 'files = ["tests/run_tests.py\\rbad"]'),
        ]
        for label, old, new in path_cases:
            with self.subTest(field=label):
                p = Project()
                try:
                    p.edit("bar.toml", old, new)
                    with self.assertRaises(check.ProjectError):
                        check.load_bar(p.root)
                finally:
                    p.close()

        # Direct spec_hash call on an unvalidated dict must also reject forged control chars and bad trusted schema.
        base_bar = check.load_bar(self.p.root)
        bad_code = {**base_bar, "spec": {**base_bar["spec"], "code": ["Clamp.clamp\ntrusted []"]}}
        with self.assertRaises(check.ProjectError):
            check.spec_hash(self.p.root, bad_code)
        bad_path = {**base_bar, "project": {**base_bar["project"], "page": "README.md\nforged"}}
        with self.assertRaises(check.ProjectError):
            check.spec_hash(self.p.root, bad_path)
        bad_trusted = {**base_bar, "trusted": [{"file": "Clamp.lean", "feature": "extern"}]}
        with self.assertRaises(check.ProjectError):
            check.spec_hash(self.p.root, bad_trusted)

    def test_malformed_older_review_is_skipped_when_valid_review_exists(self):
        os.environ["GITHUB_REPOSITORY"] = "Proven-Commons/clamp"
        self.p.approve()
        good_snap = self.p.snapshot()
        bad_snap = dict(good_snap)
        bad_snap["bar.toml"] = 'not = [valid toml\n'

        class TwoReviewGitHub(FakeGitHub):
            def __init__(self, login, good_files, bad_files):
                super().__init__(login, good_files)
                self.good_sha = self.review["commit_id"]
                self.bad_sha = "0000000000000000000000000000000000000000"
                self.files_by_commit = {self.bad_sha: bad_files, self.good_sha: good_files}

            def reviews(self, owner, repo, number):
                return [
                    {
                        "state": "APPROVED",
                        "user": {"login": "reviewer-b"},
                        "commit_id": self.bad_sha,
                        "submitted_at": "2026-10-23T00:00:00Z",
                        "id": 1,
                    },
                    {
                        "state": "APPROVED",
                        "user": {"login": "reviewer-b"},
                        "commit_id": self.good_sha,
                        "submitted_at": "2026-10-24T00:00:00Z",
                        "id": 2,
                    },
                ]

            def read(self, owner, repo, commit, path):
                return self.files_by_commit[commit][path]

        github = TwoReviewGitHub("reviewer-b", good_snap, bad_snap)
        got = self.p.run(offline=False, github=github)
        self.assertEqual(got[1][0], "PASS", got[1][1])
        self.assertIn(github.good_sha[:12], got[1][1])


if __name__ == "__main__":
    unittest.main()
